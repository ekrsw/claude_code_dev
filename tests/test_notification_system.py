"""
通知システムの包括的な単体テスト
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4
from datetime import datetime, timezone

def create_test_notification(**kwargs):
    """Helper function to create test notification with required timestamps"""
    now = datetime.now(timezone.utc)
    defaults = {
        'created_at': now,
        'updated_at': now,
        'is_read': False
    }
    defaults.update(kwargs)
    return Notification(**defaults)

from app.services.notification import NotificationService
from app.repositories.notification import NotificationRepository
from app.models.notification import Notification
from app.models.user import User
from app.models.revision import Revision
from app.constants.enums import NotificationType, Role, RevisionStatus
from app.schemas.notification import (
    NotificationResponse,
    NotificationListResponse,
    NotificationSummary
)


@pytest.fixture
def mock_db():
    """Mock database session"""
    return AsyncMock()


@pytest.fixture
def mock_notification_repo():
    """Mock notification repository"""
    return AsyncMock(spec=NotificationRepository)


@pytest.fixture
def notification_service(mock_db, mock_notification_repo):
    """Create notification service with mocked dependencies"""
    service = NotificationService(mock_db)
    service.notification_repository = mock_notification_repo
    return service


@pytest.fixture
def sample_user():
    """Sample user for testing"""
    return User(
        id=uuid4(),
        username="testuser",
        email="test@example.com",
        role=Role.GENERAL
    )


@pytest.fixture
def sample_approver():
    """Sample approver for testing"""
    return User(
        id=uuid4(),
        username="approver",
        email="approver@example.com",
        role=Role.APPROVER
    )


@pytest.fixture
def sample_revision(sample_user):
    """Sample revision for testing"""
    return Revision(
        id=uuid4(),
        proposer_id=sample_user.id,
        target_article_id="article_123",
        status=RevisionStatus.UNDER_REVIEW,
        reason="Test revision"
    )


@pytest.fixture
def sample_notification(sample_user):
    """Sample notification for testing"""
    return create_test_notification(
        id=uuid4(),
        recipient_id=sample_user.id,
        type=NotificationType.REVISION_CREATED,
        title="テスト通知",
        content="テスト用の通知コンテンツです",
        extra_data={"revision_id": str(uuid4())}
    )


class TestNotificationService:
    """通知サービスのテストクラス"""

    @pytest.mark.asyncio
    async def test_create_notification(self, notification_service, mock_notification_repo, sample_user):
        """通知作成のテスト"""
        # Arrange
        notification_id = uuid4()
        mock_notification = create_test_notification(
            id=notification_id,
            recipient_id=sample_user.id,
            type=NotificationType.REVISION_CREATED,
            title="テスト通知",
            content="テスト用の通知です"
        )
        mock_notification_repo.create.return_value = mock_notification

        # Act
        result = await notification_service.create_notification(
            recipient_id=sample_user.id,
            notification_type=NotificationType.REVISION_CREATED,
            title="テスト通知",
            content="テスト用の通知です"
        )

        # Assert
        assert isinstance(result, NotificationResponse)
        assert result.recipient_id == sample_user.id
        assert result.type == NotificationType.REVISION_CREATED
        mock_notification_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_notifications(self, notification_service, mock_notification_repo, sample_user):
        """通知一覧取得のテスト"""
        # Arrange
        notifications = [
            create_test_notification(
                id=uuid4(),
                recipient_id=sample_user.id,
                type=NotificationType.REVISION_CREATED,
                title=f"通知{i}",
                content=f"テスト通知{i}",
                is_read=False
            )
            for i in range(3)
        ]
        mock_notification_repo.get_counts_and_notifications.return_value = (3, 3, notifications)

        # Act
        result = await notification_service.get_notifications(
            recipient_id=sample_user.id,
            page=1,
            page_size=20
        )

        # Assert
        assert isinstance(result, NotificationListResponse)
        assert result.total == 3
        assert result.unread_count == 3
        assert len(result.notifications) == 3
        assert result.page == 1
        assert result.page_size == 20

    @pytest.mark.asyncio
    async def test_mark_as_read(self, notification_service, mock_notification_repo, sample_notification):
        """通知既読処理のテスト"""
        # Arrange
        sample_notification.is_read = True
        sample_notification.read_at = datetime.now(timezone.utc)
        mock_notification_repo.mark_as_read.return_value = sample_notification

        # Act
        result = await notification_service.mark_as_read(sample_notification.id)

        # Assert
        assert result is not None
        assert isinstance(result, NotificationResponse)
        mock_notification_repo.mark_as_read.assert_called_once_with(sample_notification.id)

    @pytest.mark.asyncio
    async def test_mark_multiple_as_read(self, notification_service, mock_notification_repo, sample_user):
        """複数通知既読処理のテスト"""
        # Arrange
        notification_ids = [uuid4(), uuid4(), uuid4()]
        mock_notification_repo.mark_multiple_as_read.return_value = 3

        # Act
        result = await notification_service.mark_multiple_as_read(
            notification_ids=notification_ids,
            recipient_id=sample_user.id
        )

        # Assert
        assert result == 3
        mock_notification_repo.mark_multiple_as_read.assert_called_once_with(
            notification_ids, sample_user.id
        )

    @pytest.mark.asyncio
    async def test_mark_all_as_read(self, notification_service, mock_notification_repo, sample_user):
        """全通知既読処理のテスト"""
        # Arrange
        mock_notification_repo.mark_all_as_read.return_value = 5

        # Act
        result = await notification_service.mark_all_as_read(sample_user.id)

        # Assert
        assert result == 5
        mock_notification_repo.mark_all_as_read.assert_called_once_with(sample_user.id)

    @pytest.mark.asyncio
    async def test_get_notification_summary(self, notification_service, mock_notification_repo, sample_user, sample_notification):
        """通知サマリー取得のテスト"""
        # Arrange
        mock_notification_repo.get_total_count.return_value = 10
        mock_notification_repo.get_unread_count.return_value = 3
        mock_notification_repo.get_latest_notification.return_value = sample_notification

        # Act
        result = await notification_service.get_notification_summary(sample_user.id)

        # Assert
        assert isinstance(result, NotificationSummary)
        assert result.total_count == 10
        assert result.unread_count == 3
        assert result.latest_notification is not None

    @pytest.mark.asyncio
    async def test_notify_revision_created(self, notification_service, mock_notification_repo, sample_revision, sample_approver):
        """修正案作成通知のテスト"""
        # Arrange
        mock_notification = create_test_notification(
            id=uuid4(),
            recipient_id=sample_approver.id,
            type=NotificationType.REVISION_CREATED,
            title="新しい修正案が作成されました",
            content="修正案が作成されました。"
        )
        mock_notification_repo.create_revision_notification.return_value = mock_notification

        # Act
        result = await notification_service.notify_revision_created(
            revision=sample_revision,
            approvers=[sample_approver]
        )

        # Assert
        assert len(result) == 1
        assert isinstance(result[0], NotificationResponse)
        assert result[0].type == NotificationType.REVISION_CREATED
        mock_notification_repo.create_revision_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_revision_submitted(self, notification_service, mock_notification_repo, sample_revision, sample_approver):
        """修正案提出通知のテスト"""
        # Arrange
        mock_notification = create_test_notification(
            id=uuid4(),
            recipient_id=sample_approver.id,
            type=NotificationType.REVISION_SUBMITTED,
            title="修正案がレビュー依頼されました",
            content="修正案のレビューをお願いします。"
        )
        mock_notification_repo.create_revision_notification.return_value = mock_notification

        # Act
        result = await notification_service.notify_revision_submitted(
            revision=sample_revision,
            approvers=[sample_approver]
        )

        # Assert
        assert len(result) == 1
        assert isinstance(result[0], NotificationResponse)
        assert result[0].type == NotificationType.REVISION_SUBMITTED
        mock_notification_repo.create_revision_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_revision_approved(self, notification_service, mock_notification_repo, sample_revision, sample_approver, sample_user):
        """修正案承認通知のテスト"""
        # Arrange
        mock_notification = create_test_notification(
            id=uuid4(),
            recipient_id=sample_user.id,
            type=NotificationType.REVISION_APPROVED,
            title="修正案が承認されました",
            content="修正案が承認されました。"
        )
        mock_notification_repo.create_revision_notification.return_value = mock_notification

        # Act
        result = await notification_service.notify_revision_approved(
            revision=sample_revision,
            approver=sample_approver,
            recipient_id=sample_user.id
        )

        # Assert
        assert isinstance(result, NotificationResponse)
        assert result.type == NotificationType.REVISION_APPROVED
        mock_notification_repo.create_revision_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_revision_rejected(self, notification_service, mock_notification_repo, sample_revision, sample_approver, sample_user):
        """修正案却下通知のテスト"""
        # Arrange
        mock_notification = create_test_notification(
            id=uuid4(),
            recipient_id=sample_user.id,
            type=NotificationType.REVISION_REJECTED,
            title="修正案が却下されました",
            content="修正案が却下されました。"
        )
        mock_notification_repo.create_revision_notification.return_value = mock_notification

        # Act
        result = await notification_service.notify_revision_rejected(
            revision=sample_revision,
            approver=sample_approver,
            recipient_id=sample_user.id,
            rejection_reason="修正が必要です"
        )

        # Assert
        assert isinstance(result, NotificationResponse)
        assert result.type == NotificationType.REVISION_REJECTED
        mock_notification_repo.create_revision_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_revision_modification_requested(self, notification_service, mock_notification_repo, sample_revision, sample_approver, sample_user):
        """修正依頼通知のテスト"""
        # Arrange
        mock_notification = create_test_notification(
            id=uuid4(),
            recipient_id=sample_user.id,
            type=NotificationType.REVISION_REQUEST,
            title="修正案の修正が依頼されました",
            content="修正案について修正依頼があります。"
        )
        mock_notification_repo.create_revision_notification.return_value = mock_notification

        # Act
        result = await notification_service.notify_revision_modification_requested(
            revision=sample_revision,
            approver=sample_approver,
            recipient_id=sample_user.id,
            instruction_text="タイトルを修正してください"
        )

        # Assert
        assert isinstance(result, NotificationResponse)
        assert result.type == NotificationType.REVISION_REQUEST
        mock_notification_repo.create_revision_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_notify_comment_added(self, notification_service, mock_notification_repo, sample_revision, sample_approver, sample_user):
        """コメント追加通知のテスト"""
        # Arrange
        mock_notification = create_test_notification(
            id=uuid4(),
            recipient_id=sample_user.id,
            type=NotificationType.COMMENT_ADDED,
            title="修正案にコメントが追加されました",
            content="修正案にコメントが追加されました。"
        )
        mock_notification_repo.create_revision_notification.return_value = mock_notification

        # Act
        result = await notification_service.notify_comment_added(
            revision=sample_revision,
            commenter=sample_approver,
            recipient_id=sample_user.id,
            comment_text="良い修正案ですね。"
        )

        # Assert
        assert isinstance(result, NotificationResponse)
        assert result.type == NotificationType.COMMENT_ADDED
        mock_notification_repo.create_revision_notification.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_notifications(self, notification_service, mock_notification_repo, sample_user):
        """古い通知削除のテスト"""
        # Arrange
        mock_notification_repo.delete_old_notifications.return_value = 5

        # Act
        result = await notification_service.cleanup_old_notifications(
            recipient_id=sample_user.id,
            days_old=30
        )

        # Assert
        assert result == 5
        mock_notification_repo.delete_old_notifications.assert_called_once_with(
            sample_user.id, 30
        )


class TestNotificationModel:
    """通知モデルのテストクラス"""

    def test_mark_as_read(self, sample_notification):
        """既読処理のテスト"""
        # Act
        sample_notification.mark_as_read()

        # Assert
        assert sample_notification.is_read is True
        assert sample_notification.read_at is not None
        assert isinstance(sample_notification.read_at, datetime)

    def test_notification_repr(self, sample_notification):
        """通知の文字列表現のテスト"""
        # Act
        repr_str = repr(sample_notification)

        # Assert
        assert "Notification" in repr_str
        assert str(sample_notification.type) in repr_str
        assert str(sample_notification.recipient_id) in repr_str
        assert str(sample_notification.is_read) in repr_str


if __name__ == "__main__":
    pytest.main([__file__])