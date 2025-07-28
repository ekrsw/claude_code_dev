# SQLAlchemy モデル定義書 - 既存ナレッジ修正案管理システム

## 1. 基礎設定とEnum定義

### 1.1 基底クラスと共通設定

```python
# app/models/base.py
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from sqlalchemy import (
    Boolean, DateTime, Integer, String, Text, UUID as SQLUuid, func,
    CheckConstraint, Index, ForeignKey, ARRAY
)
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncSession


class Base(DeclarativeBase):
    """SQLAlchemy基底クラス"""
    
    # 共通型エイリアス
    type_annotation_map = {
        datetime: DateTime(timezone=True),
        UUID: SQLUuid(as_uuid=True),
    }


# 共通Mixinクラス
class TimestampMixin:
    """作成日時・更新日時のMixin"""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(),
        nullable=False,
        doc="作成日時"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        doc="更新日時"
    )


class UUIDMixin:
    """UUID主キーのMixin"""
    id: Mapped[UUID] = mapped_column(
        SQLUuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
        doc="UUID主キー"
    )
```

### 1.2 Enum定義

```python
# app/models/enums.py
from enum import Enum


class UserRole(str, Enum):
    """ユーザーロール"""
    GENERAL = "general"
    SUPERVISOR = "supervisor"
    APPROVER = "approver"
    ADMIN = "admin"


class RevisionStatus(str, Enum):
    """修正案ステータス"""
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    REVISION_REQUESTED = "revision_requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ArticleTarget(str, Enum):
    """記事対象者分類"""
    INTERNAL = "社内向け"
    EXTERNAL = "社外向け"
    EXCLUDED = "対象外"


class CommentType(str, Enum):
    """コメント種別"""
    FEEDBACK = "feedback"
    QUESTION = "question"
    ANSWER = "answer"
    APPROVAL = "approval"
    REJECTION = "rejection"


class InstructionPriority(str, Enum):
    """修正指示優先度"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ApprovalAction(str, Enum):
    """承認アクション"""
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"
    WITHDRAWN = "withdrawn"
```

## 2. ユーザー関連モデル

### 2.1 Userモデル

```python
# app/models/user.py
from typing import Optional, List
from sqlalchemy import String, Boolean, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin, UUIDMixin
from .enums import UserRole


class User(Base, UUIDMixin, TimestampMixin):
    """ユーザーモデル"""
    
    __tablename__ = "users"
    
    # 基本情報
    username: Mapped[str] = mapped_column(
        String(100), 
        unique=True, 
        nullable=False,
        doc="ユーザー名"
    )
    email: Mapped[str] = mapped_column(
        String(255), 
        unique=True, 
        nullable=False,
        doc="メールアドレス"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255), 
        nullable=False,
        doc="パスワードハッシュ"
    )
    
    # 権限・ロール
    role: Mapped[UserRole] = mapped_column(
        String(20),
        default=UserRole.GENERAL,
        nullable=False,
        doc="ユーザーロール"
    )
    is_sv: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="スーパーバイザー権限フラグ"
    )
    
    # 外部システム連携用（将来拡張）
    sweet_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Sweet連携用ユーザー名（将来拡張用）"
    )
    ctstage_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Ctstage連携用ユーザー名（将来拡張用）"
    )
    
    # アカウント状態
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="アカウント有効フラグ"
    )
    
    # リレーションシップ
    proposed_revisions: Mapped[List["Revision"]] = relationship(
        "Revision",
        foreign_keys="Revision.proposer_id",
        back_populates="proposer",
        lazy="selectin"
    )
    approved_revisions: Mapped[List["Revision"]] = relationship(
        "Revision",
        foreign_keys="Revision.approver_id", 
        back_populates="approver",
        lazy="selectin"
    )
    edit_histories: Mapped[List["RevisionEditHistory"]] = relationship(
        "RevisionEditHistory",
        back_populates="editor",
        lazy="selectin"
    )
    instructions: Mapped[List["RevisionInstruction"]] = relationship(
        "RevisionInstruction",
        back_populates="instructor",
        lazy="selectin"
    )
    comments: Mapped[List["RevisionComment"]] = relationship(
        "RevisionComment",
        back_populates="commenter",
        lazy="selectin"
    )
    approval_histories: Mapped[List["ApprovalHistory"]] = relationship(
        "ApprovalHistory",
        back_populates="actor",
        lazy="selectin"
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification",
        back_populates="recipient",
        lazy="selectin"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        lazy="selectin"
    )
    
    # 制約
    __table_args__ = (
        CheckConstraint(
            "role IN ('general', 'supervisor', 'approver', 'admin')",
            name="chk_users_role"
        ),
        CheckConstraint(
            "char_length(username) >= 3",
            name="chk_users_username_length"
        ),
        CheckConstraint(
            "email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$'",
            name="chk_users_email_format"
        ),
        Index("idx_users_role", "role"),
        Index("idx_users_is_sv", "is_sv"),
        Index("idx_users_is_active", "is_active"),
        Index("idx_users_created_at", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username='{self.username}', role='{self.role}')>"
    
    @property
    def is_admin(self) -> bool:
        """管理者かどうか"""
        return self.role == UserRole.ADMIN
    
    @property
    def is_supervisor(self) -> bool:
        """スーパーバイザーかどうか"""
        return self.role == UserRole.SUPERVISOR or self.is_sv
    
    @property
    def is_approver(self) -> bool:
        """承認者かどうか"""
        return self.role == UserRole.APPROVER
    
    @property
    def can_approve_revisions(self) -> bool:
        """修正案を承認できるかどうか"""
        return self.role in [UserRole.ADMIN, UserRole.SUPERVISOR, UserRole.APPROVER] or self.is_sv
```

