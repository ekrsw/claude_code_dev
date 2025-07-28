from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_user
from app.constants.enums import NotificationType
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    NotificationMarkReadRequest,
    NotificationSummary
)
from app.services.notification import NotificationService


router = APIRouter()


@router.get("/", response_model=NotificationListResponse)
async def get_notifications(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Number of notifications per page"),
    unread_only: bool = Query(False, description="Filter to unread notifications only"),
    notification_type: Optional[NotificationType] = Query(None, description="Filter by notification type"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get paginated notifications for the current user"""
    notification_service = NotificationService(db)
    
    return await notification_service.get_notifications(
        recipient_id=current_user.id,
        page=page,
        page_size=page_size,
        unread_only=unread_only,
        notification_type=notification_type
    )


@router.get("/summary", response_model=NotificationSummary)
async def get_notification_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get notification summary for the current user"""
    notification_service = NotificationService(db)
    
    return await notification_service.get_notification_summary(current_user.id)


@router.get("/unread-count")
async def get_unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get count of unread notifications for the current user"""
    notification_service = NotificationService(db)
    summary = await notification_service.get_notification_summary(current_user.id)
    
    return {"unread_count": summary.unread_count}


@router.get("/{notification_id}", response_model=NotificationResponse)
async def get_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get a specific notification"""
    notification_service = NotificationService(db)
    
    notification = await notification_service.get_notification(notification_id)
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    # Check if the notification belongs to the current user
    if notification.recipient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this notification"
        )
    
    return notification


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_as_read(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark a specific notification as read"""
    notification_service = NotificationService(db)
    
    # First, check if the notification exists and belongs to the user
    notification = await notification_service.get_notification(notification_id)
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    if notification.recipient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this notification"
        )
    
    # Mark as read
    updated_notification = await notification_service.mark_as_read(notification_id)
    if not updated_notification:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification"
        )
    
    return updated_notification


@router.patch("/mark-read")
async def mark_multiple_notifications_as_read(
    request: NotificationMarkReadRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark multiple notifications as read"""
    notification_service = NotificationService(db)
    
    updated_count = await notification_service.mark_multiple_as_read(
        request.notification_ids, current_user.id
    )
    
    return {
        "message": f"Marked {updated_count} notifications as read",
        "updated_count": updated_count
    }


@router.patch("/mark-all-read")
async def mark_all_notifications_as_read(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark all notifications as read for the current user"""
    notification_service = NotificationService(db)
    
    updated_count = await notification_service.mark_all_as_read(current_user.id)
    
    return {
        "message": f"Marked {updated_count} notifications as read",
        "updated_count": updated_count
    }


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a specific notification"""
    notification_service = NotificationService(db)
    
    # First, check if the notification exists and belongs to the user
    notification = await notification_service.get_notification(notification_id)
    if not notification:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    if notification.recipient_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this notification"
        )
    
    # Delete the notification
    success = await notification_service.delete_notification(notification_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete notification"
        )
    
    return {"message": "Notification deleted successfully"}


@router.post("/cleanup")
async def cleanup_old_notifications(
    days_old: int = Query(30, ge=1, le=365, description="Delete notifications older than this many days"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Clean up old notifications for the current user"""
    notification_service = NotificationService(db)
    
    deleted_count = await notification_service.cleanup_old_notifications(
        recipient_id=current_user.id,
        days_old=days_old
    )
    
    return {
        "message": f"Deleted {deleted_count} old notifications",
        "deleted_count": deleted_count
    }