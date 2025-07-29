from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.repositories.base import BaseRepository
from app.schemas.notification import NotificationCreate, NotificationUpdate
from app.constants.enums import NotificationType


class NotificationRepository(BaseRepository[Notification]):
    """Repository for notification operations"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(Notification, db)
    
    async def get_by_recipient(
        self,
        recipient_id: UUID,
        *,
        unread_only: bool = False,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        notification_type: Optional[NotificationType] = None
    ) -> List[Notification]:
        """Get notifications for a specific recipient"""
        query = select(self.model).where(self.model.recipient_id == recipient_id)
        
        if unread_only:
            query = query.where(self.model.is_read == False)
        
        if notification_type:
            query = query.where(self.model.type == notification_type)
        
        query = query.order_by(desc(self.model.created_at))
        
        if offset:
            query = query.offset(offset)
        if limit:
            query = query.limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_unread_count(self, recipient_id: UUID) -> int:
        """Get count of unread notifications for a recipient"""
        query = select(func.count(self.model.id)).where(
            and_(
                self.model.recipient_id == recipient_id,
                self.model.is_read == False
            )
        )
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def get_total_count(self, recipient_id: UUID) -> int:
        """Get total count of notifications for a recipient"""
        query = select(func.count(self.model.id)).where(
            self.model.recipient_id == recipient_id
        )
        result = await self.db.execute(query)
        return result.scalar() or 0
    
    async def get_counts_and_notifications(
        self,
        recipient_id: UUID,
        *,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        notification_type: Optional[NotificationType] = None
    ) -> Tuple[int, int, List[Notification]]:
        """Get total count, unread count, and notifications in one operation"""
        # Get counts
        total_count = await self.get_total_count(recipient_id)
        unread_count = await self.get_unread_count(recipient_id)
        
        # Get notifications
        notifications = await self.get_by_recipient(
            recipient_id,
            limit=limit,
            offset=offset,
            notification_type=notification_type
        )
        
        return total_count, unread_count, notifications
    
    async def mark_as_read(self, notification_id: UUID) -> Optional[Notification]:
        """Mark a single notification as read"""
        notification = await self.get(notification_id)
        if notification and not notification.is_read:
            notification.mark_as_read()
            await self.db.commit()
            await self.db.refresh(notification)
        return notification
    
    async def mark_multiple_as_read(
        self,
        notification_ids: List[UUID],
        recipient_id: Optional[UUID] = None
    ) -> int:
        """Mark multiple notifications as read"""
        query = select(self.model).where(self.model.id.in_(notification_ids))
        
        if recipient_id:
            query = query.where(self.model.recipient_id == recipient_id)
        
        result = await self.db.execute(query)
        notifications = result.scalars().all()
        
        updated_count = 0
        for notification in notifications:
            if not notification.is_read:
                notification.mark_as_read()
                updated_count += 1
        
        if updated_count > 0:
            await self.db.commit()
        
        return updated_count
    
    async def mark_all_as_read(self, recipient_id: UUID) -> int:
        """Mark all unread notifications as read for a recipient"""
        query = select(self.model).where(
            and_(
                self.model.recipient_id == recipient_id,
                self.model.is_read == False
            )
        )
        result = await self.db.execute(query)
        notifications = result.scalars().all()
        
        for notification in notifications:
            notification.mark_as_read()
        
        if notifications:
            await self.db.commit()
        
        return len(notifications)
    
    async def delete_old_notifications(
        self,
        recipient_id: Optional[UUID] = None,
        days_old: int = 30
    ) -> int:
        """Delete notifications older than specified days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        query = select(self.model).where(self.model.created_at < cutoff_date)
        
        if recipient_id:
            query = query.where(self.model.recipient_id == recipient_id)
        
        result = await self.db.execute(query)
        notifications = result.scalars().all()
        
        for notification in notifications:
            await self.delete(notification.id)
        
        return len(notifications)
    
    async def get_latest_notification(self, recipient_id: UUID) -> Optional[Notification]:
        """Get the latest notification for a recipient"""
        query = select(self.model).where(
            self.model.recipient_id == recipient_id
        ).order_by(desc(self.model.created_at)).limit(1)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def create_revision_notification(
        self,
        recipient_id: UUID,
        notification_type: NotificationType,
        revision_id: UUID,
        title: str,
        content: str,
        extra_data: Optional[dict] = None
    ) -> Notification:
        """Create a revision-related notification with standardized metadata"""
        metadata = {
            "revision_id": str(revision_id),
            **(extra_data or {})
        }
        
        return await self.create(
            recipient_id=recipient_id,
            type=notification_type,
            title=title,
            content=content,
            extra_data=metadata
        )