## 3. 記事・カテゴリモデル

### 3.1 InfoCategoryモデル

```python
# app/models/info_category.py
from typing import List
from sqlalchemy import String, Integer, Boolean, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin


class InfoCategory(Base, TimestampMixin):
    """情報カテゴリマスターモデル"""
    
    __tablename__ = "info_categories"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        doc="カテゴリID"
    )
    code: Mapped[str] = mapped_column(
        String(2),
        unique=True,
        nullable=False,
        doc="カテゴリコード（2桁数字）"
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="表示名"
    )
    display_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="表示順序"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="有効フラグ"
    )
    
    # リレーションシップ
    articles: Mapped[List["Article"]] = relationship(
        "Article",
        back_populates="info_category",
        lazy="selectin"
    )
    before_revisions: Mapped[List["Revision"]] = relationship(
        "Revision",
        foreign_keys="Revision.before_info_category",
        back_populates="before_category",
        lazy="selectin"
    )
    after_revisions: Mapped[List["Revision"]] = relationship(
        "Revision",
        foreign_keys="Revision.after_info_category",
        back_populates="after_category",
        lazy="selectin"
    )
    
    # 制約
    __table_args__ = (
        CheckConstraint(
            "code ~ '^[0-9]{2}$'",
            name="chk_info_categories_code_format"
        ),
        CheckConstraint(
            "display_order > 0",
            name="chk_info_categories_display_order_positive"
        ),
        Index("idx_info_categories_is_active", "is_active"),
        Index("idx_info_categories_display_order", "display_order"),
    )
    
    def __repr__(self) -> str:
        return f"<InfoCategory(code='{self.code}', name='{self.display_name}')>"


# 初期データ定義
INITIAL_CATEGORIES = [
    ("01", "_会計・財務", 1),
    ("02", "_起動トラブル", 2),
    ("03", "_給与・年末調整", 3),
    ("04", "_減価・ﾘｰｽ/資産管理", 4),
    ("05", "_公益・医療会計", 5),
    ("06", "_工事・原価", 6),
    ("07", "_債権・債務", 7),
    ("08", "_事務所管理", 8),
    ("09", "_人事", 9),
    ("10", "_税務関連", 10),
    ("11", "_電子申告", 11),
    ("12", "_販売", 12),
    ("13", "EdgeTracker", 13),
    ("14", "MJS-Connect関連", 14),
    ("15", "インストール・MOU", 15),
    ("16", "かんたん！シリーズ", 16),
    ("17", "その他（システム以外）", 17),
    ("18", "その他MJSシステム", 18),
    ("19", "その他システム（共通）", 19),
    ("20", "ハード関連(HHD)", 20),
    ("21", "ハード関連（ソフトフェア）", 21),
    ("22", "マイナンバー", 22),
    ("23", "ワークフロー", 23),
    ("24", "一時受付用", 24),
    ("25", "運用ルール", 25),
    ("26", "顧客情報", 26),
]
```

