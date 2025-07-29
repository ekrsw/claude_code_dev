"""
承認サービスの単体テスト
"""
import pytest
from uuid import uuid4

from app.services.approval import ApprovalService
from app.services.notification import NotificationService
from app.models.revision import Revision
from app.schemas.approval import ApprovalRequest, RejectionRequest, ModificationRequest
from app.constants.enums import RevisionStatus, Role
from app.core.exceptions import InvalidStateError, AuthorizationError, NotFoundError


@pytest.mark.asyncio
class TestApprovalService:
    """ApprovalServiceのテストクラス"""
    
    async def test_approve_revision_success(self, db_session, test_approver, test_article, test_user):
        """修正案承認が成功することを確認"""
        notification_service = NotificationService(db_session)
        approval_service = ApprovalService(db_session, notification_service)
        
        # UNDER_REVIEW状態の修正案を作成
        revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=test_user.id,
            status=RevisionStatus.UNDER_REVIEW,
            reason="承認テスト用の修正案です。内容を改善するために作成しました。",
            before_title=test_article.title,
            after_title="承認テスト修正案",
            before_answer=test_article.answer,
            after_answer="承認テスト内容",
            version=1
        )
        db_session.add(revision)
        await db_session.commit()
        
        approved_revision = await approval_service.approve_revision(
            revision.id,
            test_approver.id,
            test_approver.role,
            "承認します。良い修正案です。"
        )
        
        assert approved_revision is not None
        assert approved_revision.status == RevisionStatus.APPROVED
        assert approved_revision.approver_id == test_approver.id
        assert approved_revision.approval_comment == "承認します。良い修正案です。"
        assert approved_revision.approved_at is not None
    
    async def test_approve_revision_invalid_state(self, db_session, test_approver, test_article, test_user):
        """無効な状態の修正案承認が失敗することを確認"""
        notification_service = NotificationService(db_session)
        approval_service = ApprovalService(db_session, notification_service)
        
        # DRAFT状態の修正案を作成
        revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=test_user.id,
            status=RevisionStatus.DRAFT,
            reason="無効承認テスト用の修正案です。内容を改善するために作成しました。",
            before_title=test_article.title,
            after_title="無効承認テスト",
            before_answer=test_article.answer,
            after_answer="テスト内容",
            version=1
        )
        db_session.add(revision)
        await db_session.commit()
        
        with pytest.raises(InvalidStateError) as exc_info:
            await approval_service.approve_revision(
                revision.id,
                test_approver.id,
                test_approver.role,
                "承認"
            )
        
        assert "Cannot approve" in str(exc_info.value)
    
    async def test_approve_revision_unauthorized(self, db_session, test_user, test_article):
        """権限のないユーザーによる承認が失敗することを確認"""
        notification_service = NotificationService(db_session)
        approval_service = ApprovalService(db_session, notification_service)
        
        # UNDER_REVIEW状態の修正案を作成
        revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=test_user.id,
            status=RevisionStatus.UNDER_REVIEW,
            reason="権限なし承認テスト用の修正案です。内容を改善するために作成しました。",
            before_title=test_article.title,
            after_title="権限なし承認テスト",
            before_answer=test_article.answer,
            after_answer="テスト内容",
            version=1
        )
        db_session.add(revision)
        await db_session.commit()
        
        with pytest.raises(AuthorizationError):
            await approval_service.approve_revision(
                revision.id,
                test_user.id,  # 一般ユーザーには承認権限がない
                test_user.role,
                "承認"
            )
    
    async def test_reject_revision_success(self, db_session, test_approver, test_article, test_user):
        """修正案却下が成功することを確認"""
        notification_service = NotificationService(db_session)
        approval_service = ApprovalService(db_session, notification_service)
        
        # UNDER_REVIEW状態の修正案を作成
        revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=test_user.id,
            status=RevisionStatus.UNDER_REVIEW,
            reason="却下テスト用の修正案です。内容を改善するために作成しました。",
            before_title=test_article.title,
            after_title="却下テスト修正案",
            before_answer=test_article.answer,
            after_answer="却下テスト内容",
            version=1
        )
        db_session.add(revision)
        await db_session.commit()
        
        rejected_revision = await approval_service.reject_revision(
            revision.id,
            test_approver.id,
            test_approver.role,
            "内容が不適切です。詳細な理由を説明してください。"
        )
        
        assert rejected_revision is not None
        assert rejected_revision.status == RevisionStatus.REJECTED
        assert rejected_revision.approver_id == test_approver.id
        assert rejected_revision.approval_comment == "内容が不適切です。詳細な理由を説明してください。"
        assert rejected_revision.approved_at is not None
    
    async def test_request_modification_success(self, db_session, test_approver, test_article, test_user):
        """修正指示が成功することを確認"""
        notification_service = NotificationService(db_session)
        approval_service = ApprovalService(db_session, notification_service)
        
        # UNDER_REVIEW状態の修正案を作成
        revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=test_user.id,
            status=RevisionStatus.UNDER_REVIEW,
            reason="修正指示テスト用の修正案です。内容を改善するために作成しました。",
            before_title=test_article.title,
            after_title="修正指示テスト",
            before_answer=test_article.answer,
            after_answer="修正指示内容",
            version=1
        )
        db_session.add(revision)
        await db_session.commit()
        
        modified_revision = await approval_service.request_modification(
            revision.id,
            test_approver.id,
            test_approver.role,
            "タイトルをより具体的にしてください。",
            ["title", "answer"],
            "normal"
        )
        
        assert modified_revision is not None
        assert modified_revision.status == RevisionStatus.REVISION_REQUESTED
    
    async def test_withdraw_revision_by_proposer(self, db_session, test_user, test_article):
        """提案者による修正案取り下げが成功することを確認"""
        notification_service = NotificationService(db_session)
        approval_service = ApprovalService(db_session, notification_service)
        
        # DRAFT状態の修正案を作成
        revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=test_user.id,
            status=RevisionStatus.DRAFT,
            reason="取り下げテスト用の修正案です。内容を改善するために作成しました。",
            before_title=test_article.title,
            after_title="取り下げテスト",
            before_answer=test_article.answer,
            after_answer="取り下げ内容",
            version=1
        )
        db_session.add(revision)
        await db_session.commit()
        
        withdrawn_revision = await approval_service.withdraw_revision(
            revision.id,
            test_user.id,
            test_user.role
        )
        
        assert withdrawn_revision is not None
        assert withdrawn_revision.status == RevisionStatus.WITHDRAWN
    
    async def test_withdraw_revision_unauthorized(self, db_session, test_article, test_user):
        """権限のないユーザーによる取り下げが失敗することを確認"""
        notification_service = NotificationService(db_session)
        approval_service = ApprovalService(db_session, notification_service)
        
        # 別のユーザーの修正案を作成
        other_user_id = uuid4()
        revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=other_user_id,
            status=RevisionStatus.DRAFT,
            reason="他者取り下げテスト",
            before_title=test_article.title,
            after_title="テストタイトル",
            before_answer=test_article.answer,
            after_answer="テスト内容",
            version=1
        )
        db_session.add(revision)
        await db_session.commit()
        
        with pytest.raises(AuthorizationError):
            await approval_service.withdraw_revision(
                revision.id,
                test_user.id,  # 他人の修正案は取り下げできない
                test_user.role
            )
    
    async def test_get_approval_history(self, db_session, test_approver, test_article, test_user):
        """承認履歴取得が成功することを確認"""
        notification_service = NotificationService(db_session)
        approval_service = ApprovalService(db_session, notification_service)
        
        # UNDER_REVIEW状態の修正案を作成
        revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=test_user.id,
            status=RevisionStatus.UNDER_REVIEW,
            reason="履歴テスト用の修正案です。内容を改善するために作成しました。",
            before_title=test_article.title,
            after_title="履歴テスト",
            before_answer=test_article.answer,
            after_answer="履歴テスト内容",
            version=1
        )
        db_session.add(revision)
        await db_session.commit()
        
        # 承認を実行
        await approval_service.approve_revision(
            revision.id,
            test_approver.id,
            test_approver.role,
            "承認します。良い修正案です。"
        )
        
        # 履歴を取得
        history = await approval_service.get_approval_history(
            revision.id,
            test_approver.id,
            test_approver.role
        )
        
        assert len(history) >= 1
        assert any(h.action == "approved" for h in history)
        assert any(h.actor_id == test_approver.id for h in history)
    
    async def test_get_approval_status_counts(self, db_session, test_approver, test_article, test_user):
        """承認ステータス集計が成功することを確認"""
        notification_service = NotificationService(db_session)
        approval_service = ApprovalService(db_session, notification_service)
        
        # 複数の修正案を異なる状態で作成
        statuses = [RevisionStatus.DRAFT, RevisionStatus.UNDER_REVIEW, RevisionStatus.APPROVED]
        for i, status in enumerate(statuses):
            revision = Revision(
                id=uuid4(),
                target_article_id=test_article.article_id,
                proposer_id=test_user.id,
                status=status,
                reason=f"集計テスト{i}用の修正案です。内容を改善するために作成しました。",
                before_title=test_article.title,
                after_title=f"集計テスト{i}",
                before_answer=test_article.answer,
                after_answer=f"内容{i}",
                version=1
            )
            if status == RevisionStatus.APPROVED:
                revision.approver_id = test_approver.id
            db_session.add(revision)
        await db_session.commit()
        
        # 集計を取得
        counts = await approval_service.get_revision_status_counts(test_approver.role)
        
        assert counts is not None
        total_count = sum(counts.values())
        assert total_count >= 3
        assert counts.get("under_review", 0) >= 1  # UNDER_REVIEW
        assert counts.get("approved", 0) >= 1  # APPROVED
    
    async def test_get_pending_approvals_for_approver(self, db_session, test_approver, test_article, test_user):
        """承認者の承認待ち修正案取得が成功することを確認"""
        notification_service = NotificationService(db_session)
        approval_service = ApprovalService(db_session, notification_service)
        
        # UNDER_REVIEW状態の修正案を作成
        revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=test_user.id,
            status=RevisionStatus.UNDER_REVIEW,
            reason="承認待ちテスト用の修正案です。内容を改善するために作成しました。",
            before_title=test_article.title,
            after_title="承認待ちテスト",
            before_answer=test_article.answer,
            after_answer="承認待ち内容",
            version=1
        )
        db_session.add(revision)
        await db_session.commit()
        
        # 承認待ちの修正案を取得
        pending_revisions = await approval_service.get_pending_approvals_for_approver(
            test_approver.id,
            skip=0,
            limit=10
        )
        
        assert len(pending_revisions) >= 1
        assert all(r.status == RevisionStatus.UNDER_REVIEW for r in pending_revisions)