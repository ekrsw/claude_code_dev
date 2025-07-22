# 詳細設計書 - Python API設計（ユーザー・記事管理システム）

## 1. アーキテクチャ概要

### 1.1 システム構成図

```mermaid
graph TB
    Client[クライアント] --> API[FastAPI Server]
    API --> Auth[認証ミドルウェア]
    API --> Router[APIルーター]
    Router --> UserController[ユーザーコントローラー]
    Router --> ArticleController[記事コントローラー]
    UserController --> UserService[ユーザーサービス]
    ArticleController --> ArticleService[記事サービス]
    UserService --> UserRepo[ユーザーリポジトリ]
    ArticleService --> ArticleRepo[記事リポジトリ]
    UserRepo --> DB[(PostgreSQL)]
    ArticleRepo --> DB
    API --> Cache[(Redis)]
    UserService --> Cache
    ArticleService --> Cache
```

### 1.2 技術スタック

- **言語**: Python 3.12+（3.13未満）
- **フレームワーク**: FastAPI 0.115.12
- **データベース**: PostgreSQL（asyncpg 0.30.0）
- **ORM**: SQLAlchemy 2.0.40（非同期対応）
- **キャッシュ**: Redis 5.3.0 / aioredis 2.0.1
- **認証**: python-jose 3.4.0（JWT）
- **パスワード暗号化**: passlib 1.7.4 / bcrypt 4.0.1
- **バリデーション**: pydantic 2.11.3
- **設定管理**: pydantic-settings 2.9.1
- **マイグレーション**: alembic 1.15.2
- **ASGIサーバー**: uvicorn 0.34.2
- **テスト**: pytest 8.3.5 / pytest-asyncio 0.26.0 / pytest-cov 6.2.1
- **メール検証**: email_validator 2.2.0
- **ファイルアップロード**: python-multipart 0.0.20
- **暗号化**: cryptography 44.0.2
- **タイムゾーン**: tzdata 2025.2
- **デプロイメント**: 仮想環境 + systemd
- **Python新機能**: 型パラメータ構文、改善されたエラーメッセージ

## 2. コンポーネント設計

### 2.1 コンポーネント一覧

| コンポーネント名 | 責務 | 依存関係 |
| --- | --- | --- |
| APIルーター | エンドポイントの定義とリクエストの振り分け | コントローラー層 |
| 認証ミドルウェア | JWT認証の検証と認可 | JWTサービス |
| ユーザーコントローラー | ユーザー関連のAPIロジック | ユーザーサービス |
| 記事コントローラー | 記事関連のAPIロジック | 記事サービス、認証サービス |
| ユーザーサービス | ユーザー関連のビジネスロジック | ユーザーリポジトリ、Redis |
| 記事サービス | 記事関連のビジネスロジック | 記事リポジトリ、Redis |
| ユーザーリポジトリ | ユーザーデータの永続化 | SQLAlchemy、PostgreSQL |
| 記事リポジトリ | 記事データの永続化 | SQLAlchemy、PostgreSQL |
| JWTサービス | トークンの生成と検証 | python-jose |
| Redisサービス | キャッシュ管理 | aioredis |

### 2.2 各コンポーネントの詳細

#### APIルーター

- **目的**: APIエンドポイントの定義と整理
- **公開インターフェース**:
```python
from fastapi import APIRouter

# ユーザー関連
user_router = APIRouter(prefix="/api/v1/users", tags=["users"])
# 記事関連
article_router = APIRouter(prefix="/api/v1/articles", tags=["articles"])
# 認証関連
auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
```

#### 認証ミドルウェア