### 3.2 Articleモデル

```python
# app/models/article.py
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, Boolean, DateTime, CheckConstraint, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin
from .enums import ArticleTarget


class Article(Base, TimestampMixin):
    """既存記事モデル（参照専用）"""
    
    __tablename__ = "articles"
    
    id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
        doc="記事ID"
    )
    article_number: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="記事番号"
    )
    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="タイトル"
    )
    content: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="本文"
    )
    
    # カテゴリ・分類
    info_category_code: Mapped[Optional[str]] = mapped_column(
        String(2),
        ForeignKey("info_categories.code"),
        nullable=True,
        doc="情報カテゴリコード"
    )
    keywords: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="キーワード"
    )
    importance: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="重要度フラグ"
    )
    target: Mapped[ArticleTarget] = mapped_column(
        String(20),
        default=ArticleTarget.INTERNAL,
        nullable=False,
        doc="対象者分類"
    )
    
    # Q&A
    question: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="質問"
    )
    answer: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="回答"
    )
    additional_comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="追加コメント"
    )
    
    # 公開期限
    publish_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="公開開始日時"
    )
    publish_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="公開終了日時"
    )
    
    # その他
    approval_group: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="承認グループ"
    )
    
    # リレーションシップ
    info_category: Mapped[Optional["InfoCategory"]] = relationship(
        "InfoCategory",
        back_populates="articles",
        lazy="selectin"
    )
    revisions: Mapped[List["Revision"]] = relationship(
        "Revision",
        back_populates="target_article",
        lazy="selectin"
    )
    
    # 制約
    __table_args__ = (
        CheckConstraint(
            "target IN ('社内', '社外', '対象外')",
            name="chk_articles_target"
        ),
        CheckConstraint(
            "char_length(trim(title)) > 0",
            name="chk_articles_title_not_empty"
        ),
        Index("idx_articles_info_category", "info_category_code"),
        Index("idx_articles_importance", "importance"),
        Index("idx_articles_target", "target"),
        Index("idx_articles_article_number", "article_number"),
        Index("idx_articles_created_at", "created_at"),
        # 全文検索用インデックス（PostgreSQL GIN）
        Index(
            "idx_articles_title_gin",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"}
        ),
        Index(
            "idx_articles_content_gin", 
            "content",
            postgresql_using="gin",
            postgresql_ops={"content": "gin_trgm_ops"}
        ),
        Index(
            "idx_articles_keywords_gin",
            "keywords", 
            postgresql_using="gin",
            postgresql_ops={"keywords": "gin_trgm_ops"}
        ),
    )
    
    def __repr__(self) -> str:
        return f"<Article(id='{self.id}', title='{self.title[:50]}...')>"
    
    @property
    def is_published(self) -> bool:
        """現在公開中かどうか"""
        now = datetime.now()
        if self.publish_start and now < self.publish_start:
            return False
        if self.publish_end and now > self.publish_end:
            return False
        return True
```

## 4. 修正案関連モデル

### 4.1 Revisionモデル

