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

## 3. 修正案ワークフロー詳細設計

### 3.1 ワークフロー概要

修正案のワークフローは以下の3つの主要フェーズで構成されます：

1. **提出フェーズ**: 一般ユーザーが修正案を作成・編集・提出
2. **レビューフェーズ**: 承認者が修正案を確認・修正指示・自ら修正
3. **承認フェーズ**: 承認者が最終承認または却下

### 3.2 状態遷移詳細

```mermaid
stateDiagram-v2
    [*] --> Draft: 修正案作成
    Draft --> Draft: 提案者による編集
    Draft --> UnderReview: レビュー依頼
    UnderReview --> UnderReview: 承認者による直接編集
    UnderReview --> RevisionRequested: 承認者が修正指示
    RevisionRequested --> RevisionRequested: 提案者/承認者による編集
    RevisionRequested --> UnderReview: 再提出
    UnderReview --> Approved: 承認
    UnderReview --> Rejected: 却下
    Draft --> Withdrawn: 取り下げ
    Approved --> [*]
    Rejected --> [*]
    Withdrawn --> [*]
```

### 3.3 状態別アクセス権限マトリクス

| 状態 | 提案者 | 承認者 | SV | 管理者 | 一般ユーザー |
|------|--------|--------|----|---------|--------------| 
| Draft | 閲覧・編集・削除 | - | - | 閲覧 | - |
| UnderReview | 閲覧のみ | 閲覧・編集・承認・却下・修正指示 | 閲覧・編集・承認・却下・修正指示 | 全権限 | - |
| RevisionRequested | 閲覧・編集 | 閲覧・編集・承認・却下 | 閲覧・編集・承認・却下 | 全権限 | - |
| Approved | 閲覧のみ | 閲覧のみ | 閲覧のみ | 閲覧のみ | 閲覧のみ※ |
| Rejected | 閲覧のみ | 閲覧のみ | 閲覧のみ | 閲覧のみ | - |
| Withdrawn | 閲覧のみ | 閲覧のみ | 閲覧のみ | 閲覧のみ | - |

※承認済み修正案は記事の対象者設定に従って一般ユーザーも閲覧可能

### 3.4 修正案編集権限の詳細実装

```python
class RevisionPermissionService:
    """修正案の編集権限を管理するサービス"""
    
    async def can_edit_revision(
        self,
        user: User,
        revision: Revision
    ) -> Tuple[bool, Optional[str]]:
        """
        修正案の編集可否を判定
        Returns: (編集可否, 不可の場合の理由)
        """
        # 管理者は常に編集可能
        if user.role == Role.ADMIN:
            return True, None
            
        # 状態別の権限チェック
        if revision.status == RevisionStatus.DRAFT:
            # 下書きは提案者のみ編集可能
            if user.id == revision.proposer_id:
                return True, None
            return False, "下書きは提案者のみ編集可能です"
            
        elif revision.status == RevisionStatus.UNDER_REVIEW:
            # レビュー中は承認者とSVが編集可能
            if user.role in [Role.APPROVER, Role.SUPERVISOR]:
                return True, None
            return False, "レビュー中の修正案は承認者のみ編集可能です"
            
        elif revision.status == RevisionStatus.REVISION_REQUESTED:
            # 修正依頼中は提案者と承認者が編集可能
            if user.id == revision.proposer_id:
                return True, None
            if user.role in [Role.APPROVER, Role.SUPERVISOR]:
                return True, None
            return False, "修正依頼中の修正案は提案者または承認者のみ編集可能です"
            
        else:
            # その他の状態（承認済み、却下、取り下げ）は編集不可
            return False, f"{revision.status.value}の修正案は編集できません"
```

### 3.5 承認者による修正機能

承認者が修正案を直接編集する際の実装方針：

