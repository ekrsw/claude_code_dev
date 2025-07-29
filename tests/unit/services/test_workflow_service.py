"""
ワークフローサービスの単体テスト
"""
import pytest
from uuid import uuid4
from datetime import datetime

from app.services.workflow import WorkflowService
from app.services.notification import NotificationService
from app.models.revision import Revision
from app.constants.enums import RevisionStatus, Role
from app.core.exceptions import InvalidStateError, AuthorizationError


@pytest.mark.asyncio
class TestWorkflowService:
    """WorkflowServiceのテストクラス"""
    
    async def test_transition_to_under_review(self, db_session, test_revision, test_user):
        """DRAFT → UNDER_REVIEWの状態遷移が成功することを確認"""
        workflow_service = WorkflowService(db_session)
        
        # DRAFT状態に設定
        test_revision.status = RevisionStatus.DRAFT
        await db_session.commit()
        
        updated_revision = await workflow_service.transition_status(
            test_revision.id,
            RevisionStatus.UNDER_REVIEW,
            test_user.id,
            test_user.role
        )
        
        assert updated_revision is not None
        
        # 状態が変更されたことを確認
        updated_revision = await db_session.get(Revision, test_revision.id)
        assert updated_revision.status == RevisionStatus.UNDER_REVIEW
    
    async def test_transition_to_approved(self, db_session, test_approver, test_article):
        """UNDER_REVIEW → APPROVEDの状態遷移が成功することを確認"""
        workflow_service = WorkflowService(db_session)
        
        # UNDER_REVIEW状態の修正案を作成
        revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=uuid4(),
            status=RevisionStatus.UNDER_REVIEW,
            reason="承認テスト用の修正案です。内容を改善するために作成しました。",
            before_title=test_article.title,
            after_title="承認テスト",
            before_answer=test_article.answer,
            after_answer="承認内容",
            version=1
        )
        db_session.add(revision)
        await db_session.commit()
        
        updated_revision = await workflow_service.transition_status(
            revision.id,
            RevisionStatus.APPROVED,
            test_approver.id,
            test_approver.role
        )
        
        assert updated_revision is not None
        
        # 状態が変更されたことを確認
        updated_revision = await db_session.get(Revision, revision.id)
        assert updated_revision.status == RevisionStatus.APPROVED
        assert updated_revision.approver_id == test_approver.id
        assert updated_revision.approved_at is not None
    
    async def test_transition_to_rejected(self, db_session, test_approver, test_article):
        """UNDER_REVIEW → REJECTEDの状態遷移が成功することを確認"""
        workflow_service = WorkflowService(db_session)
        
        # UNDER_REVIEW状態の修正案を作成
        revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=uuid4(),
            status=RevisionStatus.UNDER_REVIEW,
            reason="却下テスト用の修正案です。内容を改善するために作成しました。",
            before_title=test_article.title,
            after_title="却下テスト",
            before_answer=test_article.answer,
            after_answer="却下内容",
            version=1
        )
        db_session.add(revision)
        await db_session.commit()
        
        updated_revision = await workflow_service.transition_status(
            revision.id,
            RevisionStatus.REJECTED,
            test_approver.id,
            test_approver.role
        )
        
        assert updated_revision is not None
        
        # 状態が変更されたことを確認
        updated_revision = await db_session.get(Revision, revision.id)
        assert updated_revision.status == RevisionStatus.REJECTED
        assert updated_revision.approver_id == test_approver.id
    
    async def test_invalid_state_transition(self, db_session, test_user, test_article):
        """無効な状態遷移が失敗することを確認"""
        workflow_service = WorkflowService(db_session)
        
        # APPROVED状態の修正案を作成
        revision = Revision(
            id=uuid4(),
            target_article_id=test_article.article_id,
            proposer_id=test_user.id,
            status=RevisionStatus.APPROVED,
            reason="無効遷移テスト用の修正案です。承認済みの状態です。",
            before_title=test_article.title,
            after_title="無効遷移テスト",
            before_answer=test_article.answer,
            after_answer="承認済み内容",
            version=1
        )
        db_session.add(revision)
        await db_session.commit()
        
        # 承認済みからDRAFTに戻すことはできない
        with pytest.raises(AuthorizationError):
            await workflow_service.transition_status(
                revision.id,
                RevisionStatus.DRAFT,
                test_user.id,
                test_user.role
            )
    
    async def test_can_transition_draft_to_under_review(self, db_session):
        """DRAFT → UNDER_REVIEWの遷移可能性チェック"""
        workflow_service = WorkflowService(db_session)
        
        can_transition = workflow_service.can_transition(
            RevisionStatus.DRAFT,
            RevisionStatus.UNDER_REVIEW
        )
        
        assert can_transition is True
    
    async def test_can_transition_under_review_to_approved(self, db_session):
        """UNDER_REVIEW → APPROVEDの遷移可能性チェック"""
        workflow_service = WorkflowService(db_session)
        
        can_transition = workflow_service.can_transition(
            RevisionStatus.UNDER_REVIEW,
            RevisionStatus.APPROVED
        )
        
        assert can_transition is True
    
    async def test_cannot_transition_approved_to_draft(self, db_session):
        """APPROVED → DRAFTの遷移不可能性チェック"""
        workflow_service = WorkflowService(db_session)
        
        can_transition = workflow_service.can_transition(
            RevisionStatus.APPROVED,
            RevisionStatus.DRAFT
        )
        
        assert can_transition is False
    
    async def test_get_next_possible_statuses_from_draft(self, db_session):
        """DRAFT状態から可能な次の状態一覧を取得"""
        workflow_service = WorkflowService(db_session)
        
        next_statuses = workflow_service.get_next_possible_statuses(
            RevisionStatus.DRAFT
        )
        
        expected_statuses = [RevisionStatus.UNDER_REVIEW, RevisionStatus.WITHDRAWN]
        assert set(next_statuses) == set(expected_statuses)
    
    async def test_get_next_possible_statuses_from_under_review(self, db_session):
        """UNDER_REVIEW状態から可能な次の状態一覧を取得"""
        workflow_service = WorkflowService(db_session)
        
        next_statuses = workflow_service.get_next_possible_statuses(
            RevisionStatus.UNDER_REVIEW
        )
        
        expected_statuses = [
            RevisionStatus.APPROVED,
            RevisionStatus.REJECTED,
            RevisionStatus.REVISION_REQUESTED
        ]
        assert set(next_statuses) == set(expected_statuses)
    
    async def test_check_user_permission_for_transition_as_proposer(self, db_session, test_user):
        """提案者による状態遷移権限チェック"""
        workflow_service = WorkflowService(db_session)
        
        # 提案者はDRAFT → UNDER_REVIEWの遷移ができる
        has_permission = workflow_service.check_user_permission_for_transition(
            test_user.role,
            RevisionStatus.DRAFT,
            RevisionStatus.UNDER_REVIEW
        )
        
        assert has_permission is True
        
        # 提案者はUNDER_REVIEW → APPROVEDの遷移はできない
        has_permission = workflow_service.check_user_permission_for_transition(
            test_user.role,
            RevisionStatus.UNDER_REVIEW,
            RevisionStatus.APPROVED
        )
        
        assert has_permission is False
    
    async def test_check_user_permission_for_transition_as_approver(self, db_session, test_approver):
        """承認者による状態遷移権限チェック"""
        workflow_service = WorkflowService(db_session)
        
        # 承認者はUNDER_REVIEW → APPROVEDの遷移ができる
        has_permission = workflow_service.check_user_permission_for_transition(
            test_approver.role,
            RevisionStatus.UNDER_REVIEW,
            RevisionStatus.APPROVED
        )
        
        assert has_permission is True
        
        # 承認者はUNDER_REVIEW → REJECTEDの遷移もできる
        has_permission = workflow_service.check_user_permission_for_transition(
            test_approver.role,
            RevisionStatus.UNDER_REVIEW,
            RevisionStatus.REJECTED
        )
        
        assert has_permission is True
    
    async def test_get_workflow_history(self, db_session, test_revision, test_user, test_approver):
        """修正案のワークフロー履歴取得"""
        workflow_service = WorkflowService(db_session)
        
        # 複数の状態遷移を実行
        await workflow_service.transition_status(
            test_revision.id,
            RevisionStatus.UNDER_REVIEW,
            test_user.id,
            test_user.role
        )
        
        await workflow_service.transition_status(
            test_revision.id,
            RevisionStatus.APPROVED,
            test_approver.id,
            test_approver.role
        )
        
        # 履歴を取得
        history = await workflow_service.get_workflow_history(test_revision.id)
        
        assert len(history) >= 2
        assert any(h['to_status'] == RevisionStatus.UNDER_REVIEW for h in history)
        assert any(h['to_status'] == RevisionStatus.APPROVED for h in history)
    
    async def test_is_final_status(self, db_session):
        """最終状態の判定"""
        workflow_service = WorkflowService(db_session)
        
        # 最終状態
        assert workflow_service.is_final_status(RevisionStatus.APPROVED) is True
        assert workflow_service.is_final_status(RevisionStatus.REJECTED) is True
        assert workflow_service.is_final_status(RevisionStatus.WITHDRAWN) is True
        
        # 非最終状態
        assert workflow_service.is_final_status(RevisionStatus.DRAFT) is False
        assert workflow_service.is_final_status(RevisionStatus.UNDER_REVIEW) is False
        assert workflow_service.is_final_status(RevisionStatus.REVISION_REQUESTED) is False