```python
# app/models/revision.py
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String, Text, Boolean, DateTime, Integer, ForeignKey, 
    CheckConstraint, Index
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, TimestampMixin, UUIDMixin
from .enums import RevisionStatus, ArticleTarget


class Revision(Base, UUIDMixin, TimestampMixin):
    """修正案モデル"""
    
    __tablename__ = "revisions"
    
    # 基本情報
    target_article_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("articles.id"),
        nullable=False,
        doc="対象記事ID"
    )
    proposer_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        doc="提案者ID"
    )
    status: Mapped[RevisionStatus] = mapped_column(
        String(20),
        default=RevisionStatus.DRAFT,
        nullable=False,
        doc="ステータス"
    )
    
    # 修正前フィールド（nullable）
    before_title: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="修正前タイトル"
    )
    before_info_category: Mapped[Optional[str]] = mapped_column(
        String(2), ForeignKey("info_categories.code"), nullable=True, 
        doc="修正前情報カテゴリ"
    )
    before_keywords: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="修正前キーワード"
    )
    before_importance: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, doc="修正前重要度"
    )
    before_publish_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="修正前公開開始日時"
    )
    before_publish_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="修正前公開終了日時"
    )
    before_target: Mapped[Optional[ArticleTarget]] = mapped_column(
        String(20), nullable=True, doc="修正前対象者分類"
    )
    before_question: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="修正前質問"
    )
    before_answer: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="修正前回答"
    )
    before_additional_comment: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="修正前追加コメント"
    )
    
    # 修正後フィールド（nullable）
    after_title: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="修正後タイトル"
    )
    after_info_category: Mapped[Optional[str]] = mapped_column(
        String(2), ForeignKey("info_categories.code"), nullable=True,
        doc="修正後情報カテゴリ"
    )
    after_keywords: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="修正後キーワード"
    )
    after_importance: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, doc="修正後重要度"
    )
    after_publish_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="修正後公開開始日時"
    )
    after_publish_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="修正後公開終了日時"
    )
    after_target: Mapped[Optional[ArticleTarget]] = mapped_column(
        String(20), nullable=True, doc="修正後対象者分類"
    )
    after_question: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="修正後質問"
    )
    after_answer: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="修正後回答"
    )
    after_additional_comment: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="修正後追加コメント"
    )
    
    # メタデータ
    reason: Mapped[str] = mapped_column(
        Text, nullable=False, doc="修正理由"
    )
    approver_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"), nullable=True, doc="承認者ID"
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="承認日時"
    )
    approval_comment: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, doc="承認コメント"
    )
    
    # システムフィールド
    version: Mapped[int] = mapped_column(
        Integer, default=1, nullable=False, doc="バージョン（楽観的ロック用）"
    )
    
    # リレーションシップ
    target_article: Mapped["Article"] = relationship(
        "Article", back_populates="revisions", lazy="selectin"
    )
    proposer: Mapped["User"] = relationship(
        "User", foreign_keys=[proposer_id], back_populates="proposed_revisions",
        lazy="selectin"
    )
    approver: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[approver_id], back_populates="approved_revisions",
        lazy="selectin"
    )
    before_category: Mapped[Optional["InfoCategory"]] = relationship(
        "InfoCategory", foreign_keys=[before_info_category],
        back_populates="before_revisions", lazy="selectin"
    )
    after_category: Mapped[Optional["InfoCategory"]] = relationship(
        "InfoCategory", foreign_keys=[after_info_category],
        back_populates="after_revisions", lazy="selectin"
    )
    
    edit_histories: Mapped[List["RevisionEditHistory"]] = relationship(
        "RevisionEditHistory", back_populates="revision",
        cascade="all, delete-orphan", lazy="selectin"
    )
    instructions: Mapped[List["RevisionInstruction"]] = relationship(
        "RevisionInstruction", back_populates="revision",
        cascade="all, delete-orphan", lazy="selectin"
    )
    comments: Mapped[List["RevisionComment"]] = relationship(
        "RevisionComment", back_populates="revision",
        cascade="all, delete-orphan", lazy="selectin"
    )
    approval_histories: Mapped[List["ApprovalHistory"]] = relationship(
        "ApprovalHistory", back_populates="revision",
        cascade="all, delete-orphan", lazy="selectin"
    )
    
    # 制約
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'under_review', 'revision_requested', 'approved', 'rejected', 'withdrawn')",
            name="chk_revisions_status"
        ),
        CheckConstraint(
            "before_target IS NULL OR before_target IN ('社内', '社外', '対象外')",
            name="chk_revisions_before_target"
        ),
        CheckConstraint(
            "after_target IS NULL OR after_target IN ('社内', '社外', '対象外')",
            name="chk_revisions_after_target"
        ),
        CheckConstraint(
            "char_length(trim(reason)) >= 10",
            name="chk_revisions_reason_not_empty"
        ),
        CheckConstraint(
            """
            (status = 'approved' AND approver_id IS NOT NULL AND approved_at IS NOT NULL) OR
            (status != 'approved' AND (approver_id IS NULL OR approved_at IS NULL))
            """,
            name="chk_revisions_approval_consistency"
        ),
        Index("idx_revisions_target_article", "target_article_id"),
        Index("idx_revisions_proposer", "proposer_id"),
        Index("idx_revisions_approver", "approver_id"),
        Index("idx_revisions_status", "status"),
        Index("idx_revisions_created_at", "created_at"),
        Index("idx_revisions_approved_at", "approved_at"),
        Index("idx_revisions_status_proposer", "status", "proposer_id"),
        Index("idx_revisions_status_created", "status", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<Revision(id={self.id}, article='{self.target_article_id}', status='{self.status}')>"
    
    @property
    def is_editable(self) -> bool:
        """編集可能かどうか"""
        return self.status in [RevisionStatus.DRAFT, RevisionStatus.REVISION_REQUESTED]
    
    @property
    def is_pending(self) -> bool:
        """承認待ちかどうか"""
        return self.status == RevisionStatus.UNDER_REVIEW
    
    @property
    def is_approved(self) -> bool:
        """承認済みかどうか"""
        return self.status == RevisionStatus.APPROVED
    
    @property
    def is_rejected(self) -> bool:
        """却下済みかどうか"""
        return self.status == RevisionStatus.REJECTED
    
    def get_changed_fields(self) -> List[str]:
        """変更されたフィールド一覧を取得"""
        changed_fields = []
        field_mappings = [
            ("title", self.after_title),
            ("info_category", self.after_info_category),
            ("keywords", self.after_keywords),
            ("importance", self.after_importance),
            ("publish_start", self.after_publish_start),
            ("publish_end", self.after_publish_end),
            ("target", self.after_target),
            ("question", self.after_question),
            ("answer", self.after_answer),
            ("additional_comment", self.after_additional_comment),
        ]
        
        for field_name, after_value in field_mappings:
            if after_value is not None:
                changed_fields.append(field_name)
        
        return changed_fields
    
    def get_diff_summary(self) -> Dict[str, Dict[str, Any]]:
        """差分サマリーを取得"""
        diff = {}
        field_mappings = [
            ("title", self.before_title, self.after_title),
            ("info_category", self.before_info_category, self.after_info_category),
            ("keywords", self.before_keywords, self.after_keywords),
            ("importance", self.before_importance, self.after_importance),
            ("publish_start", self.before_publish_start, self.after_publish_start),
            ("publish_end", self.before_publish_end, self.after_publish_end),
            ("target", self.before_target, self.after_target),
            ("question", self.before_question, self.after_question),
            ("answer", self.before_answer, self.after_answer),
            ("additional_comment", self.before_additional_comment, self.after_additional_comment),
        ]
        
        for field_name, before_value, after_value in field_mappings:
            if after_value is not None:
                diff[field_name] = {
                    "before": before_value,
                    "after": after_value
                }
        
        return diff
```

