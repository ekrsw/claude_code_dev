# 詳細設計書 - Python API設計（既存ナレッジ修正案管理システム）

## 1. アーキテクチャ概要

### 1.1 システム構成図

```mermaid
graph TB
    Client[クライアント] --> API[FastAPI Server]
    API --> Auth[認証ミドルウェア]
    API --> Router[APIルーター]
    Router --> UserController[ユーザーコントローラー]
    Router --> ArticleController[既存記事コントローラー]
    Router --> RevisionController[修正案コントローラー]
    Router --> ApprovalController[承認ワークフローコントローラー]
    UserController --> UserService[ユーザーサービス]
    ArticleController --> ArticleService[記事参照サービス]
    RevisionController --> RevisionService[修正案サービス]
    ApprovalController --> ApprovalService[承認サービス]
    UserService --> UserRepo[ユーザーリポジトリ]
    ArticleService --> ArticleRepo[記事リポジトリ]
    RevisionService --> RevisionRepo[修正案リポジトリ]
    ApprovalService --> ApprovalRepo[承認リポジトリ]
    UserRepo --> DB[(PostgreSQL)]
    ArticleRepo --> DB
    RevisionRepo --> DB
    ApprovalRepo --> DB
    API --> Cache[(Redis)]
    UserService --> Cache
    ArticleService --> Cache
    RevisionService --> Cache
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
| 認証ミドルウェア | JWT認証の検証と認可（役割別アクセス制御） | JWTサービス |
| ユーザーコントローラー | ユーザー関連のAPIロジック | ユーザーサービス |
| 記事コントローラー | 既存記事参照のAPIロジック | 記事サービス、認証サービス |
| 修正案コントローラー | 修正案管理のAPIロジック | 修正案サービス、認証サービス |
| 承認ワークフローコントローラー | 承認・却下処理のAPIロジック | 承認サービス、認証サービス |
| ユーザーサービス | ユーザー関連のビジネスロジック | ユーザーリポジトリ、Redis |
| 記事サービス | 既存記事参照のビジネスロジック | 記事リポジトリ、Redis |
| 修正案サービス | 修正案管理のビジネスロジック | 修正案リポジトリ、Redis |
| 承認サービス | 承認ワークフローのビジネスロジック | 承認リポジトリ、Redis |
| ユーザーリポジトリ | ユーザーデータの永続化 | SQLAlchemy、PostgreSQL |
| 記事リポジトリ | 既存記事データの永続化 | SQLAlchemy、PostgreSQL |
| 修正案リポジトリ | 修正案データの永続化 | SQLAlchemy、PostgreSQL |
| 承認リポジトリ | 承認データの永続化 | SQLAlchemy、PostgreSQL |
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
# 既存記事関連
article_router = APIRouter(prefix="/api/v1/articles", tags=["articles"])
# 修正案関連
revision_router = APIRouter(prefix="/api/v1/revisions", tags=["revisions"])
# 承認ワークフロー関連
approval_router = APIRouter(prefix="/api/v1/approvals", tags=["approvals"])
# 認証関連
auth_router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
```

#### 認証ミドルウェア

- **目的**: リクエストの認証と認可の処理（役割別アクセス制御）
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

# 役割別認証
def require_admin(current_user: dict = Depends(JWTBearer())):
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