- **目的**: リクエストの認証と認可の処理
- **公開インターフェース**:
```python
from typing import Optional
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

class JWTBearer(HTTPBearer):
    async def __call__(self, credentials: HTTPAuthorizationCredentials) -> Optional[dict]:
        if credentials:
            if not credentials.scheme == "Bearer":
                raise HTTPException(status_code=403, detail="Invalid authentication scheme.")
            payload = self.verify_jwt(credentials.credentials)
            if not payload:
                raise HTTPException(status_code=403, detail="Invalid token or expired token.")
            return payload
        else:
            raise HTTPException(status_code=403, detail="Invalid authorization code.")
```

#### ユーザーサービス

- **目的**: ユーザー管理のビジネスロジック
- **公開インターフェース**:
```python
# Python 3.12の改善された型ヒント機能を活用
from __future__ import annotations
from typing import Generic, TypeVar, Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr

# Python 3.12の型パラメータ構文を活用
T = TypeVar('T')

class BaseService[T]:
    """ジェネリックベースサービスクラス"""
    pass

class UserService(BaseService[User]):
    """ユーザー管理サービス
    
    Python 3.12の改善されたエラーメッセージと
    性能向上の恩恵を受ける
    """
    
    async def create_user(self, user_data: UserCreate) -> User:
        """新規ユーザー作成"""
        pass
    
    async def authenticate_user(self, email: str, password: str) -> User | None:
        """ユーザー認証 - Python 3.10+ Union構文使用"""
        pass
    
    async def get_user(self, user_id: int) -> User | None:
        """ユーザー情報取得"""
        pass
    
    async def update_user(self, user_id: int, user_data: UserUpdate) -> User | None:
        """ユーザー情報更新"""
        pass
    
    async def delete_user(self, user_id: int) -> bool:
        """ユーザー削除"""
        pass
```

#### 記事サービス

- **目的**: 記事管理のビジネスロジック
- **公開インターフェース**:
```python
class ArticleService:
    async def create_article(self, article_data: ArticleCreate, author_id: int) -> Article:
        """記事作成"""
        pass
    
    async def get_articles(self, skip: int = 0, limit: int = 10, search: Optional[str] = None) -> List[Article]:
        """記事一覧取得（ページネーション、検索対応）"""
        pass
    
    async def get_article(self, article_id: int) -> Optional[Article]:
        """記事詳細取得"""
        pass
    
    async def update_article(self, article_id: int, article_data: ArticleUpdate, user_id: int) -> Optional[Article]:
        """記事更新"""
        pass
    
    async def delete_article(self, article_id: int, user_id: int) -> bool:
        """記事削除"""
        pass
```

## 3. データフロー

### 3.1 データフロー図

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Auth
    participant Service
    participant Cache
    participant DB

    Client->>API: HTTPリクエスト
    API->>Auth: 認証チェック
    Auth-->>API: 認証結果
    API->>Service: ビジネスロジック実行
    Service->>Cache: キャッシュ確認
    alt キャッシュヒット
        Cache-->>Service: キャッシュデータ
    else キャッシュミス
        Service->>DB: データ取得
        DB-->>Service: データ
        Service->>Cache: キャッシュ保存
    end
    Service-->>API: 処理結果
    API-->>Client: HTTPレスポンス
```

### 3.2 データ変換

- **入力データ形式**: JSON（pydanticによる自動バリデーション）
- **処理過程**: 
  1. pydanticモデルによるバリデーション
  2. ビジネスロジックでの処理
  3. SQLAlchemyモデルへの変換
  4. データベース保存
- **出力データ形式**: JSON（pydanticモデルによる自動シリアライズ）

## 4. APIインターフェース

### 4.1 内部API

#### Pydanticモデル定義

```python
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime

# ユーザー関連
class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    full_name: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8)

class User(UserBase):
    id: int
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# 記事関連
class ArticleBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1)
    summary: Optional[str] = Field(None, max_length=500)

class ArticleCreate(ArticleBase):
    pass

class ArticleUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content: Optional[str] = Field(None, min_length=1)
    summary: Optional[str] = Field(None, max_length=500)

class Article(ArticleBase):
    id: int
    author_id: int
    author: User
    created_at: datetime
    updated_at: datetime
    view_count: int = 0

    class Config:
        from_attributes = True