1. **編集履歴の記録**
   ```python
   class RevisionEditHistory(Base):
       """修正案の編集履歴"""
       __tablename__ = "revision_edit_histories"
       
       id = Column(UUID, primary_key=True)
       revision_id = Column(UUID, ForeignKey("revisions.id"))
       editor_id = Column(UUID, ForeignKey("users.id"))
       editor_role = Column(Enum(Role))
       edited_at = Column(DateTime, default=datetime.utcnow)
       changes = Column(JSON)  # 変更内容のJSON
       comment = Column(Text)  # 編集理由
   ```

2. **通知機能**
   ```python
   class NotificationService:
       async def notify_revision_edited_by_approver(
           self,
           revision: Revision,
           editor: User,
           changes: Dict[str, Any]
       ):
           """承認者による編集を提案者に通知"""
           notification = Notification(
               recipient_id=revision.proposer_id,
               type=NotificationType.REVISION_EDITED,
               title="修正案が承認者により編集されました",
               content=f"{editor.name}さんが修正案を編集しました",
               metadata={
                   "revision_id": str(revision.id),
                   "editor_id": str(editor.id),
                   "changes": changes
               }
           )
           await self.notification_repository.create(notification)
   ```

3. **編集内容の差分表示**
   ```python
   class RevisionDiffService:
       async def get_edit_history_diff(
           self,
           revision_id: UUID,
           from_version: int,
           to_version: int
       ) -> Dict[str, Any]:
           """指定バージョン間の差分を取得"""
           histories = await self.get_histories_between_versions(
               revision_id, from_version, to_version
           )
           return self.calculate_diff(histories)
   ```

### 3.6 修正指示機能の実装

```python
class RevisionInstructionService:
    """修正指示機能を管理するサービス"""
    
    async def request_modification(
        self,
        revision_id: UUID,
        approver_id: UUID,
        instruction: ModificationInstruction
    ) -> Revision:
        """修正指示を作成"""
        # 権限チェック
        if not await self.can_request_modification(approver_id, revision_id):
            raise PermissionError("修正指示の権限がありません")
            
        # 修正指示を保存
        revision = await self.revision_repository.get(revision_id)
        revision.status = RevisionStatus.REVISION_REQUESTED
        
        # 修正指示内容を保存
        instruction_record = RevisionInstruction(
            revision_id=revision_id,
            instructor_id=approver_id,
            instruction_text=instruction.text,
            required_fields=instruction.required_fields,  # 修正が必要なフィールドリスト
            due_date=instruction.due_date,
            priority=instruction.priority
        )
        await self.instruction_repository.create(instruction_record)
        
        # 提案者に通知
        await self.notification_service.notify_modification_requested(
            revision, approver_id, instruction
        )
        
        return revision
```

### 3.7 承認プロセスの実装

```python
class ApprovalService:
    """承認プロセスを管理するサービス"""
    
    async def approve_revision(
        self,
        revision_id: UUID,
        approver_id: UUID,
        approval_comment: Optional[str] = None
    ) -> Revision:
        """修正案を承認"""
        async with self.db.begin():
            revision = await self.revision_repository.get(revision_id)
            
            # 承認可能な状態かチェック
            if revision.status not in [RevisionStatus.UNDER_REVIEW, RevisionStatus.REVISION_REQUESTED]:
                raise InvalidStateError("この状態の修正案は承認できません")
                
            # 承認処理
            revision.status = RevisionStatus.APPROVED
            revision.approver_id = approver_id
            revision.approved_at = datetime.utcnow()
            revision.approval_comment = approval_comment
            
            # 承認履歴を記録
            approval_history = ApprovalHistory(
                revision_id=revision_id,
                approver_id=approver_id,
                action=ApprovalAction.APPROVED,
                comment=approval_comment,
                created_at=datetime.utcnow()
            )
            await self.history_repository.create(approval_history)
            
            # 関係者に通知
            await self.notification_service.notify_approval(revision, approver_id)
            
            # 記事への反映処理をキューに追加
            await self.queue_service.enqueue_article_update(revision)
            
            return revision
```

## 4. データフロー

### 4.1 修正案提出フロー

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

