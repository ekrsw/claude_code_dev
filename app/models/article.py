from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.db.base_model import BaseModel


class Article(BaseModel):
    """Existing article model (read-only reference)"""
    
    __tablename__ = "articles"
    
    # Basic information
    article_id = Column(String(50), unique=True, nullable=False, index=True)
    article_number = Column(String(50), nullable=True)
    title = Column(Text, nullable=False)
    
    # Category and classification
    info_category_code = Column(String(2), ForeignKey("info_categories.code"), nullable=True)
    keywords = Column(Text, nullable=True)  # Comma-separated keywords
    importance = Column(Boolean, default=False, nullable=False)
    target = Column(String(20), nullable=True)  # 社内/社外/対象外
    
    # Content
    question = Column(Text, nullable=True)
    answer = Column(Text, nullable=True)
    additional_comment = Column(Text, nullable=True)
    
    # Publishing period
    publish_start = Column(DateTime(timezone=True), nullable=True)
    publish_end = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    approval_group = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    category = relationship("InfoCategory", backref="articles")
    revisions = relationship("Revision", back_populates="target_article", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Article(article_id={self.article_id}, title={self.title[:50]}...)>"
    
    @property
    def is_published(self) -> bool:
        """Check if article is currently published"""
        now = datetime.utcnow()
        if self.publish_start and now < self.publish_start:
            return False
        if self.publish_end and now > self.publish_end:
            return False
        return self.is_active
    
    @property
    def keywords_list(self) -> list[str]:
        """Get keywords as a list"""
        if not self.keywords:
            return []
        return [k.strip() for k in self.keywords.split(",") if k.strip()]