# 認証関連
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenData(BaseModel):
    user_id: int
    email: str
    is_admin: bool = False
```

### 4.2 外部API

#### RESTful APIエンドポイント

```yaml
# 認証API
POST   /api/v1/auth/register     # ユーザー登録
POST   /api/v1/auth/login        # ログイン
POST   /api/v1/auth/logout       # ログアウト
POST   /api/v1/auth/refresh      # トークンリフレッシュ

# ユーザーAPI
GET    /api/v1/users/me          # 現在のユーザー情報取得
GET    /api/v1/users/{user_id}   # ユーザー情報取得
PUT    /api/v1/users/me          # ユーザー情報更新
DELETE /api/v1/users/me          # ユーザー削除

# 記事API
GET    /api/v1/articles          # 記事一覧取得（ページネーション対応）
POST   /api/v1/articles          # 記事作成
GET    /api/v1/articles/{id}     # 記事詳細取得
PUT    /api/v1/articles/{id}     # 記事更新
DELETE /api/v1/articles/{id}     # 記事削除
GET    /api/v1/articles/search   # 記事検索
```

## 5. データベース設計

### 5.1 データベーススキーマ

#### Users テーブル
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
```

#### Articles テーブル
```sql
CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    author_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    is_published BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_articles_author_id ON articles(author_id);
CREATE INDEX idx_articles_created_at ON articles(created_at);
CREATE INDEX idx_articles_published ON articles(is_published);
```

### 5.2 SQLAlchemyモデル（非同期対応）
```python
# app/models/base.py
from __future__ import annotations
from typing import Any
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase

class Base(AsyncAttrs, DeclarativeBase):
    """SQLAlchemy Baseモデルクラス
    
    Python 3.12の改善されたエラーメッセージと
    型ヒント機能を活用
    """
    pass

# app/models/user.py
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.article import Article

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    articles: Mapped[List["Article"]] = relationship(
        "Article", 
        back_populates="author",
        cascade="all, delete-orphan"
    )

# app/models/article.py
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User

class Article(Base):
    __tablename__ = "articles"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text)
    summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    view_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    author: Mapped["User"] = relationship("User", back_populates="articles")
```

### 5.3 データベース接続設定

```python
# app/database.py
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, AsyncEngine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.config import settings

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    poolclass=NullPool,  # asyncpgは独自のコネクションプールを持つ
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

## 6. エラーハンドリング

### 6.1 エラー分類

- **400 Bad Request**: バリデーションエラー、不正なリクエスト
- **401 Unauthorized**: 認証が必要、トークン無効
- **403 Forbidden**: 権限不足
- **404 Not Found**: リソースが見つからない
- **409 Conflict**: 重複エラー（例：既存のメールアドレス）
- **422 Unprocessable Entity**: 処理不可能なエンティティ
- **500 Internal Server Error**: サーバー内部エラー

### 6.2 エラー通知

```python
class APIError(BaseModel):
    error_code: str
    message: str
    details: Optional[dict] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

# エラーレスポンス例
{
    "error_code": "VALIDATION_ERROR",
    "message": "入力データが無効です",
    "details": {
        "field": "email",
        "error": "有効なメールアドレスを入力してください"
    },
    "timestamp": "2025-01-22T10:30:00Z"
}
```

## 7. セキュリティ設計

### 7.1 認証・認可
```python
POST /auth/register
Content-Type: application/json
{
    "username": "johndoe",
    "email": "user@example.com",
    "password": "secure123",
    "full_name": "John Doe"
}

Response:
{
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "johndoe",
    "email": "user@example.com",
    "full_name": "John Doe",
    "is_active": true,
    "created_at": "2024-01-01T00:00:00Z"
}

POST /auth/login
Content-Type: application/x-www-form-urlencoded
username=johndoe&password=secure123

