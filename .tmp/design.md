# 詳細設計書 - 既存ナレッジ修正案管理システム

## 1. アーキテクチャ概要

### 1.1 システム構成図

```mermaid
graph TB
    subgraph "フロントエンド層"
        CLIENT[クライアント<br/>Web/Mobile]
    end
    
    subgraph "APIゲートウェイ層"
        FASTAPI[FastAPI<br/>v0.115.12]
    end
    
    subgraph "アプリケーション層"
        AUTH[認証サービス<br/>JWT]
        USER[ユーザー管理<br/>サービス]
        ARTICLE[記事参照<br/>サービス]
        REVISION[修正案管理<br/>サービス]
        WORKFLOW[承認ワークフロー<br/>サービス]
    end
    
    subgraph "キャッシュ層"
        REDIS[Redis<br/>v3.0.504]
    end
    
    subgraph "データ永続化層"
        POSTGRES[(PostgreSQL<br/>asyncpg)]
    end
    
    subgraph "外部システム連携"
        SWEET[Sweet<br/>シフト管理]
        CTSTAGE[Ctstage<br/>レポーティング]
    end
    
    CLIENT --> FASTAPI
    FASTAPI --> AUTH
    FASTAPI --> USER
    FASTAPI --> ARTICLE
    FASTAPI --> REVISION
    FASTAPI --> WORKFLOW
    
    AUTH --> REDIS
    ARTICLE --> REDIS
    REVISION --> REDIS
    
    USER --> POSTGRES
    ARTICLE --> POSTGRES
    REVISION --> POSTGRES
    WORKFLOW --> POSTGRES
    
    USER -.-> SWEET
    USER -.-> CTSTAGE
```

### 1.2 技術スタック

- **言語**: Python 3.12+ (3.13未満)
- **フレームワーク**: FastAPI 0.115.12
- **データベース**: 
  - PostgreSQL (asyncpg 0.30.0)
  - Redis 3.0.504 (aioredis 2.0.1)
- **ORM**: SQLAlchemy 2.0.40 (非同期対応)
- **認証**: python-jose 3.4.0 (JWT)
- **パスワード暗号化**: passlib 1.7.4 / bcrypt 4.0.1
- **バリデーション**: pydantic 2.11.3
- **マイグレーション**: alembic 1.15.2
- **テスト**: pytest, pytest-asyncio
- **ドキュメント**: OpenAPI/Swagger (自動生成)

## 2. コンポーネント設計

### 2.1 コンポーネント一覧

| コンポーネント名 | 責務 | 依存関係 |
|-----------------|------|----------|
| AuthService | JWT認証、ユーザー認証 | UserRepository, Redis |
| UserService | ユーザー管理、プロファイル拡張 | UserRepository, ExternalSystemAdapter |
| ArticleService | 既存記事の参照、検索 | ArticleRepository, Redis |
| RevisionService | 修正案の作成、管理、差分計算 | RevisionRepository, ArticleService |
| WorkflowService | 承認ワークフロー、権限管理 | RevisionService, UserService |
| ExternalSystemAdapter | Sweet/Ctstage連携 | HTTPクライアント |
| CacheManager | Redisキャッシュ管理 | aioredis |

### 2.2 各コンポーネントの詳細

#### AuthService

- **目的**: ユーザー認証とJWTトークン管理
- **公開インターフェース**:
  ```python
  class AuthService:
      async def authenticate_user(self, username: str, password: str) -> Optional[User]
      async def create_access_token(self, user_id: UUID) -> str
      async def verify_token(self, token: str) -> Optional[TokenData]
      async def refresh_token(self, refresh_token: str) -> str
  ```
- **内部実装方針**: 
  - bcryptによるパスワードハッシュ化
  - JWTトークンの有効期限管理
  - Redisでのトークンブラックリスト管理

#### UserService

- **目的**: ユーザー情報とプロファイル拡張フィールドの管理
- **公開インターフェース**:
  ```python
  class UserService:
      async def create_user(self, user_data: UserCreate) -> User
      async def get_user(self, user_id: UUID) -> Optional[User]
      async def update_user_profile(self, user_id: UUID, profile_data: UserProfileUpdate) -> User
      async def update_external_mappings(self, user_id: UUID, sweet_name: str, ctstage_name: str) -> User
      async def set_supervisor_status(self, user_id: UUID, is_sv: bool) -> User
  ```
- **内部実装方針**:
  - 拡張フィールド（sweet_name、ctstage_name、is_sv）の管理
  - 外部システムとの名前マッピング検証

