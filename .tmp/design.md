# 詳細設計書 - Python API設計（ユーザー・記事管理システム）

## 1. アーキテクチャ概要

### 1.1 システム構成図

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   API Gateway   │    │   Database      │
│   (Client)      │◄──►│   (FastAPI)     │◄──►│   (PostgreSQL)  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Redis Cache   │
                       │   (Optional)    │
                       └─────────────────┘

レイヤー構成:
┌─────────────────────────────────────────┐
│           API Layer (FastAPI)           │
├─────────────────────────────────────────┤
│         Business Logic Layer            │
├─────────────────────────────────────────┤
│         Data Access Layer (ORM)         │
├─────────────────────────────────────────┤
│         Database Layer (PostgreSQL)     │
└─────────────────────────────────────────┘
```

### 1.2 技術スタック

- **言語**: Python 3.9+
- **フレームワーク**: FastAPI 0.104+
- **データベース**: PostgreSQL 14+ (開発時はSQLite)
- **ORM**: SQLAlchemy 2.0+ with Alembic (Mapped & mapped_column構文)
- **認証**: JWT (PyJWT, python-jose)
- **バリデーション**: Pydantic 2.0+
- **テスト**: pytest, pytest-asyncio
- **ドキュメント**: OpenAPI/Swagger (FastAPI自動生成)
- **ASGI Server**: Uvicorn
- **タイムゾーン**: ZoneInfo (Python 3.9+標準ライブラリ, デフォルト: Asia/Tokyo)
- **その他**: bcrypt, python-multipart, python-dotenv

## 2. コンポーネント設計

### 2.1 コンポーネント一覧

| コンポーネント名 | 責務 | 依存関係 |
|------------------|------|----------|
| API Routes | HTTPリクエスト処理、レスポンス返却 | Services |
| Services | ビジネスロジック実行 | Repositories, Auth |
| Repositories | データアクセス抽象化 | Database Models |
| Database Models | データ構造定義、ORM設定 | SQLAlchemy |
| Auth Module | 認証・認可処理 | JWT, Database |
| Validation Schemas | リクエスト/レスポンス検証 | Pydantic |

### 2.2 各コンポーネントの詳細

#### API Routes (`app/api/`)
- **目的**: HTTPエンドポイントの定義、リクエスト/レスポンス処理
- **公開インターフェース**:
  ```python
  # app/api/users.py
  @router.post("/users/", response_model=UserResponse)
  async def create_user(user: UserCreate, db: Session = Depends(get_db))
  
  @router.get("/users/me", response_model=UserResponse)
  async def get_current_user(current_user: User = Depends(get_current_user))
  
  # app/api/articles.py  
  @router.post("/articles/", response_model=ArticleResponse)
  async def create_article(article: ArticleCreate, current_user: User = Depends(get_current_user))
  
  @router.get("/articles/", response_model=List[ArticleResponse])
  async def get_articles(skip: int = 0, limit: int = 100, db: Session = Depends(get_db))
  ```

#### Services (`app/services/`)
- **目的**: ビジネスロジックの実装、トランザクション管理
- **公開インターフェース**:
  ```python
  class UserService:
      def __init__(self, user_repo: UserRepository):
          self.user_repo = user_repo
      
      async def create_user(self, user_data: UserCreate) -> User:
          # パスワードハッシュ化、重複チェック等
          
      async def authenticate_user(self, username: str, password: str) -> Optional[User]:
          # 認証ロジック
  
  class ArticleService:
      def __init__(self, article_repo: ArticleRepository):
          self.article_repo = article_repo
      
      async def create_article(self, article_data: ArticleCreate, author_id: UUID) -> Article:
          # 記事作成ロジック
          
      async def get_user_articles(self, user_id: UUID) -> List[Article]:
          # ユーザーの記事取得
  ```

#### Repositories (`app/repositories/`)
- **目的**: データアクセスの抽象化、クエリ実装
- **公開インターフェース**:
  ```python
  class UserRepository:
      def __init__(self, db: Session):
          self.db = db
      
      async def create(self, user: User) -> User:
      async def get_by_id(self, user_id: UUID) -> Optional[User]:
      async def get_by_username(self, username: str) -> Optional[User]:
      async def get_by_email(self, email: str) -> Optional[User]:
      async def update(self, user_id: UUID, user_data: dict) -> Optional[User]:
      async def delete(self, user_id: UUID) -> bool:
  ```

## 3. データベース設計

### 3.1 データベーススキーマ

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

### 3.2 SQLAlchemy Models
```python
# app/models/user.py
import uuid
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.config import settings

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4, 
        index=True
    )
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    full_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo(settings.timezone))
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo(settings.timezone)),
        onupdate=lambda: datetime.now(ZoneInfo(settings.timezone))
    )
    
    articles: Mapped[list["Article"]] = relationship("Article", back_populates="author")