Response:
{
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "bearer",
    "user_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

- **JWT認証**:
  - アクセストークン有効期限: 30分
  - リフレッシュトークン有効期限: 7日
  - トークンはRedisで管理（ブラックリスト方式）

- **権限レベル**:
  - ゲスト: 記事閲覧のみ
  - 一般ユーザー: 自身の記事のCRUD
  - 管理者: 全ユーザー・記事の管理

### 7.2 データ保護

- パスワードはbcryptでハッシュ化（コストファクター: 12）
- SQLインジェクション対策: SQLAlchemyのパラメータバインディング使用
- XSS対策: pydanticによる入力値検証
- CORS設定: 許可されたオリジンのみ
- HTTPS通信の強制
- 機密情報はログに出力しない

## 8. テスト戦略

### 8.1 単体テスト

- カバレッジ目標: 85%以上
- テストフレームワーク: pytest, pytest-asyncio
- モックツール: pytest-mock
- テスト対象:
  - サービス層のビジネスロジック
  - バリデーション
  - 認証・認可

### 8.2 統合テスト

- APIエンドポイントのE2Eテスト
- データベース操作を含むテスト
- 認証フローの完全なテスト
- テスト用データベース（SQLite）使用

## 9. パフォーマンス最適化

### 9.1 想定される負荷

- 同時接続数: 100ユーザー
- 1秒あたりのリクエスト数: 50RPS
- 95パーセンタイル応答時間: 500ms以下

### 9.2 最適化方針

- **データベース**:
  - 適切なインデックス設定
  - N+1問題の回避（eager loading）
  - コネクションプーリング（最小: 5, 最大: 20）

- **キャッシュ戦略**:
  - 記事一覧: 5分間キャッシュ
  - 記事詳細: 10分間キャッシュ
  - ユーザー情報: 30分間キャッシュ

- **非同期処理**:
  - FastAPIの非同期エンドポイント
  - asyncpgによる非同期DB操作

## 10. デプロイメント

### 10.1 デプロイ構成

#### 開発環境
```bash
# Python 3.12+の使用を確認
python --version  # Python 3.12.x であることを確認

# 仮想環境の作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存ライブラリのインストール
pip install -r requirements.txt

# データベースマイグレーション
alembic upgrade head

# アプリケーション起動
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### 本番環境
```bash
# systemdサービスファイル: /etc/systemd/system/api.service
[Unit]
Description=User Article API
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=apiuser
Group=apiuser
WorkingDirectory=/opt/api
Environment=PATH=/opt/api/venv/bin
ExecStart=/opt/api/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
EnvironmentFile=/opt/api/.env

[Install]
WantedBy=multi-user.target

# サービスの有効化と起動
sudo systemctl enable api
sudo systemctl start api
```

### 10.2 設定管理

```python
# app/config.py
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # アプリケーション設定
    app_name: str = "User Article API"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 8000
    
    # データベース設定
    database_url: str  # postgresql+asyncpg://user:pass@host/db
    
    # Redis設定
    redis_url: str = "redis://localhost:6379"
    
    # JWT設定
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # CORS設定
    allowed_origins: List[str] = ["http://localhost:3000"]
    
    # ログ設定
    log_level: str = "INFO"
    log_file: str = "/var/log/api/app.log"
    
    class Config:
        env_file = ".env"
        
settings = Settings()
```

### 10.3 環境変数設定例

```bash
# .env
# アプリケーション設定
APP_NAME=User Article API
DEBUG=false
HOST=0.0.0.0
PORT=8000
# Python 3.12+を使用することを明示
PYTHON_VERSION_MIN=3.12
PYTHON_VERSION_MAX=3.13

# データベース設定
DATABASE_URL=postgresql+asyncpg://apiuser:apipass@localhost/apidb

# Redis設定
REDIS_URL=redis://localhost:6379

# JWT設定
SECRET_KEY=your-super-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS設定
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com

# ログ設定
LOG_LEVEL=INFO
LOG_FILE=/var/log/api/app.log
```

## 11. 実装上の注意事項

### 11.1 Python 3.12の活用
- **型パラメータ構文**: `class Service[T]` や `def function[T](param: T) -> T` を積極活用
- **Union構文**: `Optional[T]` より `T | None` を優先使用
- **改善されたエラーメッセージ**: デバッグ時を意識したコード記述
- **性能向上**: Python 3.12の内部最適化の恩恵を受ける
- **`from __future__ import annotations`**: 前方参照の問題を解決

### 11.2 一般的な注意事項
- 非同期処理を活用してパフォーマンスを最適化する
- エラーハンドリングは統一的に行い、適切なHTTPステータスコードを返す
- ログは構造化ログ（JSON形式）で出力し、分析しやすくする
- データベーストランザクションは適切にスコープを管理する
- 循環参照を避けるため、依存性注入パターンを使用する
- 型ヒントを積極的に使用し、IDEのサポートを最大化する
- docstringを書いて、自動的にAPIドキュメントを生成する
- 設定値はハードコーディングせず、環境変数から取得する
- テストデータは本番データと明確に分離する
- マイグレーションは必ずレビューしてから実行する
- モノリシック構成でシンプルに保ち、必要に応じてスケールアップを検討する
- Redisキャッシュはaioredisを使用して非同期対応する

### 11.3 バージョン管理とライブラリ対応
- **Pythonバージョン**: 3.12.x を基準、本番環境での統一必須
- **主要ライブラリ**: FastAPI 0.115.12, SQLAlchemy 2.0.40, Pydantic 2.11.3 等
- **全ライブラリ**: Python 3.12 対応確認済み ✓
- **注意事項**: Python 3.13 リリース時の互換性チェック

### 10.4 プロジェクト構造

```
api_project/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPIアプリケーション
│   ├── config.py            # 設定管理
│   ├── database.py          # DB接続設定
│   ├── dependencies.py      # 依存性注入
│   ├── exceptions.py        # カスタム例外
│   ├── api/                 # APIルート
│   │   ├── __init__.py
│   │   ├── v1/              # API v1
│   │       ├── __init__.py
│   │       ├── auth.py      # 認証エンドポイント
│   │       ├── users.py     # ユーザーエンドポイント
│   │       └── articles.py  # 記事エンドポイント
│   ├── models/              # SQLAlchemyモデル
│   │   ├── __init__.py
│   │   ├── base.py          # Baseモデル
│   │   ├── user.py          # Userモデル
│   │   └── article.py       # Articleモデル
│   ├── schemas/             # Pydanticスキーマ
│   │   ├── __init__.py
│   │   ├── user.py          # ユーザースキーマ
│   │   ├── article.py       # 記事スキーマ
│   │   └── auth.py          # 認証スキーマ
│   ├── services/            # ビジネスロジック
│   │   ├── __init__.py
│   │   ├── auth_service.py  # 認証サービス
│   │   ├── user_service.py  # ユーザーサービス
│   │   ├── article_service.py # 記事サービス
│   │   └── cache_service.py   # キャッシュサービス
│   └── repositories/        # データアクセス
│       ├── __init__.py
│       ├── base.py          # ベースリポジトリ
│       ├── user_repository.py
│       └── article_repository.py
├── tests/                   # テストコード
│   ├── __init__.py
│   ├── conftest.py          # pytest設定
│   ├── test_auth.py         # 認証テスト
│   ├── test_users.py        # ユーザーテスト
│   └── test_articles.py     # 記事テスト
├── alembic/                 # マイグレーション
│   ├── versions/
│   ├── env.py
│   └── script.py.mako
├── requirements.txt         # 依存ライブラリ
├── alembic.ini             # Alembic設定
├── .env                     # 環境変数
├── .env.example             # 環境変数テンプレート
├── .gitignore
└── README.md                # プロジェクトドキュメント
```