## 5. ワークフロー・履歴モデル

### 5.1 RevisionEditHistoryモデル

```python
# app/models/revision_edit_history.py
from datetime import datetime
from typing import Dict, Any
from sqlalchemy import String, DateTime, Integer, Text, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, UUIDMixin
from .enums import UserRole


class RevisionEditHistory(Base, UUIDMixin):
    """修正案編集履歴モデル"""
    
    __tablename__ = "revision_edit_histories"
    
    revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("revisions.id", ondelete="CASCADE"),
        nullable=False,
        doc="修正案ID"
    )
    editor_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        doc="編集者ID"
    )
    editor_role: Mapped[UserRole] = mapped_column(
        String(20),
        nullable=False,
        doc="編集者ロール"
    )
    edited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="編集日時"
    )
    changes: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        doc="変更内容の詳細（JSON形式）"
    )
    comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="編集理由・コメント"
    )
    version_before: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="編集前バージョン"
    )
    version_after: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        doc="編集後バージョン"
    )
    
    # リレーションシップ
    revision: Mapped["Revision"] = relationship(
        "Revision", back_populates="edit_histories", lazy="selectin"
    )
    editor: Mapped["User"] = relationship(
        "User", back_populates="edit_histories", lazy="selectin"
    )
    
    # 制約
    __table_args__ = (
        CheckConstraint(
            "editor_role IN ('general', 'supervisor', 'approver', 'admin')",
            name="chk_revision_edit_histories_editor_role"
        ),
        CheckConstraint(
            "version_after = version_before + 1",
            name="chk_revision_edit_histories_version_increment"
        ),
        Index("idx_revision_edit_histories_revision", "revision_id"),
        Index("idx_revision_edit_histories_editor", "editor_id"),
        Index("idx_revision_edit_histories_edited_at", "edited_at"),
        Index(
            "idx_revision_edit_histories_changes_gin",
            "changes",
            postgresql_using="gin"
        ),
    )
    
    def __repr__(self) -> str:
        return f"<RevisionEditHistory(id={self.id}, revision={self.revision_id}, editor={self.editor_id})>"
```