#### RevisionService

- **目的**: 修正案の作成、管理、差分計算
- **公開インターフェース**:
  ```python
  class RevisionService:
      async def create_revision(self, revision_data: RevisionCreate, user_id: UUID) -> Revision
      async def get_revision(self, revision_id: UUID) -> Optional[Revision]
      async def update_revision(self, revision_id: UUID, update_data: RevisionUpdate, user_id: UUID) -> Revision
      async def calculate_diff(self, revision_id: UUID) -> RevisionDiff
      async def list_revisions(self, filters: RevisionFilter, pagination: Pagination) -> RevisionList
  ```
- **内部実装方針**:
  - 修正前後の全フィールドを個別に管理
  - 差分計算ロジックの実装
  - ステータス管理（pending/approved/rejected）

## 3. データフロー

### 3.1 修正案提出フロー

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Auth
    participant Revision
    participant DB
    participant Cache
    
    Client->>API: POST /api/v1/revisions
    API->>Auth: Verify JWT Token
    Auth->>API: User Info
    API->>Revision: Create Revision
    Revision->>DB: Store Revision Data
    Revision->>Cache: Invalidate Article Cache
    Revision->>API: Revision Created
    API->>Client: 201 Created
```

### 3.2 データ変換

- **入力データ形式**: 
  ```json
  {
    "target_article_id": "uuid",
    "modifications": {
      "title": "新しいタイトル",
      "info_category": "02",
      "keywords": ["キーワード1", "キーワード2"],
      "importance": true,
      "target": "社内",
      "question": "質問内容",
      "answer": "回答内容"
    },
    "reason": "修正理由"
  }
  ```
- **処理過程**: 
  - 既存記事データの取得
  - 修正フィールドの差分計算
  - 修正履歴の生成
  - ステータスの初期化（pending）
- **出力データ形式**: 修正案オブジェクト（差分情報含む）

## 4. APIインターフェース

### 4.1 内部API

#### ユーザー管理API
```python
# ユーザー登録
POST   /api/v1/users/register
# ユーザー認証
POST   /api/v1/auth/login
# ユーザー情報取得
GET    /api/v1/users/{user_id}
# プロファイル更新
PATCH  /api/v1/users/{user_id}/profile
# 外部システムマッピング更新
PATCH  /api/v1/users/{user_id}/external-mappings
```

#### 修正案管理API
```python
# 修正案作成
POST   /api/v1/revisions
# 修正案一覧取得
GET    /api/v1/revisions?status={status}&page={page}
# 修正案詳細取得
GET    /api/v1/revisions/{revision_id}
# 修正案更新
PATCH  /api/v1/revisions/{revision_id}
# 差分表示
GET    /api/v1/revisions/{revision_id}/diff
```

#### 承認ワークフローAPI
```python
# 修正案承認
POST   /api/v1/revisions/{revision_id}/approve
# 修正案却下
POST   /api/v1/revisions/{revision_id}/reject
# コメント追加
POST   /api/v1/revisions/{revision_id}/comments
```

### 4.2 外部API連携

#### Sweet API連携
```python
class SweetAdapter:
    async def validate_user_name(self, sweet_name: str) -> bool
    async def get_shift_info(self, sweet_name: str, date: datetime) -> Optional[ShiftInfo]
```

#### Ctstage API連携
```python
class CtstageAdapter:
    async def validate_reporter_name(self, ctstage_name: str) -> bool
    async def get_report_data(self, ctstage_name: str, period: DateRange) -> Optional[ReportData]
