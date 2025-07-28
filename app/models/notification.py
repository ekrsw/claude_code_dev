from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, String, Text, DateTime, ForeignKey, JSON, Enum as SQLEnum, UUID
from sqlalchemy.orm import relationship

from app.constants.enums import NotificationType
from app.db.base_model import BaseModel


class Notification(BaseModel):
    """User notification model"""
    
    __tablename__ = "notifications"
    
    recipient_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type = Column(SQLEnum(NotificationType), nullable=False)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    extra_data = Column(JSON, nullable=True)  # Additional data (revision_id, etc.)
    is_read = Column(Boolean, default=False, nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    recipient = relationship("User", back_populates="notifications")
    
    def __repr__(self) -> str:
        return f"<Notification(type={self.type}, recipient={self.recipient_id}, read={self.is_read})>"
    
    def mark_as_read(self) -> None:
        """Mark notification as read"""
        self.is_read = True
        self.read_at = datetime.now(timezone.utc)