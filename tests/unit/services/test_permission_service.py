"""
権限サービスの単体テスト
"""
import pytest
from uuid import uuid4

from app.services.permission import RevisionPermissionService
from app.models.revision import Revision
from app.models.user import User
from app.constants.enums import Role, RevisionStatus
from app.core.security import get_password_hash


@pytest.mark.asyncio
class TestRevisionPermissionService:
    """RevisionPermissionServiceのテストクラス"""
    
    async def test_can_view_revision_as_proposer(self, db_session, test_user, test_revision):
        """提案者として修正案を閲覧できることを確認"""
        
        can_view, reason = RevisionPermissionService.can_view_revision(
            test_user,
            test_revision
        )
        
        assert can_view is True
        assert reason is None
    
    async def test_can_view_revision_as_admin(self, db_session, test_admin, test_revision):
        """管理者として修正案を閲覧できることを確認"""
        
        can_view, reason = RevisionPermissionService.can_view_revision(
            test_admin,
            test_revision
        )
        
        assert can_view is True
        assert reason is None
    
    async def test_cannot_view_revision_as_other_general_user(self, db_session, test_revision):
        """一般ユーザーが他者の修正案を閲覧できないことを確認"""
        
        # 別の一般ユーザーを作成
        other_user_id = uuid4()
        other_user = User(
            id=other_user_id,
            username=f"otheruser_{str(other_user_id)[:8]}",
            email=f"other_{str(other_user_id)[:8]}@example.com",
            hashed_password=get_password_hash("password"),
            full_name="Other User",
            role=Role.GENERAL
        )
        db_session.add(other_user)
        await db_session.commit()
        
        can_view, reason = RevisionPermissionService.can_view_revision(
            other_user,
            test_revision
        )
        
        assert can_view is False
        assert "権限がありません" in reason
    
    async def test_can_edit_revision_draft_as_proposer(self, db_session, test_user, test_revision):
        """提案者がDRAFT状態の修正案を編集できることを確認"""
        
        # DRAFT状態に設定
        test_revision.status = RevisionStatus.DRAFT
        await db_session.commit()
        
        can_edit, reason = RevisionPermissionService.can_edit_revision(
            test_user,
            test_revision
        )
        
        assert can_edit is True
        assert reason is None
    
    async def test_cannot_edit_revision_under_review_as_proposer(self, db_session, test_user, test_revision):
        """提案者がUNDER_REVIEW状態の修正案を編集できないことを確認"""
        
        # UNDER_REVIEW状態に設定
        test_revision.status = RevisionStatus.UNDER_REVIEW
        await db_session.commit()
        
        can_edit, reason = RevisionPermissionService.can_edit_revision(
            test_user,
            test_revision
        )
        
        assert can_edit is False
        assert "承認者のみ編集可能" in reason
    
    async def test_can_edit_revision_under_review_as_approver(self, db_session, test_approver, test_revision):
        """承認者がUNDER_REVIEW状態の修正案を編集できることを確認"""
        
        # UNDER_REVIEW状態に設定
        test_revision.status = RevisionStatus.UNDER_REVIEW
        await db_session.commit()
        
        can_edit, reason = RevisionPermissionService.can_edit_revision(
            test_approver,
            test_revision
        )
        
        assert can_edit is True
        assert reason is None
    
    async def test_can_edit_revision_revision_requested_as_proposer(self, db_session, test_user, test_revision):
        """提案者がREVISION_REQUESTED状態の修正案を編集できることを確認"""
        
        # REVISION_REQUESTED状態に設定
        test_revision.status = RevisionStatus.REVISION_REQUESTED
        await db_session.commit()
        
        can_edit, reason = RevisionPermissionService.can_edit_revision(
            test_user,
            test_revision
        )
        
        assert can_edit is True
        assert reason is None
    
    async def test_cannot_edit_revision_approved(self, db_session, test_user, test_revision):
        """承認済み修正案を編集できないことを確認"""
        
        # APPROVED状態に設定
        test_revision.status = RevisionStatus.APPROVED
        await db_session.commit()
        
        can_edit, reason = RevisionPermissionService.can_edit_revision(
            test_user,
            test_revision
        )
        
        assert can_edit is False
        assert "編集できません" in reason
    
    async def test_can_approve_revision_as_approver(self, db_session, test_approver, test_revision):
        """承認者が修正案を承認できることを確認"""
        
        # UNDER_REVIEW状態に設定
        test_revision.status = RevisionStatus.UNDER_REVIEW
        await db_session.commit()
        
        can_approve, reason = RevisionPermissionService.can_approve_revision(
            test_approver,
            test_revision
        )
        
        assert can_approve is True
        assert reason is None
    
    async def test_can_approve_revision_as_supervisor(self, db_session, test_supervisor, test_revision):
        """スーパーバイザーが修正案を承認できることを確認"""
        
        # UNDER_REVIEW状態に設定
        test_revision.status = RevisionStatus.UNDER_REVIEW
        await db_session.commit()
        
        can_approve, reason = RevisionPermissionService.can_approve_revision(
            test_supervisor,
            test_revision
        )
        
        assert can_approve is True
        assert reason is None
    
    async def test_cannot_approve_revision_as_general_user(self, db_session, test_user, test_revision):
        """一般ユーザーが修正案を承認できないことを確認"""
        
        # UNDER_REVIEW状態に設定
        test_revision.status = RevisionStatus.UNDER_REVIEW
        await db_session.commit()
        
        can_approve, reason = RevisionPermissionService.can_approve_revision(
            test_user,
            test_revision
        )
        
        assert can_approve is False
        assert "承認権限がありません" in reason
    
    async def test_cannot_approve_revision_draft_state(self, db_session, test_approver, test_revision):
        """DRAFT状態の修正案を承認できないことを確認"""
        
        # DRAFT状態のまま
        test_revision.status = RevisionStatus.DRAFT
        await db_session.commit()
        
        can_approve, reason = RevisionPermissionService.can_approve_revision(
            test_approver,
            test_revision
        )
        
        assert can_approve is False
        assert "承認できません" in reason
    
    async def test_can_delete_revision_as_proposer(self, db_session, test_user, test_revision):
        """提案者が修正案を削除できることを確認"""
        
        can_delete, reason = RevisionPermissionService.can_delete_revision(
            test_user,
            test_revision
        )
        
        assert can_delete is True
        assert reason is None
    
    async def test_can_delete_revision_as_admin(self, db_session, test_admin, test_revision):
        """管理者が修正案を削除できることを確認"""
        
        can_delete, reason = RevisionPermissionService.can_delete_revision(
            test_admin,
            test_revision
        )
        
        assert can_delete is True
        assert reason is None
    
    async def test_cannot_delete_revision_as_other_user(self, db_session, test_revision):
        """他のユーザーが修正案を削除できないことを確認"""
        
        # 別のユーザーを作成
        other_user_id = uuid4()
        other_user = User(
            id=other_user_id,
            username=f"otheruser_{str(other_user_id)[:8]}",
            email=f"other_{str(other_user_id)[:8]}@example.com",
            hashed_password=get_password_hash("password"),
            role=Role.GENERAL
        )
        db_session.add(other_user)
        await db_session.commit()
        
        can_delete, reason = RevisionPermissionService.can_delete_revision(
            other_user,
            test_revision
        )
        
        assert can_delete is False
        assert "提案者のみ可能" in reason
    
    async def test_cannot_delete_approved_revision(self, db_session, test_user, test_revision):
        """承認済み修正案を削除できないことを確認"""
        
        # APPROVED状態に設定
        test_revision.status = RevisionStatus.APPROVED
        await db_session.commit()
        
        can_delete, reason = RevisionPermissionService.can_delete_revision(
            test_user,
            test_revision
        )
        
        assert can_delete is False
        assert "下書き状態" in reason
    
    async def test_can_request_modification_as_approver(self, db_session, test_approver, test_revision):
        """承認者が修正指示を出せることを確認"""
        
        # UNDER_REVIEW状態に設定
        test_revision.status = RevisionStatus.UNDER_REVIEW
        await db_session.commit()
        
        can_request, reason = RevisionPermissionService.can_request_modification(
            test_approver,
            test_revision
        )
        
        assert can_request is True
        assert reason is None
    
    async def test_cannot_request_modification_as_proposer(self, db_session, test_user, test_revision):
        """提案者が修正指示を出せないことを確認"""
        
        # UNDER_REVIEW状態に設定
        test_revision.status = RevisionStatus.UNDER_REVIEW
        await db_session.commit()
        
        can_request, reason = RevisionPermissionService.can_request_modification(
            test_user,
            test_revision
        )
        
        assert can_request is False
        assert "修正指示権限がありません" in reason