### 5.2 RevisionInstructionモデル

```python
# app/models/revision_instruction.py
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String, Text, DateTime, ForeignKey, CheckConstraint, Index, ARRAY
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, UUIDMixin
from .enums import InstructionPriority


class RevisionInstruction(Base, UUIDMixin):
    """修正指示モデル"""
    
    __tablename__ = "revision_instructions"
    
    revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("revisions.id", ondelete="CASCADE"),
        nullable=False,
        doc="修正案ID"
    )
    instructor_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        doc="指示者ID"
    )
    instruction_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="修正指示内容"
    )
    required_fields: Mapped[Optional[List[str]]] = mapped_column(
        ARRAY(String),
        nullable=True,
        doc="修正が必要なフィールドのリスト"
    )
    priority: Mapped[InstructionPriority] = mapped_column(
        String(10),
        default=InstructionPriority.NORMAL,
        nullable=False,
        doc="優先度"
    )
    due_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="期限日時"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="作成日時"
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="解決日時"
    )
    resolution_comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="解決コメント"
    )
    
    # リレーションシップ
    revision: Mapped["Revision"] = relationship(
        "Revision", back_populates="instructions", lazy="selectin"
    )
    instructor: Mapped["User"] = relationship(
        "User", back_populates="instructions", lazy="selectin"
    )
    
    # 制約
    __table_args__ = (
        CheckConstraint(
            "priority IN ('low', 'normal', 'high', 'urgent')",
            name="chk_revision_instructions_priority"
        ),
        CheckConstraint(
            "char_length(trim(instruction_text)) > 0",
            name="chk_revision_instructions_text_not_empty"
        ),
        CheckConstraint(
            "due_date IS NULL OR due_date > created_at",
            name="chk_revision_instructions_due_date_future"
        ),
        Index("idx_revision_instructions_revision", "revision_id"),
        Index("idx_revision_instructions_instructor", "instructor_id"),
        Index("idx_revision_instructions_priority", "priority"),
        Index("idx_revision_instructions_due_date", "due_date"),
        Index("idx_revision_instructions_resolved_at", "resolved_at"),
    )
    
    def __repr__(self) -> str:
        return f"<RevisionInstruction(id={self.id}, revision={self.revision_id}, priority='{self.priority}')>"
    
    @property
    def is_resolved(self) -> bool:
        """解決済みかどうか"""
        return self.resolved_at is not None
    
    @property
    def is_overdue(self) -> bool:
        """期限切れかどうか"""
        if self.due_date is None or self.is_resolved:
            return False
        return datetime.now() > self.due_date
```

### 5.3 RevisionCommentモデル

```python
# app/models/revision_comment.py
from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, UUIDMixin, TimestampMixin
from .enums import CommentType


class RevisionComment(Base, UUIDMixin, TimestampMixin):
    """修正案コメント・フィードバックモデル"""
    
    __tablename__ = "revision_comments"
    
    revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("revisions.id", ondelete="CASCADE"),
        nullable=False,
        doc="修正案ID"
    )
    commenter_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        doc="コメント投稿者ID"
    )
    comment_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="コメント内容"
    )
    comment_type: Mapped[CommentType] = mapped_column(
        String(20),
        default=CommentType.FEEDBACK,
        nullable=False,
        doc="コメント種別"
    )
    parent_comment_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("revision_comments.id"),
        nullable=True,
        doc="親コメントID（スレッド機能用）"
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="削除フラグ"
    )
    
    # リレーションシップ
    revision: Mapped["Revision"] = relationship(
        "Revision", back_populates="comments", lazy="selectin"
    )
    commenter: Mapped["User"] = relationship(
        "User", back_populates="comments", lazy="selectin"
    )
    parent_comment: Mapped[Optional["RevisionComment"]] = relationship(
        "RevisionComment", remote_side="RevisionComment.id", lazy="selectin"
    )
    child_comments: Mapped[List["RevisionComment"]] = relationship(
        "RevisionComment", lazy="selectin"
    )
    
    # 制約
    __table_args__ = (
        CheckConstraint(
            "comment_type IN ('feedback', 'question', 'answer', 'approval', 'rejection')",
            name="chk_revision_comments_type"
        ),
        CheckConstraint(
            "char_length(trim(comment_text)) > 0",
            name="chk_revision_comments_text_not_empty"
        ),
        Index("idx_revision_comments_revision", "revision_id"),
        Index("idx_revision_comments_commenter", "commenter_id"),
        Index("idx_revision_comments_parent", "parent_comment_id"),
        Index("idx_revision_comments_created_at", "created_at"),
        Index("idx_revision_comments_is_deleted", "is_deleted"),
    )
    
    def __repr__(self) -> str:
        return f"<RevisionComment(id={self.id}, revision={self.revision_id}, type='{self.comment_type}')>"
    
    @property
    def is_thread_root(self) -> bool:
        """スレッドのルートコメントかどうか"""
        return self.parent_comment_id is None
```

