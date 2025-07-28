from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID

from pydantic import BaseModel, Field

from app.constants.enums import NotificationType


class NotificationBase(BaseModel):
    """Base notification schema"""
    type: NotificationType
    title: str = Field(..., max_length=200, description="Notification title")
    content: str = Field(..., description="Notification content")
    extra_data: Optional[Dict[str, Any]] = Field(None, description="Additional notification data")


class NotificationCreate(NotificationBase):
    """Schema for creating a notification"""
    recipient_id: UUID


class NotificationUpdate(BaseModel):
    """Schema for updating a notification"""
    is_read: Optional[bool] = None
    read_at: Optional[datetime] = None


class NotificationResponse(NotificationBase):
    """Schema for notification response"""
    id: UUID
    recipient_id: UUID
    is_read: bool
    read_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NotificationListResponse(BaseModel):
    """Schema for notification list response"""
    notifications: List[NotificationResponse]
    total: int
    unread_count: int
    page: int
    page_size: int
    total_pages: int


class NotificationMarkReadRequest(BaseModel):
    """Schema for marking notifications as read"""
    notification_ids: List[UUID] = Field(..., description="List of notification IDs to mark as read")


class NotificationSummary(BaseModel):
    """Schema for notification summary"""
    total_count: int
    unread_count: int
    latest_notification: Optional[NotificationResponse] = None