# app/models/article.py  
class Article(Base):
    __tablename__ = "articles"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4, 
        index=True
    )
    title: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(String)  # または Text
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("users.id")
    )
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo(settings.timezone))
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(ZoneInfo(settings.timezone)),
        onupdate=lambda: datetime.now(ZoneInfo(settings.timezone))
    )
    
    author: Mapped["User"] = relationship("User", back_populates="articles")
```

## 4. APIインターフェース

### 4.1 認証エンドポイント
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

### 4.2 ユーザー管理エンドポイント
```python
GET /users/me
Authorization: Bearer {token}

PUT /users/me
Authorization: Bearer {token}
{
    "full_name": "Updated Name"
}

DELETE /users/me
Authorization: Bearer {token}
```

### 4.3 記事管理エンドポイント
```python
POST /articles/
Authorization: Bearer {token}
{
    "title": "Article Title",
    "content": "Article content...",
    "is_published": true
}

Response:
{
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "title": "Article Title",
    "content": "Article content...",
    "author_id": "550e8400-e29b-41d4-a716-446655440000",
    "is_published": true,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
}

GET /articles/?skip=0&limit=10&search=keyword
Authorization: Bearer {token} (optional)

GET /articles/{article_id}     # article_id は UUID
PUT /articles/{article_id}     # article_id は UUID
DELETE /articles/{article_id}  # article_id は UUID
Authorization: Bearer {token}
```

## 5. 認証・セキュリティ設計

### 5.1 JWT認証フロー
```python
# app/auth.py
class JWTAuth:
    def create_access_token(self, data: dict, expires_delta: timedelta = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(hours=24)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt
    
    def verify_token(self, token: str):
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            return None
```

### 5.2 パスワードセキュリティ
```python
# app/security.py
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)
```

### 5.3 権限管理
```python
# app/auth.py
def check_article_permission(current_user: User, article: Article):
    if current_user.is_admin:
        return True
    return current_user.id == article.author_id
```

## 6. エラーハンドリング

### 6.1 エラー分類
```python
# app/exceptions.py
class APIException(Exception):
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail

class ValidationError(APIException):
    def __init__(self, detail: str):
        super().__init__(422, detail)

class AuthenticationError(APIException):
    def __init__(self):
        super().__init__(401, "認証が必要です")

class AuthorizationError(APIException):
    def __init__(self):
        super().__init__(403, "権限がありません")

class NotFoundError(APIException):
    def __init__(self, resource: str = "リソース"):
        super().__init__(404, f"{resource}が見つかりません")
```

### 6.2 グローバルエラーハンドラー
```python
# app/main.py
@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )
```

## 7. テスト戦略

### 7.1 単体テスト
- **カバレッジ目標**: 80%以上
- **テストフレームワーク**: pytest, pytest-asyncio
- **テスト構成**:
  ```python
  tests/
  ├── conftest.py          # テスト設定
  ├── test_auth.py         # 認証テスト
  ├── test_users.py        # ユーザー機能テスト
  ├── test_articles.py     # 記事機能テスト
  └── test_repositories.py # データアクセステスト
  ```

### 7.2 統合テスト
```python
# tests/test_integration.py
async def test_user_article_workflow():
    # ユーザー登録 → ログイン → 記事作成 → 記事取得
    pass
```

## 8. パフォーマンス最適化

### 8.1 データベース最適化
- インデックス設計（users.email, articles.author_id等）
- クエリ最適化（N+1問題回避）
- コネクションプール設定

### 8.2 キャッシュ戦略
```python
# app/cache.py
from redis import Redis

