from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Column, String, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship

from app.constants.enums import Role
from app.db.base_model import BaseModel


class User(BaseModel):
    """User model"""
    
    __tablename__ = "users"
    
    # Basic information
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    
    # Role and permissions
    role = Column(SQLEnum(Role), default=Role.GENERAL, nullable=False)
    is_sv = Column(Boolean, default=False, nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # External system mapping (prepared for future)
    sweet_name = Column(String(100), nullable=True)
    ctstage_name = Column(String(100), nullable=True)
    
    # Authentication tracking
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    password_changed_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    
    # Relationships
    created_revisions = relationship(
        "Revision",
        back_populates="proposer",
        foreign_keys="Revision.proposer_id",
        cascade="all, delete-orphan"
    )
    approved_revisions = relationship(
        "Revision",
        back_populates="approver",
        foreign_keys="Revision.approver_id"
    )
    edit_histories = relationship(
        "RevisionEditHistory",
        back_populates="editor",
        cascade="all, delete-orphan"
    )
    notifications = relationship(
        "Notification",
        back_populates="recipient",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<User(username={self.username}, role={self.role})>"
    
    @property
    def is_supervisor(self) -> bool:
        """Check if user has supervisor privileges"""
        return self.is_sv or self.role in [Role.SUPERVISOR, Role.APPROVER, Role.ADMIN]
    
    @property
    def can_approve(self) -> bool:
        """Check if user can approve revisions"""
        return self.role in [Role.APPROVER, Role.ADMIN] or self.is_sv
    
    @property
    def is_admin(self) -> bool:
        """Check if user is admin"""
        return self.role == Role.ADMIN