### 5.4 ApprovalHistoryモデル

```python
# app/models/approval_history.py
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import String, Text, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, UUIDMixin
from .enums import ApprovalAction


class ApprovalHistory(Base, UUIDMixin):
    """承認履歴モデル"""
    
    __tablename__ = "approval_histories"
    
    revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("revisions.id", ondelete="CASCADE"),
        nullable=False,
        doc="修正案ID"
    )
    actor_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        doc="実行者ID"
    )
    action: Mapped[ApprovalAction] = mapped_column(
        String(20),
        nullable=False,
        doc="アクション"
    )
    comment: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="コメント"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="実行日時"
    )
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        doc="追加メタデータ"
    )
    
    # リレーションシップ
    revision: Mapped["Revision"] = relationship(
        "Revision", back_populates="approval_histories", lazy="selectin"
    )
    actor: Mapped["User"] = relationship(
        "User", back_populates="approval_histories", lazy="selectin"
    )
    
    # 制約
    __table_args__ = (
        CheckConstraint(
            "action IN ('submitted', 'approved', 'rejected', 'revision_requested', 'withdrawn')",
            name="chk_approval_histories_action"
        ),
        Index("idx_approval_histories_revision", "revision_id"),
        Index("idx_approval_histories_actor", "actor_id"),
        Index("idx_approval_histories_action", "action"),
        Index("idx_approval_histories_created_at", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<ApprovalHistory(id={self.id}, revision={self.revision_id}, action='{self.action}')>"
```

## 6. 通知・監査モデル

### 6.1 Notificationモデル

```python
# app/models/notification.py
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, UUIDMixin


class Notification(Base, UUIDMixin):
    """通知モデル"""
    
    __tablename__ = "notifications"
    
    recipient_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        doc="受信者ID"
    )
    notification_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="通知種別"
    )
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        doc="タイトル"
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="通知内容"
    )
    metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        doc="追加メタデータ"
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        doc="既読フラグ"
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="既読日時"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="作成日時"
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="有効期限"
    )
    
    # リレーションシップ
    recipient: Mapped["User"] = relationship(
        "User", back_populates="notifications", lazy="selectin"
    )
    
    # 制約
    __table_args__ = (
        CheckConstraint(
            """
            (is_read = TRUE AND read_at IS NOT NULL) OR
            (is_read = FALSE AND read_at IS NULL)
            """,
            name="chk_notifications_read_consistency"
        ),
        CheckConstraint(
            "expires_at IS NULL OR expires_at > created_at",
            name="chk_notifications_expires_future"
        ),
        Index("idx_notifications_recipient", "recipient_id"),
        Index("idx_notifications_is_read", "is_read"),
        Index("idx_notifications_created_at", "created_at"),
        Index("idx_notifications_expires_at", "expires_at"),
        Index("idx_notifications_recipient_read", "recipient_id", "is_read"),
    )
    
    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, recipient={self.recipient_id}, type='{self.notification_type}')>"
    
    @property
    def is_expired(self) -> bool:
        """期限切れかどうか"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def mark_as_read(self) -> None:
        """既読にする"""
        self.is_read = True
        self.read_at = datetime.now()
```

### 6.2 AuditLogモデル

