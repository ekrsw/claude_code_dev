"""
通知サービスの単体テスト
"""
import pytest
from uuid import uuid4, UUID
from datetime import datetime

from app.services.notification import NotificationService
from app.models.notification import Notification
from app.models.revision import Revision
from app.models.user import User
from app.constants.enums import NotificationType, Role, RevisionStatus
from app.schemas.notification import NotificationCreate


@pytest.mark.asyncio
class TestNotificationService:
    """NotificationServiceのテストクラス"""
    
    async def test_create_notification_success(self, db_session, test_user):
        """通知作成が成功することを確認"""
        notification_service = NotificationService(db_session)
        
        notification_response = await notification_service.create_notification(
            recipient_id=test_user.id,
            notification_type=NotificationType.REVISION_CREATED,
            title="テスト通知",
            content="これはテスト用の通知です。",
            extra_data={"test_key": "test_value"}
        )
        
        assert notification_response is not None
        assert notification_response.title == "テスト通知"
        assert notification_response.content == "これはテスト用の通知です。"
        assert notification_response.type == NotificationType.REVISION_CREATED
        assert notification_response.recipient_id == test_user.id
        assert notification_response.is_read is False
    
    async def test_get_notifications_success(self, db_session, test_user):
        """通知一覧取得が成功することを確認"""
        notification_service = NotificationService(db_session)
        
        # 複数の通知を作成
        for i in range(5):
            await notification_service.create_notification(
                recipient_id=test_user.id,
                notification_type=NotificationType.REVISION_CREATED,
                title=f"テスト通知{i}",
                content=f"これはテスト用の通知{i}です。"
            )
        
        # 通知一覧を取得
        notification_list = await notification_service.get_notifications(
            recipient_id=test_user.id,
            page=1,
            page_size=10
        )
        
        assert notification_list is not None
        assert len(notification_list.notifications) >= 5
        assert notification_list.total >= 5
        assert notification_list.page == 1
        assert notification_list.page_size == 10
    
    async def test_get_notifications_unread_only(self, db_session, test_user):
        """未読通知のみ取得が成功することを確認"""
        notification_service = NotificationService(db_session)
        
        # 複数の通知を作成
        notifications = []
        for i in range(3):
            notification = await notification_service.create_notification(
                recipient_id=test_user.id,
                notification_type=NotificationType.REVISION_CREATED,
                title=f"テスト通知{i}",
                content=f"これはテスト用の通知{i}です。"
            )
            notifications.append(notification)
        
        # 1つの通知を既読にする
        await notification_service.mark_as_read(notifications[0].id)
        
        # 未読通知のみ取得
        unread_list = await notification_service.get_notifications(
            recipient_id=test_user.id,
            unread_only=True
        )
        
        assert len(unread_list.notifications) >= 2
        assert all(not n.is_read for n in unread_list.notifications)
    
    async def test_get_notification_success(self, db_session, test_user):
        """単一通知取得が成功することを確認"""
        notification_service = NotificationService(db_session)
        
        # 通知を作成
        created_notification = await notification_service.create_notification(
            recipient_id=test_user.id,
            notification_type=NotificationType.REVISION_CREATED,
            title="単一取得テスト",
            content="これは単一取得テスト用の通知です。"
        )
        
        # 通知を取得
        retrieved_notification = await notification_service.get_notification(created_notification.id)
        
        assert retrieved_notification is not None
        assert retrieved_notification.id == created_notification.id
        assert retrieved_notification.title == "単一取得テスト"
    
    async def test_get_notification_not_found(self, db_session):
        """存在しない通知の取得でNoneが返されることを確認"""
        notification_service = NotificationService(db_session)
        
        non_existent_id = uuid4()
        notification = await notification_service.get_notification(non_existent_id)
        
        assert notification is None
    
    async def test_mark_as_read_success(self, db_session, test_user):
        """通知の既読化が成功することを確認"""
        notification_service = NotificationService(db_session)
        
        # 通知を作成
        notification = await notification_service.create_notification(
            recipient_id=test_user.id,
            notification_type=NotificationType.REVISION_CREATED,
            title="既読テスト",
            content="これは既読テスト用の通知です。"
        )
        
        assert notification.is_read is False
        
        # 既読にする
        updated_notification = await notification_service.mark_as_read(notification.id)
        
        assert updated_notification is not None
        assert updated_notification.is_read is True
    
    async def test_mark_as_read_not_found(self, db_session):
        """存在しない通知の既読化でNoneが返されることを確認"""
        notification_service = NotificationService(db_session)
        
        non_existent_id = uuid4()
        result = await notification_service.mark_as_read(non_existent_id)
        
        assert result is None
    
    async def test_mark_multiple_as_read_success(self, db_session, test_user):
        """複数通知の一括既読化が成功することを確認"""
        notification_service = NotificationService(db_session)
        
        # 複数の通知を作成
        notification_ids = []
        for i in range(3):
            notification = await notification_service.create_notification(
                recipient_id=test_user.id,
                notification_type=NotificationType.REVISION_CREATED,
                title=f"一括既読テスト{i}",
                content=f"これは一括既読テスト{i}用の通知です。"
            )
            notification_ids.append(notification.id)
        
        # 一括で既読にする
        updated_count = await notification_service.mark_multiple_as_read(
            notification_ids, test_user.id
        )
        
        assert updated_count >= 3
    
    async def test_mark_all_as_read_success(self, db_session, test_user):
        """全通知の一括既読化が成功することを確認"""
        notification_service = NotificationService(db_session)
        
        # 複数の通知を作成
        for i in range(3):
            await notification_service.create_notification(
                recipient_id=test_user.id,
                notification_type=NotificationType.REVISION_CREATED,
                title=f"全一括既読テスト{i}",
                content=f"これは全一括既読テスト{i}用の通知です。"
            )
        
        # 全て既読にする
        updated_count = await notification_service.mark_all_as_read(test_user.id)
        
        assert updated_count >= 3
    
    async def test_get_notification_summary_success(self, db_session, test_user):
        """通知サマリー取得が成功することを確認"""
        notification_service = NotificationService(db_session)
        
        # 複数の通知を作成
        notifications = []
        for i in range(3):
            notification = await notification_service.create_notification(
                recipient_id=test_user.id,
                notification_type=NotificationType.REVISION_CREATED,
                title=f"サマリーテスト{i}",
                content=f"これはサマリーテスト{i}用の通知です。"
            )
            notifications.append(notification)
        
        # 1つ既読にする
        await notification_service.mark_as_read(notifications[0].id)
        
        # サマリーを取得
        summary = await notification_service.get_notification_summary(test_user.id)
        
        assert summary is not None
        assert summary.total_count >= 3
        assert summary.unread_count >= 2
        assert summary.latest_notification is not None
    
    async def test_delete_notification_success(self, db_session, test_user):
        """通知削除が成功することを確認"""
        notification_service = NotificationService(db_session)
        
        # 通知を作成
        notification = await notification_service.create_notification(
            recipient_id=test_user.id,
            notification_type=NotificationType.REVISION_CREATED,
            title="削除テスト",
            content="これは削除テスト用の通知です。"
        )
        
        # 削除する
        deleted = await notification_service.delete_notification(notification.id)
        
        assert deleted is True
        
        # 削除後に取得を試みる
        retrieved = await notification_service.get_notification(notification.id)
        assert retrieved is None
    
    async def test_delete_notification_not_found(self, db_session):
        """存在しない通知の削除でFalseが返されることを確認"""
        notification_service = NotificationService(db_session)
        
        non_existent_id = uuid4()
        deleted = await notification_service.delete_notification(non_existent_id)
        
        assert deleted is False
    
    async def test_notify_revision_created_success(self, db_session, test_user, test_approver, test_article):
        """修正案作成通知が成功することを確認"""
        notification_service = NotificationService(db_session)
        
        # 修正案を作成
        revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=test_user.id,
            status=RevisionStatus.DRAFT,
            reason="修正案作成通知テスト用の修正案です。内容を改善するために作成しました。",
            before_title=test_article.title,
            after_title="修正案作成通知テスト",
            before_answer=test_article.answer,
            after_answer="修正案作成通知テスト内容",
            version=1
        )
        db_session.add(revision)
        await db_session.commit()
        
        # 承認者リストを作成
        approvers = [test_approver]
        
        # 通知を送信
        notifications = await notification_service.notify_revision_created(revision, approvers)
        
        assert len(notifications) == 1
        assert notifications[0].type == NotificationType.REVISION_CREATED
        assert notifications[0].recipient_id == test_approver.id
        assert "新しい修正案が作成されました" in notifications[0].title
    
    async def test_notify_revision_submitted_success(self, db_session, test_user, test_approver, test_article):
        """修正案提出通知が成功することを確認"""
        notification_service = NotificationService(db_session)
        
        # 修正案を作成
        revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=test_user.id,
            status=RevisionStatus.UNDER_REVIEW,
            reason="修正案提出通知テスト用の修正案です。内容を改善するために作成しました。",
            before_title=test_article.title,
            after_title="修正案提出通知テスト",
            before_answer=test_article.answer,
            after_answer="修正案提出通知テスト内容",
            version=1
        )
        db_session.add(revision)
        await db_session.commit()
        
        # 承認者リストを作成
        approvers = [test_approver]
        
        # 通知を送信
        notifications = await notification_service.notify_revision_submitted(revision, approvers)
        
        assert len(notifications) == 1
        assert notifications[0].type == NotificationType.REVISION_SUBMITTED
        assert notifications[0].recipient_id == test_approver.id
        assert "修正案がレビュー依頼されました" in notifications[0].title
    
    async def test_notify_revision_approved_success(self, db_session, test_user, test_approver, test_article):
        """修正案承認通知が成功することを確認"""
        notification_service = NotificationService(db_session)
        
        # 修正案を作成
        revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=test_user.id,
            status=RevisionStatus.APPROVED,
            reason="修正案承認通知テスト用の修正案です。内容を改善するために作成しました。",
            before_title=test_article.title,
            after_title="修正案承認通知テスト",
            before_answer=test_article.answer,
            after_answer="修正案承認通知テスト内容",
            version=1,
            approver_id=test_approver.id,
            approval_comment="承認します。良い修正案です。"
        )
        db_session.add(revision)
        await db_session.commit()
        
        # 通知を送信
        notification = await notification_service.notify_revision_approved(
            revision, test_approver, test_user.id
        )
        
        assert notification is not None
        assert notification.type == NotificationType.REVISION_APPROVED
        assert notification.recipient_id == test_user.id
        assert "修正案が承認されました" in notification.title
    
    async def test_notify_revision_rejected_success(self, db_session, test_user, test_approver, test_article):
        """修正案却下通知が成功することを確認"""
        notification_service = NotificationService(db_session)
        
        # 修正案を作成
        revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=test_user.id,
            status=RevisionStatus.REJECTED,
            reason="修正案却下通知テスト用の修正案です。内容を改善するために作成しました。",
            before_title=test_article.title,
            after_title="修正案却下通知テスト",
            before_answer=test_article.answer,
            after_answer="修正案却下通知テスト内容",
            version=1,
            approver_id=test_approver.id
        )
        db_session.add(revision)
        await db_session.commit()
        
        # 通知を送信
        notification = await notification_service.notify_revision_rejected(
            revision, test_approver, test_user.id, "内容が不適切です。"
        )
        
        assert notification is not None
        assert notification.type == NotificationType.REVISION_REJECTED
        assert notification.recipient_id == test_user.id
        assert "修正案が却下されました" in notification.title
    
    async def test_notify_revision_modification_requested_success(self, db_session, test_user, test_approver, test_article):
        """修正案修正依頼通知が成功することを確認"""
        notification_service = NotificationService(db_session)
        
        # 修正案を作成
        revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=test_user.id,
            status=RevisionStatus.REVISION_REQUESTED,
            reason="修正案修正依頼通知テスト用の修正案です。内容を改善するために作成しました。",
            before_title=test_article.title,
            after_title="修正案修正依頼通知テスト",
            before_answer=test_article.answer,
            after_answer="修正案修正依頼通知テスト内容",
            version=1
        )
        db_session.add(revision)
        await db_session.commit()
        
        # 通知を送信
        notification = await notification_service.notify_revision_modification_requested(
            revision, test_approver, test_user.id, "タイトルをより具体的にしてください。"
        )
        
        assert notification is not None
        assert notification.type == NotificationType.REVISION_REQUEST
        assert notification.recipient_id == test_user.id
        assert "修正案の修正が依頼されました" in notification.title
    
    async def test_notify_comment_added_success(self, db_session, test_user, test_approver, test_article):
        """コメント追加通知が成功することを確認"""
        notification_service = NotificationService(db_session)
        
        # 修正案を作成
        revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=test_user.id,
            status=RevisionStatus.UNDER_REVIEW,
            reason="コメント追加通知テスト用の修正案です。内容を改善するために作成しました。",
            before_title=test_article.title,
            after_title="コメント追加通知テスト",
            before_answer=test_article.answer,
            after_answer="コメント追加通知テスト内容",
            version=1
        )
        db_session.add(revision)
        await db_session.commit()
        
        # 通知を送信
        notification = await notification_service.notify_comment_added(
            revision, test_approver, test_user.id, "良い修正案ですね。"
        )
        
        assert notification is not None
        assert notification.type == NotificationType.COMMENT_ADDED
        assert notification.recipient_id == test_user.id
        assert "修正案にコメントが追加されました" in notification.title
    
    async def test_cleanup_old_notifications_success(self, db_session, test_user):
        """古い通知のクリーンアップが成功することを確認"""
        notification_service = NotificationService(db_session)
        
        # 複数の通知を作成
        for i in range(3):
            await notification_service.create_notification(
                recipient_id=test_user.id,
                notification_type=NotificationType.REVISION_CREATED,
                title=f"クリーンアップテスト{i}",
                content=f"これはクリーンアップテスト{i}用の通知です。"
            )
        
        # クリーンアップを実行（30日より古い通知を削除）
        deleted_count = await notification_service.cleanup_old_notifications(
            recipient_id=test_user.id,
            days_old=30
        )
        
        # 新しく作成した通知なので削除されない
        assert deleted_count == 0
        
        # 全体のクリーンアップも実行
        deleted_count_global = await notification_service.cleanup_old_notifications(days_old=30)
        assert deleted_count_global >= 0