### 4.2 承認者による修正フロー

```mermaid
sequenceDiagram
    participant Approver
    participant API
    participant Permission
    participant Revision
    participant History
    participant Notification
    participant Proposer
    
    Approver->>API: PATCH /api/v1/revisions/{id}
    API->>Permission: Check Edit Permission
    Permission->>API: Permission Granted
    API->>Revision: Update Revision
    Revision->>History: Record Edit History
    Revision->>API: Revision Updated
    API->>Notification: Send Notification
    Notification->>Proposer: Notify Changes
    API->>Approver: 200 OK
```

### 4.3 データ変換

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

## 5. APIインターフェース

### 5.1 内部API

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
# レビュー依頼（提出）
POST   /api/v1/revisions/{revision_id}/submit-for-review
# 修正案承認
POST   /api/v1/revisions/{revision_id}/approve
# 修正案却下
POST   /api/v1/revisions/{revision_id}/reject
# 修正指示
POST   /api/v1/revisions/{revision_id}/request-modification
# 承認者による修正案編集
PATCH  /api/v1/revisions/{revision_id}/approver-edit
# 編集履歴取得
GET    /api/v1/revisions/{revision_id}/edit-history
# コメント追加
POST   /api/v1/revisions/{revision_id}/comments
# 修正指示一覧取得
GET    /api/v1/revisions/{revision_id}/instructions
# 修正指示解決
PATCH  /api/v1/revisions/{revision_id}/instructions/{instruction_id}/resolve
```

### 5.2 外部API連携

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

## 6. エラーハンドリング

### 6.1 エラー分類

- **認証エラー (401)**: 無効なトークン、期限切れ → 再ログイン要求
- **権限エラー (403)**: アクセス権限なし → エラーメッセージ表示
- **検証エラー (422)**: 入力データ不正 → 詳細なエラー情報返却
- **競合エラー (409)**: 同一記事への同時修正 → リトライまたはマージ提案
- **外部システムエラー (503)**: Sweet/Ctstage連携失敗 → フォールバック処理

### 6.2 エラー通知

- エラーログ: 構造化ログ（JSON形式）でファイル出力
- 監視: 重要度別アラート設定
- ユーザー通知: APIレスポンスに詳細なエラー情報を含める

## 7. セキュリティ設計

### 7.1 認証・認可

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

### 7.2 データ保護

- パスワード: bcryptハッシュ化（コスト係数12）
- 機密データ: 環境変数での管理
- 通信: HTTPS必須
- SQLインジェクション対策: SQLAlchemyのパラメータバインディング
- XSS対策: pydanticによる入力検証

## 8. テスト戦略

### 8.1 単体テスト

- **カバレッジ目標**: 80%以上
- **テストフレームワーク**: pytest, pytest-asyncio
- **モック**: pytest-mock使用
- **重点テスト項目**:
  - 認証・認可ロジック
  - 修正案の差分計算
  - 権限チェック機能

### 8.2 統合テスト

- APIエンドポイントテスト（TestClient使用）
- データベース接続テスト
- Redis接続テスト
- 外部システム連携テスト（モック使用）

## 9. パフォーマンス最適化

### 9.1 想定される負荷

- 同時接続ユーザー数: 100人
- APIレスポンス時間: 95%のリクエストで500ms以下
- 記事検索: 10万件のデータから1秒以内

### 9.2 最適化方針

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

## 10. デプロイメント

### 10.1 デプロイ構成

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

### 10.2 設定管理

- **環境変数**:
  ```env
  DATABASE_URL=postgresql+asyncpg://user:pass@localhost/dbname
  REDIS_URL=redis://localhost:6379/0
  JWT_SECRET_KEY=your-secret-key
  SWEET_API_URL=https://sweet.example.com/api
  CTSTAGE_API_URL=https://ctstage.example.com/api
  ```
- **設定クラス**: pydantic-settingsによる型安全な設定管理

## 11. 実装上の注意事項

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

## 12. 情報カテゴリマスターデータ

### 12.1 カテゴリ定義

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

### 12.2 データベース設計への反映

#### 修正案ワークフロー関連テーブル

```sql
-- 修正案テーブル（拡張版）
CREATE TABLE revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_article_id VARCHAR(50) NOT NULL,
    proposer_id UUID NOT NULL REFERENCES users(id),
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    -- status: draft, under_review, revision_requested, approved, rejected, withdrawn
    
    -- 修正内容（before/after）
    before_title TEXT,
    after_title TEXT,
    before_info_category VARCHAR(2),
    after_info_category VARCHAR(2),
    before_keywords TEXT,
    after_keywords TEXT,
    before_importance BOOLEAN,
    after_importance BOOLEAN,
    before_publish_start TIMESTAMP,
    after_publish_start TIMESTAMP,
    before_publish_end TIMESTAMP,
    after_publish_end TIMESTAMP,
    before_target VARCHAR(20),
    after_target VARCHAR(20),
    before_question TEXT,
    after_question TEXT,
    before_answer TEXT,
    after_answer TEXT,
    before_additional_comment TEXT,
    after_additional_comment TEXT,
    
    reason TEXT NOT NULL,
    approver_id UUID REFERENCES users(id),
    approved_at TIMESTAMP,
    approval_comment TEXT,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1,  -- 楽観的ロック用
    
    CONSTRAINT fk_before_category FOREIGN KEY (before_info_category) REFERENCES info_categories(code),
    CONSTRAINT fk_after_category FOREIGN KEY (after_info_category) REFERENCES info_categories(code)
);

