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
- **ORM**: SQLAlchemy 2.0+ with Alembic
- **認証**: JWT (PyJWT, python-jose)
- **バリデーション**: Pydantic 2.0+
- **テスト**: pytest, pytest-asyncio
- **ドキュメント**: OpenAPI/Swagger (FastAPI自動生成)
- **ASGI Server**: Uvicorn
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
          
      async def authenticate_user(self, email: str, password: str) -> Optional[User]:
          # 認証ロジック
  
  class ArticleService:
      def __init__(self, article_repo: ArticleRepository):
          self.article_repo = article_repo
      
      async def create_article(self, article_data: ArticleCreate, author_id: int) -> Article:
          # 記事作成ロジック
          
      async def get_user_articles(self, user_id: int) -> List[Article]:
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
      async def get_by_id(self, user_id: int) -> Optional[User]:
      async def get_by_email(self, email: str) -> Optional[User]:
      async def update(self, user_id: int, user_data: dict) -> Optional[User]:
      async def delete(self, user_id: int) -> bool:
  ```

## 3. データベース設計

### 3.1 データベーススキーマ

#### Users テーブル
```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
```

#### Articles テーブル
```sql
CREATE TABLE articles (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    author_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
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
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    articles = relationship("Article", back_populates="author")

# app/models/article.py  
class Article(Base):
    __tablename__ = "articles"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_published = Column(Boolean, default=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    author = relationship("User", back_populates="articles")
```

## 4. APIインターフェース

### 4.1 認証エンドポイント
```python
POST /auth/register
Content-Type: application/json
{
    "email": "user@example.com",
    "password": "secure123",
    "full_name": "John Doe"
}

POST /auth/login
Content-Type: application/x-www-form-urlencoded
username=user@example.com&password=secure123

Response:
{
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "bearer"
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

GET /articles/?skip=0&limit=10&search=keyword
Authorization: Bearer {token} (optional)

GET /articles/{article_id}
PUT /articles/{article_id}
DELETE /articles/{article_id}
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
│   ├── schemas/             # Pydanticスキーマ
│   │   ├── __init__.py
│   │   ├── user.py
│   │   └── article.py
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
├── .env
├── docker-compose.yml
└── Dockerfile
```

## 11. 実装上の注意事項

- **セキュリティ**: 機密情報は環境変数で管理、SQLインジェクション対策済みORM使用
- **パフォーマンス**: 非同期処理の活用、適切なインデックス設計
- **保守性**: 依存性注入パターン採用、レイヤー分離
- **テスタビリティ**: モック可能な構造、テストDBの分離
- **エラーハンドリング**: 統一されたエラーレスポンス形式
- **ログ**: 構造化ログ、セキュリティログの実装