def require_supervisor(current_user: dict = Depends(JWTBearer())):
    if not (current_user.get("is_sv") or current_user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Supervisor access required")
    return current_user

def require_approver(current_user: dict = Depends(JWTBearer())):
    if not (current_user.get("is_approver") or current_user.get("is_sv") or current_user.get("is_admin")):
        raise HTTPException(status_code=403, detail="Approver access required")
    return current_user
```

#### 修正案サービス

- **目的**: 修正案管理のビジネスロジック
- **公開インターフェース**:
```python
# Python 3.12の改善された型ヒント機能を活用
from __future__ import annotations
from typing import Generic, TypeVar, Optional, List
from datetime import datetime
from pydantic import BaseModel

# Python 3.12の型パラメータ構文を活用
T = TypeVar('T')

class BaseService[T]:
    """ジェネリックベースサービスクラス"""
    pass

class RevisionService(BaseService[RevisionProposal]):
    """修正案管理サービス
    
    Python 3.12の改善されたエラーメッセージと
    性能向上の恩恵を受ける
    """
    
    async def create_revision_proposal(self, proposal_data: RevisionProposalCreate, proposer_id: int) -> RevisionProposal:
        """修正案作成"""
        pass
    
    async def get_revision_proposals(self, 
                                   skip: int = 0, 
                                   limit: int = 10, 
                                   status: Optional[str] = None,
                                   article_id: Optional[str] = None) -> List[RevisionProposal]:
        """修正案一覧取得（ステータス・記事別フィルタ対応）"""
        pass
    
    async def get_revision_proposal(self, revision_id: int) -> RevisionProposal | None:
        """修正案詳細取得"""
        pass
    
    async def update_revision_proposal(self, revision_id: int, proposal_data: RevisionProposalUpdate, user_id: int) -> RevisionProposal | None:
        """修正案更新（提案者のみ）"""
        pass
    
    async def delete_revision_proposal(self, revision_id: int, user_id: int) -> bool:
        """修正案削除（提案者のみ）"""
        pass
    
    async def get_revision_diff(self, revision_id: int) -> RevisionDiff:
        """修正案差分取得"""
        pass
    
    async def add_comment(self, revision_id: int, comment_data: CommentCreate, user_id: int) -> Comment:
        """修正案コメント追加"""
        pass
```

#### 承認サービス

- **目的**: 承認ワークフローのビジネスロジック
- **公開インターフェース**:
```python
class ApprovalService:
    async def approve_revision(self, revision_id: int, approver_id: int, approval_data: ApprovalCreate) -> RevisionProposal:
        """修正案承認"""
        pass
    
    async def reject_revision(self, revision_id: int, approver_id: int, rejection_data: RejectionCreate) -> RevisionProposal:
        """修正案却下"""
        pass
    
    async def get_pending_approvals(self, approver_id: int, skip: int = 0, limit: int = 10) -> List[RevisionProposal]:
        """承認待ち修正案一覧取得"""
        pass
    
    async def get_approval_history(self, revision_id: int) -> List[ApprovalHistory]:
        """承認履歴取得"""
        pass
    
    async def check_approval_authority(self, user_id: int, article_id: str) -> bool:
        """承認権限チェック"""
        pass
```

## 3. データフロー

### 3.1 データフロー図

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Auth
    participant RevisionService
    participant ApprovalService
    participant Cache
    participant DB

    Client->>API: 修正案提出リクエスト
    API->>Auth: 認証チェック
    Auth-->>API: 認証結果
    API->>RevisionService: 修正案作成
    RevisionService->>DB: 修正案データ保存
    DB-->>RevisionService: 保存完了
    RevisionService-->>API: 修正案作成結果
    API-->>Client: レスポンス

    Client->>API: 承認リクエスト
    API->>Auth: 承認権限チェック
    Auth-->>API: 権限確認結果
    API->>ApprovalService: 承認処理
    ApprovalService->>DB: 承認データ更新
    DB-->>ApprovalService: 更新完了
    ApprovalService->>Cache: キャッシュ更新
    ApprovalService-->>API: 承認処理結果
    API-->>Client: レスポンス
```

### 3.2 データ変換

- **入力データ形式**: JSON（pydanticによる自動バリデーション）
- **処理過程**: 
  1. pydanticモデルによるバリデーション
  2. ビジネスロジックでの処理（差分計算、権限チェック）
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
from enum import Enum

# ユーザー関連（既存）
class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    full_name: Optional[str] = None
    sweet_name: Optional[str] = None
    ctstage_name: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class User(UserBase):
    id: int
    is_active: bool
    is_admin: bool
    is_sv: bool
    is_approver: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# 既存記事関連
class ExistingArticleBase(BaseModel):
    article_id: str
    article_number: str
    approval_group: str

class ExistingArticle(ExistingArticleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# 修正案関連
class RevisionStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"

class RevisionProposalBase(BaseModel):
    target_article_id: str
    reason: str = Field(..., min_length=1, max_length=1000)
    # 修正内容（修正前後データ）
    before_title: Optional[str] = None
    after_title: Optional[str] = None
    before_info_category: Optional[str] = None
    after_info_category: Optional[str] = None
    before_keywords: Optional[str] = None
    after_keywords: Optional[str] = None
    before_importance: Optional[bool] = None
    after_importance: Optional[bool] = None
    before_publish_start: Optional[datetime] = None
    after_publish_start: Optional[datetime] = None
    before_publish_end: Optional[datetime] = None
    after_publish_end: Optional[datetime] = None
    before_target: Optional[str] = None
    after_target: Optional[str] = None
    before_question: Optional[str] = None
    after_question: Optional[str] = None
    before_answer: Optional[str] = None
    after_answer: Optional[str] = None
    before_additional_comment: Optional[str] = None
    after_additional_comment: Optional[str] = None

class RevisionProposalCreate(RevisionProposalBase):
    pass

class RevisionProposalUpdate(BaseModel):
    reason: Optional[str] = Field(None, min_length=1, max_length=1000)
    # 修正内容の更新（部分更新対応）
    before_title: Optional[str] = None
    after_title: Optional[str] = None
    # ... 他の修正内容フィールド

class RevisionProposal(RevisionProposalBase):
    id: int
    revision_id: str  # UUID
    proposer_id: int
    proposer: User
    status: RevisionStatus
    approver_id: Optional[int] = None
    approver: Optional[User] = None
    processed_at: Optional[datetime] = None
    comments: Optional[str] = None
    review_deadline: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# 差分表示用
class RevisionDiff(BaseModel):
    revision_id: str
    changes: List[dict]  # 変更項目のリスト
    
# コメント関連
class CommentBase(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class CommentCreate(CommentBase):
    pass

class Comment(CommentBase):
    id: int
    revision_id: str
    user_id: int
    user: User
    created_at: datetime

    class Config:
        from_attributes = True

# 承認関連
class ApprovalBase(BaseModel):
    approval_comment: Optional[str] = Field(None, max_length=1000)

class ApprovalCreate(ApprovalBase):
    pass

class RejectionCreate(ApprovalBase):
    rejection_reason: str = Field(..., min_length=1, max_length=1000)

class ApprovalHistory(BaseModel):
    id: int
    revision_id: str
    approver_id: int
    approver: User
    action: str  # "approved" or "rejected"
    comment: Optional[str] = None
    processed_at: datetime

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
    is_sv: bool = False
    is_approver: bool = False
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

# 既存記事API
GET    /api/v1/articles          # 既存記事一覧取得（ページネーション対応）
GET    /api/v1/articles/{article_id}     # 既存記事詳細取得
GET    /api/v1/articles/search   # 記事検索

# 修正案API
GET    /api/v1/revisions         # 修正案一覧取得（ステータス・記事別フィルタ）
POST   /api/v1/revisions         # 修正案作成
GET    /api/v1/revisions/{revision_id}   # 修正案詳細取得
PUT    /api/v1/revisions/{revision_id}   # 修正案更新（提案者のみ）
DELETE /api/v1/revisions/{revision_id}   # 修正案削除（提案者のみ）
GET    /api/v1/revisions/{revision_id}/diff  # 修正案差分取得
POST   /api/v1/revisions/{revision_id}/comments  # コメント追加
GET    /api/v1/revisions/{revision_id}/comments  # コメント一覧取得

# 承認ワークフローAPI
POST   /api/v1/approvals/{revision_id}/approve  # 修正案承認
POST   /api/v1/approvals/{revision_id}/reject   # 修正案却下
GET    /api/v1/approvals/pending                # 承認待ち一覧取得
GET    /api/v1/approvals/{revision_id}/history  # 承認履歴取得
```

## 5. データベース設計

### 5.1 データベーススキーマ

#### Users テーブル

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    sweet_name VARCHAR(255),
    ctstage_name VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    is_admin BOOLEAN DEFAULT FALSE,
    is_sv BOOLEAN DEFAULT FALSE,
    is_approver BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_is_sv ON users(is_sv);
CREATE INDEX idx_users_is_approver ON users(is_approver);
```

#### Existing Articles テーブル

```sql
CREATE TABLE existing_articles (
    id SERIAL PRIMARY KEY,
    article_id VARCHAR(255) UNIQUE NOT NULL,
    article_number VARCHAR(255) NOT NULL,
    approval_group VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_existing_articles_article_id ON existing_articles(article_id);
CREATE INDEX idx_existing_articles_approval_group ON existing_articles(approval_group);
```

#### Revision Proposals テーブル

```sql
CREATE TABLE revision_proposals (
    id SERIAL PRIMARY KEY,
    revision_id UUID UNIQUE DEFAULT uuid_generate_v4(),
    target_article_id VARCHAR(255) NOT NULL REFERENCES existing_articles(article_id),
    proposer_id INTEGER NOT NULL REFERENCES users(id),
    reason TEXT NOT NULL,
    
    -- 修正内容（修正前後データ）
    before_title TEXT,
    after_title TEXT,
    before_info_category VARCHAR(255),
    after_info_category VARCHAR(255),
    before_keywords TEXT,
    after_keywords TEXT,
    before_importance BOOLEAN,
    after_importance BOOLEAN,
    before_publish_start TIMESTAMP,
    after_publish_start TIMESTAMP,
    before_publish_end TIMESTAMP,
    after_publish_end TIMESTAMP,
    before_target VARCHAR(255),
    after_target VARCHAR(255),
    before_question TEXT,
    after_question TEXT,
    before_answer TEXT,
    after_answer TEXT,
    before_additional_comment TEXT,
    after_additional_comment TEXT,
    
    status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    approver_id INTEGER REFERENCES users(id),
    processed_at TIMESTAMP,
    comments TEXT,
    review_deadline TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_revision_proposals_target_article_id ON revision_proposals(target_article_id);
CREATE INDEX idx_revision_proposals_proposer_id ON revision_proposals(proposer_id);
CREATE INDEX idx_revision_proposals_status ON revision_proposals(status);
CREATE INDEX idx_revision_proposals_approver_id ON revision_proposals(approver_id);
CREATE INDEX idx_revision_proposals_review_deadline ON revision_proposals(review_deadline);
```

#### Revision Comments テーブル

```sql
CREATE TABLE revision_comments (
    id SERIAL PRIMARY KEY,
    revision_id UUID NOT NULL REFERENCES revision_proposals(revision_id),
    user_id INTEGER NOT NULL REFERENCES users(id),
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_revision_comments_revision_id ON revision_comments(revision_id);
CREATE INDEX idx_revision_comments_user_id ON revision_comments(user_id);
```

#### Approval History テーブル

```sql
CREATE TABLE approval_history (
    id SERIAL PRIMARY KEY,
    revision_id UUID NOT NULL REFERENCES revision_proposals(revision_id),
    approver_id INTEGER NOT NULL REFERENCES users(id),
    action VARCHAR(20) NOT NULL CHECK (action IN ('approved', 'rejected')),
    comment TEXT,
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_approval_history_revision_id ON approval_history(revision_id);
CREATE INDEX idx_approval_history_approver_id ON approval_history(approver_id);
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
    from app.models.revision_proposal import RevisionProposal

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sweet_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ctstage_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_sv: Mapped[bool] = mapped_column(Boolean, default=False)
    is_approver: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # リレーションシップ
    proposed_revisions: Mapped[List["RevisionProposal"]] = relationship(
        "RevisionProposal", 
        foreign_keys="RevisionProposal.proposer_id",
        back_populates="proposer"
    )
    approved_revisions: Mapped[List["RevisionProposal"]] = relationship(
        "RevisionProposal", 
        foreign_keys="RevisionProposal.approver_id",
        back_populates="approver"
    )

# app/models/existing_article.py
from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base

class ExistingArticle(Base):
    __tablename__ = "existing_articles"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    article_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    article_number: Mapped[str] = mapped_column(String(255))
    approval_group: Mapped[str] = mapped_column(String(255), index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

# app/models/revision_proposal.py
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.revision_comment import RevisionComment

class RevisionProposal(Base):
    __tablename__ = "revision_proposals"
    
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    revision_id: Mapped[str] = mapped_column(UUID, unique=True, index=True)
    target_article_id: Mapped[str] = mapped_column(String(255), ForeignKey("existing_articles.article_id"))
    proposer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(Text)
    
    # 修正内容（修正前後データ）
    before_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    after_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    before_info_category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    after_info_category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    before_keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    after_keywords: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    before_importance: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    after_importance: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    before_publish_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    after_publish_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    before_publish_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    after_publish_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    before_target: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    after_target: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    before_question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    after_question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    before_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    after_answer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    before_additional_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    after_additional_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    approver_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )
    
    # リレーションシップ
    proposer: Mapped["User"] = relationship("User", foreign_keys=[proposer_id], back_populates="proposed_revisions")
    approver: Mapped[Optional["User"]] = relationship("User", foreign_keys=[approver_id], back_populates="approved_revisions")
    comments_list: Mapped[List["RevisionComment"]] = relationship("RevisionComment", back_populates="revision")
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
- **403 Forbidden**: 権限不足（承認者権限、SV権限など）
- **404 Not Found**: リソースが見つからない（記事、修正案など）
- **409 Conflict**: 重複エラー、競合状態（同時修正案提出など）
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
    "error_code": "REVISION_APPROVAL_FORBIDDEN",
    "message": "この修正案の承認権限がありません",
    "details": {
        "revision_id": "550e8400-e29b-41d4-a716-446655440000",
        "required_role": "approver",
        "user_role": "user"
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
    "id": 1,
    "username": "johndoe",
    "email": "user@example.com",
    "full_name": "John Doe",
    "is_active": true,
    "is_approver": false,
    "created_at": "2024-01-01T00:00:00Z"
}

POST /auth/login
Content-Type: application/x-www-form-urlencoded
username=johndoe&password=secure123

Response:
{
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "bearer",
    "user_id": 1,
    "expires_in": 1800
}
```

- **JWT認証**:
  - アクセストークン有効期限: 30分
  - リフレッシュトークン有効期限: 7日
  - トークンはRedisで管理（ブラックリスト方式）

- **権限レベル**:
  - ゲスト: 既存記事閲覧のみ
  - 一般ユーザー: 修正案提出、自身の修正案編集
  - 承認者: 担当範囲の修正案承認・却下
  - スーパーバイザー(SV): 修正案承認、ユーザー管理の一部
  - 管理者: 全ユーザー・修正案の管理

### 7.2 データ保護

- パスワードはbcryptでハッシュ化（コストファクター: 12）
- SQLインジェクション対策: SQLAlchemyのパラメータバインディング使用
- XSS対策: pydanticによる入力値検証
- CORS設定: 許可されたオリジンのみ
- HTTPS通信の強制
- 機密情報はログに出力しない
- 修正案の承認権限厳格化

## 8. テスト戦略

### 8.1 単体テスト

- カバレッジ目標: 85%以上
- テストフレームワーク: pytest, pytest-asyncio
- モックツール: pytest-mock
- テスト対象:
  - サービス層のビジネスロジック
  - 修正案承認ワークフロー
  - バリデーション
  - 認証・認可

### 8.2 統合テスト

- APIエンドポイントのE2Eテスト
- 修正案提出から承認までの完全なワークフローテスト
- 権限管理の統合テスト
- テスト用データベース（SQLite）使用

## 9. パフォーマンス最適化

### 9.1 想定される負荷

- 同時接続数: 100ユーザー
- 1秒あたりのリクエスト数: 50RPS
- 95パーセンタイル応答時間: 500ms以下

### 9.2 最適化方針

- **データベース**:
  - 適切なインデックス設定（修正案ステータス、承認者ID等）
  - N+1問題の回避（eager loading）
  - コネクションプーリング（最小: 5, 最大: 20）

- **キャッシュ戦略**:
  - 既存記事一覧: 10分間キャッシュ
  - 修正案一覧: 5分間キャッシュ
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
# systemdサービスファイル: /etc/systemd/system/revision-api.service
[Unit]
Description=Revision Proposal Management API
After=network.target postgresql.service redis.service

[Service]
Type=exec
User=apiuser
Group=apiuser
WorkingDirectory=/opt/revision-api
Environment=PATH=/opt/revision-api/venv/bin
ExecStart=/opt/revision-api/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
EnvironmentFile=/opt/revision-api/.env

[Install]
WantedBy=multi-user.target

# サービスの有効化と起動
sudo systemctl enable revision-api
sudo systemctl start revision-api
```

### 10.2 設定管理

```python
# app/config.py
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    # アプリケーション設定
    app_name: str = "Revision Proposal Management API"
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
    log_file: str = "/var/log/revision-api/app.log"
    
    class Config:
        env_file = ".env"
        
settings = Settings()
```

### 10.3 環境変数設定例

```bash
# .env
# アプリケーション設定
APP_NAME=Revision Proposal Management API
DEBUG=false
HOST=0.0.0.0
PORT=8000
# Python 3.12+を使用することを明示
PYTHON_VERSION_MIN=3.12
PYTHON_VERSION_MAX=3.13

# データベース設定
DATABASE_URL=postgresql+asyncpg://revisionuser:revisionpass@localhost/revisiondb

# Redis設定
REDIS_URL=redis://localhost:6379

# JWT設定
SECRET_KEY=your-super-secret-key-for-revision-system
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# CORS設定
ALLOWED_ORIGINS=http://localhost:3000,https://revision.yourdomain.com

# ログ設定
LOG_LEVEL=INFO
LOG_FILE=/var/log/revision-api/app.log
```

## 11. 実装上の注意事項

### 11.1 Python 3.12の活用
- **型パラメータ構文**: `class Service[T]` や `def function[T](param: T) -> T` を積極活用
- **Union構文**: `Optional[T]` より `T | None` を優先使用
- **改善されたエラーメッセージ**: デバッグ時を意識したコード記述
- **性能向上**: Python 3.12の内部最適化の恩恵を受ける
- **`from __future__ import annotations`**: 前方参照の問題を解決

### 11.2 修正案管理システム固有の注意事項
- 修正案の競合状態を適切に処理する（楽観的ロック）
- 修正前後データの一貫性を保証する
- 承認権限の厳格なチェック（記事の承認グループとユーザー権限の照合）
- 差分表示機能のパフォーマンス最適化
- 修正案の履歴管理と監査ログの確実な記録
- レビュー期限の自動管理と通知機能
- データベーストランザクションは適切にスコープを管理する
- 修正案提出時の重複チェック機能

### 11.3 一般的な注意事項
- 非同期処理を活用してパフォーマンスを最適化する
- エラーハンドリングは統一的に行い、適切なHTTPステータスコードを返す
- ログは構造化ログ（JSON形式）で出力し、分析しやすくする
- 循環参照を避けるため、依存性注入パターンを使用する
- 型ヒントを積極的に使用し、IDEのサポートを最大化する
- docstringを書いて、自動的にAPIドキュメントを生成する
- 設定値はハードコーディングせず、環境変数から取得する
- テストデータは本番データと明確に分離する
- マイグレーションは必ずレビューしてから実行する
- モノリシック構成でシンプルに保ち、必要に応じてスケールアップを検討する
- Redisキャッシュはaioredisを使用して非同期対応する

### 11.4 バージョン管理とライブラリ対応
- **Pythonバージョン**: 3.12.x を基準、本番環境での統一必須
- **主要ライブラリ**: FastAPI 0.115.12, SQLAlchemy 2.0.40, Pydantic 2.11.3 等
- **全ライブラリ**: Python 3.12 対応確認済み ✓
- **注意事項**: Python 3.13 リリース時の互換性チェック

### 11.5 プロジェクト構造

```
revision_api_project/
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
│   │       ├── articles.py  # 既存記事エンドポイント
│   │       ├── revisions.py # 修正案エンドポイント
│   │       └── approvals.py # 承認ワークフローエンドポイント
│   ├── models/              # SQLAlchemyモデル
│   │   ├── __init__.py
│   │   ├── base.py          # Baseモデル
│   │   ├── user.py          # Userモデル
│   │   ├── existing_article.py # ExistingArticleモデル
│   │   ├── revision_proposal.py # RevisionProposalモデル
│   │   └── revision_comment.py # RevisionCommentモデル
│   ├── schemas/             # Pydanticスキーマ
│   │   ├── __init__.py
│   │   ├── user.py          # ユーザースキーマ
│   │   ├── article.py       # 記事スキーマ
│   │   ├── revision.py      # 修正案スキーマ
│   │   └── auth.py          # 認証スキーマ
│   ├── services/            # ビジネスロジック
│   │   ├── __init__.py
│   │   ├── auth_service.py  # 認証サービス
│   │   ├── user_service.py  # ユーザーサービス
│   │   ├── article_service.py # 記事参照サービス
│   │   ├── revision_service.py # 修正案サービス
│   │   ├── approval_service.py # 承認サービス
│   │   └── cache_service.py   # キャッシュサービス
│   └── repositories/        # データアクセス
│       ├── __init__.py
│       ├── base.py          # ベースリポジトリ
│       ├── user_repository.py
│       ├── article_repository.py
│       ├── revision_repository.py
│       └── approval_repository.py
├── tests/                   # テストコード
│   ├── __init__.py
│   ├── conftest.py          # pytest設定
│   ├── test_auth.py         # 認証テスト
│   ├── test_users.py        # ユーザーテスト
│   ├── test_revisions.py    # 修正案テスト
│   └── test_approvals.py    # 承認ワークフローテスト
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