-- 修正案編集履歴テーブル
CREATE TABLE revision_edit_histories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    revision_id UUID NOT NULL REFERENCES revisions(id),
    editor_id UUID NOT NULL REFERENCES users(id),
    editor_role VARCHAR(20) NOT NULL,
    edited_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    changes JSONB NOT NULL,  -- 変更内容の詳細
    comment TEXT,
    version_before INTEGER NOT NULL,
    version_after INTEGER NOT NULL
);

-- 修正指示テーブル
CREATE TABLE revision_instructions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    revision_id UUID NOT NULL REFERENCES revisions(id),
    instructor_id UUID NOT NULL REFERENCES users(id),
    instruction_text TEXT NOT NULL,
    required_fields TEXT[],  -- 修正が必要なフィールドのリスト
    priority VARCHAR(10) DEFAULT 'normal',  -- low, normal, high, urgent
    due_date TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP,
    resolution_comment TEXT
);

-- 承認履歴テーブル
CREATE TABLE approval_histories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    revision_id UUID NOT NULL REFERENCES revisions(id),
    actor_id UUID NOT NULL REFERENCES users(id),
    action VARCHAR(20) NOT NULL,  -- approved, rejected, revision_requested
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 通知テーブル
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recipient_id UUID NOT NULL REFERENCES users(id),
    type VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB,
    is_read BOOLEAN DEFAULT FALSE,
    read_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- インデックス
CREATE INDEX idx_revisions_status ON revisions(status);
CREATE INDEX idx_revisions_proposer ON revisions(proposer_id);
CREATE INDEX idx_revisions_article ON revisions(target_article_id);
CREATE INDEX idx_edit_histories_revision ON revision_edit_histories(revision_id);
CREATE INDEX idx_instructions_revision ON revision_instructions(revision_id);
CREATE INDEX idx_approval_histories_revision ON approval_histories(revision_id);
CREATE INDEX idx_notifications_recipient ON notifications(recipient_id, is_read);

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

### 12.3 API実装での考慮事項

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

### 12.4 フロントエンド実装の推奨事項

- ドロップダウンメニューでの選択UI
- カテゴリコード（2文字）での内部管理
- 表示名での視覚的な識別
- アンダースコア（_）で始まるカテゴリは業務系として視覚的にグループ化
- カテゴリの有効/無効切り替えによる柔軟な運用