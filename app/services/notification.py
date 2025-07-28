from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.constants.enums import NotificationType, RevisionStatus
from app.models.notification import Notification
from app.models.revision import Revision
from app.models.user import User
from app.repositories.notification import NotificationRepository
from app.schemas.notification import (
    NotificationCreate,
    NotificationResponse,
    NotificationListResponse,
    NotificationSummary
)


class NotificationService:
    """Service for managing notifications"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.notification_repository = NotificationRepository(db)
    
    async def create_notification(
        self,
        recipient_id: UUID,
        notification_type: NotificationType,
        title: str,
        content: str,
        extra_data: Optional[Dict[str, Any]] = None
    ) -> NotificationResponse:
        """Create a new notification"""
        notification = await self.notification_repository.create(
            recipient_id=recipient_id,
            type=notification_type,
            title=title,
            content=content,
            extra_data=extra_data
        )
        return NotificationResponse.model_validate(notification)
    
    async def get_notifications(
        self,
        recipient_id: UUID,
        *,
        page: int = 1,
        page_size: int = 20,
        unread_only: bool = False,
        notification_type: Optional[NotificationType] = None
    ) -> NotificationListResponse:
        """Get paginated notifications for a user"""
        offset = (page - 1) * page_size
        
        total_count, unread_count, notifications = await self.notification_repository.get_counts_and_notifications(
            recipient_id,
            limit=page_size,
            offset=offset,
            notification_type=notification_type
        )
        
        # Filter by unread if requested
        if unread_only:
            notifications = [n for n in notifications if not n.is_read]
            total_count = unread_count
        
        total_pages = (total_count + page_size - 1) // page_size
        
        notification_responses = [
            NotificationResponse.model_validate(notification)
            for notification in notifications
        ]
        
        return NotificationListResponse(
            notifications=notification_responses,
            total=total_count,
            unread_count=unread_count,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )
    
    async def get_notification(self, notification_id: UUID) -> Optional[NotificationResponse]:
        """Get a single notification"""
        notification = await self.notification_repository.get(notification_id)
        if notification:
            return NotificationResponse.model_validate(notification)
        return None
    
    async def mark_as_read(self, notification_id: UUID) -> Optional[NotificationResponse]:
        """Mark a notification as read"""
        notification = await self.notification_repository.mark_as_read(notification_id)
        if notification:
            return NotificationResponse.model_validate(notification)
        return None
    
    async def mark_multiple_as_read(
        self,
        notification_ids: List[UUID],
        recipient_id: UUID
    ) -> int:
        """Mark multiple notifications as read"""
        return await self.notification_repository.mark_multiple_as_read(
            notification_ids, recipient_id
        )
    
    async def mark_all_as_read(self, recipient_id: UUID) -> int:
        """Mark all notifications as read for a user"""
        return await self.notification_repository.mark_all_as_read(recipient_id)
    
    async def get_notification_summary(self, recipient_id: UUID) -> NotificationSummary:
        """Get notification summary for a user"""
        total_count = await self.notification_repository.get_total_count(recipient_id)
        unread_count = await self.notification_repository.get_unread_count(recipient_id)
        latest_notification = await self.notification_repository.get_latest_notification(recipient_id)
        
        latest_response = None
        if latest_notification:
            latest_response = NotificationResponse.model_validate(latest_notification)
        
        return NotificationSummary(
            total_count=total_count,
            unread_count=unread_count,
            latest_notification=latest_response
        )
    
    async def delete_notification(self, notification_id: UUID) -> bool:
        """Delete a notification"""
        return await self.notification_repository.delete(notification_id)
    
    # Revision-specific notification methods
    
    async def notify_revision_created(
        self,
        revision: Revision,
        approvers: List[User]
    ) -> List[NotificationResponse]:
        """Notify approvers when a new revision is created"""
        notifications = []
        
        for approver in approvers:
            notification = await self.notification_repository.create_revision_notification(
                recipient_id=approver.id,
                notification_type=NotificationType.REVISION_CREATED,
                revision_id=revision.id,
                title="新しい修正案が作成されました",
                content=f"修正案「{revision.after_title or '(タイトルなし)'}」が作成されました。",
                extra_data={
                    "proposer_id": str(revision.proposer_id),
                    "target_article_id": revision.target_article_id
                }
            )
            notifications.append(NotificationResponse.model_validate(notification))
        
        return notifications
    
    async def notify_revision_submitted(
        self,
        revision: Revision,
        approvers: List[User]
    ) -> List[NotificationResponse]:
        """Notify approvers when a revision is submitted for review"""
        notifications = []
        
        for approver in approvers:
            notification = await self.notification_repository.create_revision_notification(
                recipient_id=approver.id,
                notification_type=NotificationType.REVISION_SUBMITTED,
                revision_id=revision.id,
                title="修正案がレビュー依頼されました",
                content=f"修正案「{revision.after_title or '(タイトルなし)'}」のレビューをお願いします。",
                extra_data={
                    "proposer_id": str(revision.proposer_id),
                    "target_article_id": revision.target_article_id
                }
            )
            notifications.append(NotificationResponse.model_validate(notification))
        
        return notifications
    
    async def notify_revision_edited(
        self,
        revision: Revision,
        editor: User,
        recipient_id: UUID,
        changes: Dict[str, Any]
    ) -> NotificationResponse:
        """Notify when a revision is edited by approver"""
        notification = await self.notification_repository.create_revision_notification(
            recipient_id=recipient_id,
            notification_type=NotificationType.REVISION_EDITED,
            revision_id=revision.id,
            title="修正案が編集されました",
            content=f"修正案「{revision.after_title or '(タイトルなし)'}」が{editor.username}さんによって編集されました。",
            extra_data={
                "editor_id": str(editor.id),
                "editor_name": editor.username,
                "changes": changes,
                "target_article_id": revision.target_article_id
            }
        )
        
        return NotificationResponse.model_validate(notification)
    
    async def notify_revision_approved(
        self,
        revision: Revision,
        approver: User,
        recipient_id: UUID
    ) -> NotificationResponse:
        """Notify when a revision is approved"""
        notification = await self.notification_repository.create_revision_notification(
            recipient_id=recipient_id,
            notification_type=NotificationType.REVISION_APPROVED,
            revision_id=revision.id,
            title="修正案が承認されました",
            content=f"修正案「{revision.after_title or '(タイトルなし)'}」が{approver.username}さんによって承認されました。",
            extra_data={
                "approver_id": str(approver.id),
                "approver_name": approver.username,
                "target_article_id": revision.target_article_id,
                "approval_comment": revision.approval_comment
            }
        )
        
        return NotificationResponse.model_validate(notification)
    
    async def notify_revision_rejected(
        self,
        revision: Revision,
        approver: User,
        recipient_id: UUID,
        rejection_reason: Optional[str] = None
    ) -> NotificationResponse:
        """Notify when a revision is rejected"""
        notification = await self.notification_repository.create_revision_notification(
            recipient_id=recipient_id,
            notification_type=NotificationType.REVISION_REJECTED,
            revision_id=revision.id,
            title="修正案が却下されました",
            content=f"修正案「{revision.after_title or '(タイトルなし)'}」が{approver.username}さんによって却下されました。",
            extra_data={
                "approver_id": str(approver.id),
                "approver_name": approver.username,
                "target_article_id": revision.target_article_id,
                "rejection_reason": rejection_reason
            }
        )
        
        return NotificationResponse.model_validate(notification)
    
    async def notify_revision_modification_requested(
        self,
        revision: Revision,
        approver: User,
        recipient_id: UUID,
        instruction_text: str
    ) -> NotificationResponse:
        """Notify when modification is requested for a revision"""
        notification = await self.notification_repository.create_revision_notification(
            recipient_id=recipient_id,
            notification_type=NotificationType.REVISION_REQUEST,
            revision_id=revision.id,
            title="修正案の修正が依頼されました",
            content=f"修正案「{revision.after_title or '(タイトルなし)'}」について{approver.username}さんから修正依頼があります。",
            extra_data={
                "approver_id": str(approver.id),
                "approver_name": approver.username,
                "target_article_id": revision.target_article_id,
                "instruction_text": instruction_text
            }
        )
        
        return NotificationResponse.model_validate(notification)
    
    async def notify_comment_added(
        self,
        revision: Revision,
        commenter: User,
        recipient_id: UUID,
        comment_text: str
    ) -> NotificationResponse:
        """Notify when a comment is added to a revision"""
        notification = await self.notification_repository.create_revision_notification(
            recipient_id=recipient_id,
            notification_type=NotificationType.COMMENT_ADDED,
            revision_id=revision.id,
            title="修正案にコメントが追加されました",
            content=f"修正案「{revision.after_title or '(タイトルなし)'}」に{commenter.username}さんがコメントを追加しました。",
            extra_data={
                "commenter_id": str(commenter.id),
                "commenter_name": commenter.username,
                "target_article_id": revision.target_article_id,
                "comment_text": comment_text
            }
        )
        
        return NotificationResponse.model_validate(notification)
    
    async def cleanup_old_notifications(
        self,
        recipient_id: Optional[UUID] = None,
        days_old: int = 30
    ) -> int:
        """Clean up old notifications"""
        return await self.notification_repository.delete_old_notifications(
            recipient_id, days_old
        )