from datetime import datetime

from sqlalchemy import Column, Text, DateTime, ForeignKey, Enum as SQLEnum, UUID
from sqlalchemy.orm import relationship

from app.constants.enums import ApprovalAction
from app.db.base_model import BaseModel


class ApprovalHistory(BaseModel):
    """Approval action history"""
    
    __tablename__ = "approval_histories"
    
    revision_id = Column(UUID(as_uuid=True), ForeignKey("revisions.id"), nullable=False)
    actor_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action = Column(SQLEnum(ApprovalAction), nullable=False)
    comment = Column(Text, nullable=True)
    
    # Relationships
    revision = relationship("Revision", back_populates="approval_histories")
    actor = relationship("User")
    
    def __repr__(self) -> str:
        return f"<ApprovalHistory(revision_id={self.revision_id}, action={self.action})>"