class CacheService:
    def __init__(self):
        self.redis = Redis.from_url("redis://localhost:6379")
    
    async def get_articles_cache(self, key: str):
        return self.redis.get(f"articles:{key}")
        
    async def set_articles_cache(self, key: str, data: str, expire: int = 300):
        self.redis.setex(f"articles:{key}", expire, data)
```

## 9. デプロイメント

### 9.1 Docker設定
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 9.2 環境設定管理
```python
# app/config.py
from pydantic import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./test.db"
    secret_key: str = "your-secret-key"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    timezone: str = "Asia/Tokyo"  # デフォルトタイムゾーン（日本語対応必須のため）
    
    class Config:
        env_file = ".env"

settings = Settings()
```

## 10. プロジェクト構成

```
api_project/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPIアプリケーション
│   ├── config.py            # 設定管理
│   ├── database.py          # DB接続設定
│   ├── auth.py              # 認証処理
│   ├── security.py          # セキュリティユーティリティ
│   ├── exceptions.py        # カスタム例外
│   ├── api/                 # APIルート
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── users.py
│   │   └── articles.py
│   ├── models/              # データベースモデル
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── article.py
│   ├── schemas/             # Pydanticスキーマ (UUID対応)
│   │   ├── __init__.py
│   │   ├── user.py         # from uuid import UUID を含む
│   │   └── article.py      # from uuid import UUID を含む
│   ├── services/            # ビジネスロジック
│   │   ├── __init__.py
│   │   ├── user_service.py
│   │   └── article_service.py
│   └── repositories/        # データアクセス
│       ├── __init__.py
│       ├── user_repository.py
│       └── article_repository.py
├── tests/                   # テストコード
├── alembic/                 # DBマイグレーション
├── requirements.txt
├── .env                     # 環境変数設定
├── docker-compose.yml
└── Dockerfile

### 10.2 環境変数設定例（.env）
```bash
# データベース設定
DATABASE_URL=sqlite:///./app.db
# 本番環境の場合
# DATABASE_URL=postgresql://user:password@localhost/api_db

# セキュリティ設定
SECRET_KEY=your-super-secret-key-here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# タイムゾーン設定（日本語対応必須要件）
TIMEZONE=Asia/Tokyo

# CORS設定
CORS_ORIGINS=http://localhost:3000,http://localhost:8080
```

## 11. 実装上の注意事項

- **SQLAlchemy 2.0+ 構文**: 最新のMapped・mapped_column構文を使用
  - 型安全性の向上（Mapped[Type]による明示的な型定義）
  - IDEの補完サポート改善
  - ランタイムでの型チェック強化
  - relationshipの型安全性向上
- **タイムゾーン対応**: ZoneInfoを使用した堅牢な時刻管理
  - `DateTime(timezone=True)`でタイムゾーン情報を保持
  - `settings.timezone`による設定可能なタイムゾーン（デフォルト: Asia/Tokyo）
  - UTC変換不要でローカル時間を正確に管理
  - 日本語対応必須要件に合わせたタイムゾーン設計
- **UUID使用**: 全てのテーブルの主キーはUUID v4を使用
  - セキュリティ向上（IDの推測困難）
  - 分散システムでの一意性保証
  - マイグレーション時の重複回避
- **ユーザー識別**: usernameとemailの両方をユニーク制約で管理
  - usernameによるログイン認証（ユーザビリティ向上）
  - emailとusername両方でのユニーク性チェック必須
  - username文字数制限（50文字）でパフォーマンス最適化
  - インデックス設定でログイン認証の高速化
- **セキュリティ**: 機密情報は環境変数で管理、SQLインジェクション対策済みORM使用
- **パフォーマンス**: 非同期処理の活用、適切なインデックス設計
- **保守性**: 依存性注入パターン採用、レイヤー分離
- **テスタビリティ**: モック可能な構造、テストDBの分離
- **エラーハンドリング**: 統一されたエラーレスポンス形式
- **ログ**: 構造化ログ、セキュリティログの実装
- **UUID取り扱い**: PydanticスキーマでもUUID型を使用、文字列変換時は適切にハンドリング