```

## 5. エラーハンドリング

### 5.1 エラー分類

- **認証エラー (401)**: 無効なトークン、期限切れ → 再ログイン要求
- **権限エラー (403)**: アクセス権限なし → エラーメッセージ表示
- **検証エラー (422)**: 入力データ不正 → 詳細なエラー情報返却
- **競合エラー (409)**: 同一記事への同時修正 → リトライまたはマージ提案
- **外部システムエラー (503)**: Sweet/Ctstage連携失敗 → フォールバック処理

### 5.2 エラー通知

- エラーログ: 構造化ログ（JSON形式）でファイル出力
- 監視: 重要度別アラート設定
- ユーザー通知: APIレスポンスに詳細なエラー情報を含める

## 6. セキュリティ設計

### 6.1 認証・認可

- **JWT認証**:
  - アクセストークン有効期限: 30分
  - リフレッシュトークン有効期限: 7日
  - トークンブラックリスト管理（Redis）
  
- **ロールベースアクセス制御 (RBAC)**:
  ```python
  class Role(Enum):
      GENERAL_USER = "general"     # 一般ユーザー
      SUPERVISOR = "supervisor"    # スーパーバイザー
      APPROVER = "approver"       # 承認者
      ADMIN = "admin"             # 管理者
  ```

### 6.2 データ保護

- パスワード: bcryptハッシュ化（コスト係数12）
- 機密データ: 環境変数での管理
- 通信: HTTPS必須
- SQLインジェクション対策: SQLAlchemyのパラメータバインディング
- XSS対策: pydanticによる入力検証

## 7. テスト戦略

### 7.1 単体テスト

- **カバレッジ目標**: 80%以上
- **テストフレームワーク**: pytest, pytest-asyncio
- **モック**: pytest-mock使用
- **重点テスト項目**:
  - 認証・認可ロジック
  - 修正案の差分計算
  - 権限チェック機能

### 7.2 統合テスト

- APIエンドポイントテスト（TestClient使用）
- データベース接続テスト
- Redis接続テスト
- 外部システム連携テスト（モック使用）

## 8. パフォーマンス最適化

### 8.1 想定される負荷

- 同時接続ユーザー数: 100人
- APIレスポンス時間: 95%のリクエストで500ms以下
- 記事検索: 10万件のデータから1秒以内

### 8.2 最適化方針

- **キャッシュ戦略**:
  - 記事データ: Redis（TTL: 1時間）
  - ユーザー情報: Redis（TTL: 30分）
  - 頻繁アクセスデータの事前ロード
  
- **データベース最適化**:
  - インデックス: article_id、user_id、status、is_sv
  - クエリ最適化: N+1問題の回避
  - 接続プール: 最小10、最大50接続

- **非同期処理**:
  - asyncpgによる非同期DB接続
  - aioredisによる非同期キャッシュ操作

## 9. デプロイメント

### 9.1 デプロイ構成

```bash
project/
├── app/
│   ├── main.py           # FastAPIアプリケーション
│   ├── api/              # APIエンドポイント
│   ├── core/             # 設定、セキュリティ
│   ├── services/         # ビジネスロジック
│   ├── repositories/     # データアクセス層
│   ├── models/           # SQLAlchemyモデル
│   └── schemas/          # Pydanticスキーマ
├── alembic/              # DBマイグレーション
├── tests/                # テストコード
├── .env.example          # 環境変数サンプル
├── requirements.txt      # 依存関係
└── docker-compose.yml    # ローカル開発環境
```

### 9.2 設定管理

- **環境変数**:
  ```env
  DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname
  REDIS_URL=redis://localhost:6379/0
  JWT_SECRET_KEY=your-secret-key
  SWEET_API_URL=https://sweet.example.com/api
  CTSTAGE_API_URL=https://ctstage.example.com/api
  ```
- **設定クラス**: pydantic-settingsによる型安全な設定管理

## 10. 実装上の注意事項

- **Redis 3.0.504互換性**: 
  - 基本的なGET/SET/EXPIRE操作のみ使用
  - Lua scriptingやStreamは使用不可
  - パイプライン処理での最適化
  
- **非同期処理**:
  - すべてのDB操作は非同期で実装
  - 適切なawait使用とエラーハンドリング
  
- **トランザクション管理**:
  - 修正案作成時のACID特性保証
  - ロールバック処理の実装
  
- **ログ出力**:
  - 構造化ログ（JSON形式）
  - リクエストID付与によるトレーサビリティ
  
- **外部システム連携**:
  - タイムアウト設定（デフォルト30秒）
  - リトライ機構（最大3回）
  - サーキットブレーカーパターンの実装

## 11. 情報カテゴリマスターデータ

### 11.1 カテゴリ定義

情報カテゴリとして選択可能な項目を以下に定義します：

```python
# app/constants/categories.py
from enum import Enum

