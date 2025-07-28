from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean, Column, Integer, String, Text, DateTime, 
    ForeignKey, JSON, Enum as SQLEnum, UUID
)
from sqlalchemy.orm import relationship

from app.constants.enums import RevisionStatus, Role, Priority
from app.db.base_model import BaseModel


class Revision(BaseModel):
    """Revision proposal model"""
    
    __tablename__ = "revisions"
    
    # Basic information
    target_article_id = Column(String(50), ForeignKey("articles.article_id"), nullable=False)
    proposer_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    status = Column(SQLEnum(RevisionStatus), default=RevisionStatus.DRAFT, nullable=False, index=True)
    
    # Modification content (before/after for each field)
    before_title = Column(Text, nullable=True)
    after_title = Column(Text, nullable=True)
    before_info_category = Column(String(2), ForeignKey("info_categories.code"), nullable=True)
    after_info_category = Column(String(2), ForeignKey("info_categories.code"), nullable=True)
    before_keywords = Column(Text, nullable=True)
    after_keywords = Column(Text, nullable=True)
    before_importance = Column(Boolean, nullable=True)
    after_importance = Column(Boolean, nullable=True)
    before_publish_start = Column(DateTime(timezone=True), nullable=True)
    after_publish_start = Column(DateTime(timezone=True), nullable=True)
    before_publish_end = Column(DateTime(timezone=True), nullable=True)
    after_publish_end = Column(DateTime(timezone=True), nullable=True)
    before_target = Column(String(20), nullable=True)
    after_target = Column(String(20), nullable=True)
    before_question = Column(Text, nullable=True)
    after_question = Column(Text, nullable=True)
    before_answer = Column(Text, nullable=True)
    after_answer = Column(Text, nullable=True)
    before_additional_comment = Column(Text, nullable=True)
    after_additional_comment = Column(Text, nullable=True)
    
    # Metadata
    reason = Column(Text, nullable=False)
    approver_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approval_comment = Column(Text, nullable=True)
    version = Column(Integer, default=1, nullable=False)  # For optimistic locking
    
    # Review period
    review_start_date = Column(DateTime(timezone=True), nullable=True)
    review_deadline_date = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    target_article = relationship("Article", back_populates="revisions")
    proposer = relationship("User", foreign_keys=[proposer_id], back_populates="created_revisions")
    approver = relationship("User", foreign_keys=[approver_id], back_populates="approved_revisions")
    before_category = relationship("InfoCategory", foreign_keys=[before_info_category])
    after_category = relationship("InfoCategory", foreign_keys=[after_info_category])
    edit_histories = relationship("RevisionEditHistory", back_populates="revision", cascade="all, delete-orphan")
    instructions = relationship("RevisionInstruction", back_populates="revision", cascade="all, delete-orphan")
    # Approval histories
    approval_histories = relationship("ApprovalHistory", back_populates="revision", cascade="all, delete-orphan")
    
    def __repr__(self) -> str:
        return f"<Revision(id={self.id}, status={self.status}, article={self.target_article_id})>"
    
    def get_modified_fields(self) -> list[str]:
        """Get list of fields that have been modified"""
        fields = [
            "title", "info_category", "keywords", "importance",
            "publish_start", "publish_end", "target", "question",
            "answer", "additional_comment"
        ]
        modified = []
        for field in fields:
            before_val = getattr(self, f"before_{field}")
            after_val = getattr(self, f"after_{field}")
            if before_val != after_val and after_val is not None:
                modified.append(field)
        return modified


class RevisionEditHistory(BaseModel):
    """Revision edit history"""
    
    __tablename__ = "revision_edit_histories"
    
    revision_id = Column(UUID(as_uuid=True), ForeignKey("revisions.id"), nullable=False)
    editor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    editor_role = Column(SQLEnum(Role), nullable=False)
    edited_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    changes = Column(JSON, nullable=False)  # JSON containing field changes
    comment = Column(Text, nullable=True)
    version_before = Column(Integer, nullable=False)
    version_after = Column(Integer, nullable=False)
    
    # Relationships
    revision = relationship("Revision", back_populates="edit_histories")
    editor = relationship("User", back_populates="edit_histories")
    
    def __repr__(self) -> str:
        return f"<RevisionEditHistory(revision_id={self.revision_id}, editor={self.editor_id})>"


class RevisionInstruction(BaseModel):
    """Revision modification instructions"""
    
    __tablename__ = "revision_instructions"
    
    revision_id = Column(UUID(as_uuid=True), ForeignKey("revisions.id"), nullable=False)
    instructor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    instruction_text = Column(Text, nullable=False)
    required_fields = Column(JSON, nullable=True)  # List of fields requiring modification
    priority = Column(SQLEnum(Priority), default=Priority.NORMAL, nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolution_comment = Column(Text, nullable=True)
    
    # Relationships
    revision = relationship("Revision", back_populates="instructions")
    instructor = relationship("User")
    
    def __repr__(self) -> str:
        return f"<RevisionInstruction(revision_id={self.revision_id}, priority={self.priority})>"