"""
Test cases for permissions utilities
"""
import pytest
from uuid import uuid4

from app.utils.permissions import (
    PermissionChecker, 
    require_roles, 
    require_supervisor, 
    require_admin, 
    check_revision_permission
)
from fastapi import HTTPException
from app.constants.enums import Role, RevisionStatus
from app.models.user import User
from app.models.revision import Revision


class TestPermissionChecker:
    """Test cases for PermissionChecker utility class"""
    
    def setup_method(self):
        """Setup test data"""
        self.admin_user = User(
            id=uuid4(),
            username="admin",
            email="admin@example.com",
            role=Role.ADMIN,
            is_active=True
        )
        
        self.approver_user = User(
            id=uuid4(),
            username="approver",
            email="approver@example.com",
            role=Role.APPROVER,
            is_active=True
        )
        
        self.supervisor_user = User(
            id=uuid4(),
            username="supervisor",
            email="supervisor@example.com",
            role=Role.SUPERVISOR,
            is_sv=True,
            is_active=True
        )
        
        self.general_user = User(
            id=uuid4(),
            username="general",
            email="general@example.com",
            role=Role.GENERAL,
            is_active=True
        )
        
        self.draft_revision = Revision(
            id=uuid4(),
            target_article_id="ARTICLE001",
            proposer_id=self.general_user.id,
            status=RevisionStatus.DRAFT,
            reason="Test revision"
        )
        
        self.review_revision = Revision(
            id=uuid4(),
            target_article_id="ARTICLE002",
            proposer_id=self.general_user.id,
            status=RevisionStatus.UNDER_REVIEW,
            reason="Test revision under review"
        )
    
    def test_check_user_role_admin(self):
        """Test role checking for admin user"""
        assert PermissionChecker.check_user_role(self.admin_user, [Role.ADMIN])
        assert PermissionChecker.check_user_role(self.admin_user, [Role.ADMIN, Role.APPROVER])
        assert not PermissionChecker.check_user_role(self.admin_user, [Role.GENERAL])
    
    def test_check_user_role_approver(self):
        """Test role checking for approver user"""
        assert PermissionChecker.check_user_role(self.approver_user, [Role.APPROVER])
        assert PermissionChecker.check_user_role(self.approver_user, [Role.ADMIN, Role.APPROVER])
        assert not PermissionChecker.check_user_role(self.approver_user, [Role.ADMIN])
    
    def test_check_user_role_general(self):
        """Test role checking for general user"""
        assert PermissionChecker.check_user_role(self.general_user, [Role.GENERAL])
        assert not PermissionChecker.check_user_role(self.general_user, [Role.ADMIN])
        assert not PermissionChecker.check_user_role(self.general_user, [Role.APPROVER])
    
    def test_check_supervisor_access(self):
        """Test supervisor access checking"""
        assert PermissionChecker.check_supervisor_access(self.supervisor_user)
        assert not PermissionChecker.check_supervisor_access(self.general_user)
        # Approver users have supervisor access according to User.is_supervisor property
        assert PermissionChecker.check_supervisor_access(self.approver_user)
    
    def test_check_admin_access(self):
        """Test admin access checking"""
        assert PermissionChecker.check_admin_access(self.admin_user)
        assert not PermissionChecker.check_admin_access(self.approver_user)
        assert not PermissionChecker.check_admin_access(self.general_user)
    
    def test_check_approval_permission(self):
        """Test approval permission checking"""
        assert PermissionChecker.check_approval_permission(self.approver_user)
        assert PermissionChecker.check_approval_permission(self.admin_user)
        # Assuming general users can't approve by default
        assert not PermissionChecker.check_approval_permission(self.general_user)
    
    def test_can_view_revision_admin(self):
        """Test admin can view all revisions"""
        assert PermissionChecker.can_view_revision(self.admin_user, self.draft_revision)
        assert PermissionChecker.can_view_revision(self.admin_user, self.review_revision)
    
    def test_can_view_revision_proposer(self):
        """Test proposer can view their own revisions"""
        assert PermissionChecker.can_view_revision(self.general_user, self.draft_revision)
        assert PermissionChecker.can_view_revision(self.general_user, self.review_revision)
    
    def test_can_view_revision_approver_non_draft(self):
        """Test approver can view non-draft revisions"""
        assert PermissionChecker.can_view_revision(self.approver_user, self.review_revision)
        assert not PermissionChecker.can_view_revision(self.approver_user, self.draft_revision)
    
    def test_can_view_revision_unauthorized(self):
        """Test unauthorized users cannot view others' draft revisions"""
        other_user = User(
            id=uuid4(),
            username="other",
            email="other@example.com",
            role=Role.GENERAL,
            is_active=True
        )
        assert not PermissionChecker.can_view_revision(other_user, self.draft_revision)
    
    def test_can_edit_revision_admin(self):
        """Test admin can edit all revisions"""
        assert PermissionChecker.can_edit_revision(self.admin_user, self.draft_revision)
        assert PermissionChecker.can_edit_revision(self.admin_user, self.review_revision)
    
    def test_can_edit_revision_proposer_draft(self):
        """Test proposer can edit their own draft revision"""
        assert PermissionChecker.can_edit_revision(self.general_user, self.draft_revision)
    
    def test_can_edit_revision_proposer_under_review(self):
        """Test proposer cannot edit revision under review"""
        assert not PermissionChecker.can_edit_revision(self.general_user, self.review_revision)
    
    def test_can_edit_revision_approver_under_review(self):
        """Test approver can edit revision under review"""
        assert PermissionChecker.can_edit_revision(self.approver_user, self.review_revision)
    
    def test_can_edit_revision_approved(self):
        """Test no one can edit approved revision"""
        approved_revision = Revision(
            id=uuid4(),
            target_article_id="ARTICLE003",
            proposer_id=self.general_user.id,
            status=RevisionStatus.APPROVED,
            reason="Approved revision"
        )
        assert not PermissionChecker.can_edit_revision(self.general_user, approved_revision)
        assert not PermissionChecker.can_edit_revision(self.approver_user, approved_revision)
    
    def test_can_approve_revision_success(self):
        """Test approver can approve revision under review"""
        assert PermissionChecker.can_approve_revision(self.approver_user, self.review_revision)
        assert PermissionChecker.can_approve_revision(self.admin_user, self.review_revision)
    
    def test_can_approve_revision_own_revision(self):
        """Test approver cannot approve their own revision"""
        own_revision = Revision(
            id=uuid4(),
            target_article_id="ARTICLE004",
            proposer_id=self.approver_user.id,
            status=RevisionStatus.UNDER_REVIEW,
            reason="Own revision"
        )
        assert not PermissionChecker.can_approve_revision(self.approver_user, own_revision)
    
    def test_can_approve_revision_general_user(self):
        """Test general user cannot approve revision"""
        assert not PermissionChecker.can_approve_revision(self.general_user, self.review_revision)
    
    def test_can_approve_revision_draft(self):
        """Test cannot approve draft revision"""
        assert not PermissionChecker.can_approve_revision(self.approver_user, self.draft_revision)
    
    def test_can_request_modification_success(self):
        """Test approver can request modification on under review revision"""
        assert PermissionChecker.can_request_modification(self.approver_user, self.review_revision)
    
    def test_can_request_modification_own_revision(self):
        """Test approver cannot request modification on their own revision"""
        own_revision = Revision(
            id=uuid4(),
            target_article_id="ARTICLE005",
            proposer_id=self.approver_user.id,
            status=RevisionStatus.UNDER_REVIEW,
            reason="Own revision"
        )
        assert not PermissionChecker.can_request_modification(self.approver_user, own_revision)
    
    def test_can_request_modification_draft(self):
        """Test cannot request modification on draft"""
        assert not PermissionChecker.can_request_modification(self.approver_user, self.draft_revision)
    
    def test_can_withdraw_revision_proposer(self):
        """Test proposer can withdraw their own draft/under review revision"""
        assert PermissionChecker.can_withdraw_revision(self.general_user, self.draft_revision)
        assert PermissionChecker.can_withdraw_revision(self.general_user, self.review_revision)
    
    def test_can_withdraw_revision_not_proposer(self):
        """Test non-proposer cannot withdraw revision"""
        assert not PermissionChecker.can_withdraw_revision(self.approver_user, self.draft_revision)
    
    def test_can_withdraw_revision_approved(self):
        """Test cannot withdraw approved revision"""
        approved_revision = Revision(
            id=uuid4(),
            target_article_id="ARTICLE006",
            proposer_id=self.general_user.id,
            status=RevisionStatus.APPROVED,
            reason="Approved revision"
        )
        assert not PermissionChecker.can_withdraw_revision(self.general_user, approved_revision)