class InfoCategory(Enum):
    ACCOUNTING_FINANCE = ("_会計・財務", "01")
    STARTUP_TROUBLE = ("_起動トラブル", "02")
    PAYROLL_YEAREND = ("_給与・年末調整", "03")
    DEPRECIATION_ASSET = ("_減価・ﾘｰｽ/資産管理", "04")
    PUBLIC_MEDICAL = ("_公益・医療会計", "05")
    CONSTRUCTION_COST = ("_工事・原価", "06")
    RECEIVABLE_PAYABLE = ("_債権・債務", "07")
    OFFICE_MANAGEMENT = ("_事務所管理", "08")
    HUMAN_RESOURCES = ("_人事", "09")
    TAX_RELATED = ("_税務関連", "10")
    E_FILING = ("_電子申告", "11")
    SALES = ("_販売", "12")
    EDGE_TRACKER = ("EdgeTracker", "13")
    MJS_CONNECT = ("MJS-Connect関連", "14")
    INSTALL_MOU = ("インストール・MOU", "15")
    KANTAN_SERIES = ("かんたん！シリーズ", "16")
    OTHER_NON_SYSTEM = ("その他（システム以外）", "17")
    OTHER_MJS_SYSTEM = ("その他MJSシステム", "18")
    OTHER_SYSTEM_COMMON = ("その他システム（共通）", "19")
    HARDWARE_HDD = ("ハード関連(HHD)", "20")
    HARDWARE_SOFTWARE = ("ハード関連（ソフトフェア）", "21")
    MY_NUMBER = ("マイナンバー", "22")
    WORKFLOW = ("ワークフロー", "23")
    TEMPORARY_RECEPTION = ("一時受付用", "24")
    OPERATION_RULES = ("運用ルール", "25")
    CUSTOMER_INFO = ("顧客情報", "26")
    
    def __init__(self, display_name: str, code: str):
        self.display_name = display_name
        self.code = code
```

### 11.2 データベース設計への反映

```sql
-- 情報カテゴリマスターテーブル
CREATE TABLE info_categories (
    id SERIAL PRIMARY KEY,
    code VARCHAR(2) UNIQUE NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    display_order INTEGER NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 初期データ投入
INSERT INTO info_categories (code, display_name, display_order) VALUES
('01', '_会計・財務', 1),
('02', '_起動トラブル', 2),
('03', '_給与・年末調整', 3),
('04', '_減価・ﾘｰｽ/資産管理', 4),
('05', '_公益・医療会計', 5),
('06', '_工事・原価', 6),
('07', '_債権・債務', 7),
('08', '_事務所管理', 8),
('09', '_人事', 9),
('10', '_税務関連', 10),
('11', '_電子申告', 11),
('12', '_販売', 12),
('13', 'EdgeTracker', 13),
('14', 'MJS-Connect関連', 14),
('15', 'インストール・MOU', 15),
('16', 'かんたん！シリーズ', 16),
('17', 'その他（システム以外）', 17),
('18', 'その他MJSシステム', 18),
('19', 'その他システム（共通）', 19),
('20', 'ハード関連(HHD)', 20),
('21', 'ハード関連（ソフトフェア）', 21),
('22', 'マイナンバー', 22),
('23', 'ワークフロー', 23),
('24', '一時受付用', 24),
('25', '運用ルール', 25),
('26', '顧客情報', 26);

-- 既存記事テーブルと修正案テーブルのカテゴリフィールドは外部キー参照
ALTER TABLE existing_articles ADD COLUMN info_category_code VARCHAR(2) REFERENCES info_categories(code);
ALTER TABLE revision_proposals ADD CONSTRAINT fk_before_info_category 
    FOREIGN KEY (before_info_category) REFERENCES info_categories(code);
ALTER TABLE revision_proposals ADD CONSTRAINT fk_after_info_category 
    FOREIGN KEY (after_info_category) REFERENCES info_categories(code);
```

### 11.3 API実装での考慮事項

```python
# app/schemas/category.py
from pydantic import BaseModel
from typing import List

class InfoCategoryBase(BaseModel):
    code: str
    display_name: str
    display_order: int
    is_active: bool = True

class InfoCategoryResponse(InfoCategoryBase):
    id: int
    
    class Config:
        from_attributes = True

# app/api/v1/categories.py
@router.get("/categories", response_model=List[InfoCategoryResponse])
async def get_info_categories(
    is_active: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """情報カテゴリ一覧を取得"""
    query = select(InfoCategory).where(InfoCategory.is_active == is_active)
    query = query.order_by(InfoCategory.display_order)
    result = await db.execute(query)
    return result.scalars().all()
```

### 11.4 フロントエンド実装の推奨事項

- ドロップダウンメニューでの選択UI
- カテゴリコード（2文字）での内部管理
- 表示名での視覚的な識別
- アンダースコア（_）で始まるカテゴリは業務系として視覚的にグループ化
- カテゴリの有効/無効切り替えによる柔軟な運用