```python
# app/models/audit_log.py
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import String, Text, DateTime, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import JSONB, INET
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base, UUIDMixin


class AuditLog(Base, UUIDMixin):
    """監査ログモデル"""
    
    __tablename__ = "audit_logs"
    
    user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        doc="ユーザーID"
    )
    action: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="アクション"
    )
    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        doc="リソースタイプ"
    )
    resource_id: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        doc="リソースID"
    )
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=True,
        doc="詳細情報"
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        INET,
        nullable=True,
        doc="IPアドレス"
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="ユーザーエージェント"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        doc="実行日時"
    )
    
    # リレーションシップ
    user: Mapped[Optional["User"]] = relationship(
        "User", back_populates="audit_logs", lazy="selectin"
    )
    
    # 制約
    __table_args__ = (
        CheckConstraint(
            "char_length(trim(action)) > 0",
            name="chk_audit_logs_action_not_empty"
        ),
        CheckConstraint(
            "char_length(trim(resource_type)) > 0",
            name="chk_audit_logs_resource_type_not_empty"
        ),
        Index("idx_audit_logs_user", "user_id"),
        Index("idx_audit_logs_action", "action"),
        Index("idx_audit_logs_resource_type", "resource_type"),
        Index("idx_audit_logs_resource_id", "resource_id"),
        Index("idx_audit_logs_created_at", "created_at"),
        Index("idx_audit_logs_resource", "resource_type", "resource_id"),
    )
    
    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action='{self.action}', resource='{self.resource_type}:{self.resource_id}')>"
```

## 7. ユーティリティとヘルパー

### 7.1 データベース接続設定

```python
# app/core/database.py
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from .config import settings

# 非同期エンジンの作成
async_engine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=settings.DB_ECHO,
    poolclass=NullPool if settings.ENVIRONMENT == "test" else None,
    pool_pre_ping=True,
    pool_recycle=300,
)

# セッションファクトリーの作成
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """非同期セッションの取得"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """データベース初期化"""
    from .models import Base
    
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """データベース接続の終了"""
    await async_engine.dispose()
```

### 7.2 モデルインポート設定

```python
# app/models/__init__.py
"""SQLAlchemyモデルの統合インポート"""

from .base import Base, TimestampMixin, UUIDMixin
from .enums import (
    UserRole, RevisionStatus, ArticleTarget, CommentType,
    InstructionPriority, ApprovalAction
)

# モデルクラス
from .user import User
from .info_category import InfoCategory, INITIAL_CATEGORIES
from .article import Article
from .revision import Revision
from .revision_edit_history import RevisionEditHistory
from .revision_instruction import RevisionInstruction
from .revision_comment import RevisionComment
from .approval_history import ApprovalHistory
from .notification import Notification
from .audit_log import AuditLog

__all__ = [
    # 基底クラス
    "Base",
    "TimestampMixin", 
    "UUIDMixin",
    
    # Enums
    "UserRole",
    "RevisionStatus",
    "ArticleTarget",
    "CommentType",
    "InstructionPriority",
    "ApprovalAction",
    
    # モデル
    "User",
    "InfoCategory",
    "Article", 
    "Revision",
    "RevisionEditHistory",
    "RevisionInstruction",
    "RevisionComment",
    "ApprovalHistory",
    "Notification",
    "AuditLog",
    
    # 定数
    "INITIAL_CATEGORIES",
]
```

### 7.3 モデルメソッドとプロパティの活用例

```python
# 使用例
async def example_usage():
    async with AsyncSessionLocal() as session:
        # ユーザーの作成
        user = User(
            username="testuser",
            email="test@example.com",
            password_hash="hashed_password",
            role=UserRole.GENERAL
        )
        session.add(user)
        await session.commit()
        
        # 修正案の作成
        revision = Revision(
            target_article_id="ART001",
            proposer_id=user.id,
            after_title="新しいタイトル",
            reason="タイトルの改善"
        )
        session.add(revision)
        await session.commit()
        
        # 差分の取得
        changed_fields = revision.get_changed_fields()
        diff_summary = revision.get_diff_summary()
        
        # プロパティの活用
        if revision.is_editable:
            # 編集可能な場合の処理
            pass
        
        if user.can_approve_revisions:
            # 承認可能な場合の処理
            pass
```

この設計により、SQLAlchemy 2.0の最新機能を活用した型安全で保守性の高いモデル定義が完成します。非同期対応、適切な制約、インデックス、リレーションシップが全て含まれており、要件定義書のすべての機能をサポートできます。