class TestPermissionDecorators:
    """Test cases for permission decorators"""
    
    def setup_method(self):
        """Setup test data"""
        self.admin_user = User(
            id=uuid4(),
            username="admin",
            email="admin@example.com",
            role=Role.ADMIN,
            is_active=True
        )
        
        self.general_user = User(
            id=uuid4(),
            username="general",
            email="general@example.com",
            role=Role.GENERAL,
            is_active=True
        )
        
        self.draft_revision = Revision(
            id=uuid4(),
            target_article_id="ARTICLE001",
            proposer_id=self.general_user.id,
            status=RevisionStatus.DRAFT,
            reason="Test revision"
        )
    
    @pytest.mark.asyncio
    async def test_require_roles_success(self):
        """Test require_roles decorator allows access with correct role"""
        @require_roles([Role.ADMIN])
        async def test_function(current_user=None):
            return "success"
        
        result = await test_function(current_user=self.admin_user)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_require_roles_unauthorized_no_user(self):
        """Test require_roles decorator raises error when no user provided"""
        @require_roles([Role.ADMIN])
        async def test_function(current_user=None):
            return "success"
        
        with pytest.raises(HTTPException) as exc_info:
            await test_function()
        
        assert exc_info.value.status_code == 401
        assert "Authentication required" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_require_roles_forbidden(self):
        """Test require_roles decorator raises error with wrong role"""
        @require_roles([Role.ADMIN])
        async def test_function(current_user=None):
            return "success"
        
        with pytest.raises(HTTPException) as exc_info:
            await test_function(current_user=self.general_user)
        
        assert exc_info.value.status_code == 403
        assert "Insufficient permissions" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_require_supervisor_success(self):
        """Test require_supervisor decorator allows access for admin"""
        @require_supervisor()
        async def test_function(current_user=None):
            return "success"
        
        result = await test_function(current_user=self.admin_user)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_require_supervisor_unauthorized(self):
        """Test require_supervisor decorator raises error for general user"""
        @require_supervisor()
        async def test_function(current_user=None):
            return "success"
        
        with pytest.raises(HTTPException) as exc_info:
            await test_function(current_user=self.general_user)
        
        assert exc_info.value.status_code == 403
        assert "Supervisor access required" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_require_admin_success(self):
        """Test require_admin decorator allows access for admin"""
        @require_admin()
        async def test_function(current_user=None):
            return "success"
        
        result = await test_function(current_user=self.admin_user)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_check_revision_permission_view_success(self):
        """Test check_revision_permission decorator allows view for admin"""
        @check_revision_permission("view")
        async def test_function(current_user=None, revision=None):
            return "success"
        
        result = await test_function(current_user=self.admin_user, revision=self.draft_revision)
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_check_revision_permission_missing_params(self):
        """Test check_revision_permission decorator raises error when parameters missing"""
        @check_revision_permission("view")
        async def test_function(current_user=None, revision=None):
            return "success"
        
        with pytest.raises(HTTPException) as exc_info:
            await test_function()
        
        assert exc_info.value.status_code == 400
        assert "Missing required parameters" in str(exc_info.value.detail)
    
    @pytest.mark.asyncio
    async def test_check_revision_permission_forbidden(self):
        """Test check_revision_permission decorator raises error when permission denied"""
        @check_revision_permission("approve")
        async def test_function(current_user=None, revision=None):
            return "success"
        
        with pytest.raises(HTTPException) as exc_info:
            await test_function(current_user=self.general_user, revision=self.draft_revision)
        
        assert exc_info.value.status_code == 403
        assert "Permission denied for action: approve" in str(exc_info.value.detail)