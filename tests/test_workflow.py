"""
Tests for workflow functionality
"""
import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4

from app.services.workflow import WorkflowService
from app.services.permission import RevisionPermissionService
from app.constants.enums import RevisionStatus, Role
from app.models.revision import Revision
from app.models.user import User


class TestWorkflowService:
    """Test cases for WorkflowService"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.mock_db = Mock()
        self.service = WorkflowService(self.mock_db)
        self.service.revision_repo = Mock()
        
        self.revision_id = uuid4()
        self.user_id = uuid4()
        
        self.sample_revision = Revision(
            id=self.revision_id,
            proposer_id=self.user_id,
            status=RevisionStatus.DRAFT
        )
    
    def test_validate_state_transition_valid(self):
        """Test valid state transitions"""
        # Draft -> UnderReview
        assert self.service.validate_state_transition(
            RevisionStatus.DRAFT, RevisionStatus.UNDER_REVIEW
        ) is True
        
        # UnderReview -> Approved
        assert self.service.validate_state_transition(
            RevisionStatus.UNDER_REVIEW, RevisionStatus.APPROVED
        ) is True
        
        # UnderReview -> RevisionRequested
        assert self.service.validate_state_transition(
            RevisionStatus.UNDER_REVIEW, RevisionStatus.REVISION_REQUESTED
        ) is True
    
    def test_validate_state_transition_invalid(self):
        """Test invalid state transitions"""
        # Draft -> Approved (should go through review first)
        assert self.service.validate_state_transition(
            RevisionStatus.DRAFT, RevisionStatus.APPROVED
        ) is False
        
        # Approved -> Draft (can't go back)
        assert self.service.validate_state_transition(
            RevisionStatus.APPROVED, RevisionStatus.DRAFT
        ) is False
    
    def test_get_allowed_transitions(self):
        """Test getting allowed transitions from current status"""
        draft_transitions = self.service.get_allowed_transitions(RevisionStatus.DRAFT)
        assert RevisionStatus.UNDER_REVIEW in draft_transitions
        assert RevisionStatus.WITHDRAWN in draft_transitions
        
        review_transitions = self.service.get_allowed_transitions(RevisionStatus.UNDER_REVIEW)
        assert RevisionStatus.APPROVED in review_transitions
        assert RevisionStatus.REJECTED in review_transitions
        assert RevisionStatus.REVISION_REQUESTED in review_transitions
    
    def test_check_transition_permission_proposer_draft_to_review(self):
        """Test proposer can submit draft for review"""
        can_transition, reason = self.service._check_transition_permission(
            self.sample_revision,
            RevisionStatus.UNDER_REVIEW,
            self.user_id,  # Same as proposer
            Role.GENERAL
        )
        assert can_transition is True
        assert reason is None
    
    def test_check_transition_permission_non_proposer_draft(self):
        """Test non-proposer cannot submit draft"""
        other_user_id = uuid4()
        can_transition, reason = self.service._check_transition_permission(
            self.sample_revision,
            RevisionStatus.UNDER_REVIEW,
            other_user_id,  # Different from proposer
            Role.GENERAL
        )
        assert can_transition is False
        assert "提案者のみ" in reason
    
    def test_check_transition_permission_admin_always_allowed(self):
        """Test admin can always transition"""
        other_user_id = uuid4()
        can_transition, reason = self.service._check_transition_permission(
            self.sample_revision,
            RevisionStatus.UNDER_REVIEW,
            other_user_id,
            Role.ADMIN
        )
        assert can_transition is True
        assert reason is None
    
    def test_is_terminal_status(self):
        """Test terminal status identification"""
        assert self.service.is_terminal_status(RevisionStatus.APPROVED) is True
        assert self.service.is_terminal_status(RevisionStatus.REJECTED) is True
        assert self.service.is_terminal_status(RevisionStatus.WITHDRAWN) is True
        
        assert self.service.is_terminal_status(RevisionStatus.DRAFT) is False
        assert self.service.is_terminal_status(RevisionStatus.UNDER_REVIEW) is False
    
    def test_get_status_display_name(self):
        """Test status display names"""
        assert self.service.get_status_display_name(RevisionStatus.DRAFT) == "下書き"
        assert self.service.get_status_display_name(RevisionStatus.UNDER_REVIEW) == "レビュー中"
        assert self.service.get_status_display_name(RevisionStatus.APPROVED) == "承認済み"


class TestRevisionPermissionService:
    """Test cases for RevisionPermissionService"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.user_id = uuid4()
        self.other_user_id = uuid4()
        
        self.proposer = User(
            id=self.user_id,
            role=Role.GENERAL,
            username="proposer",
            email="proposer@test.com"
        )
        
        self.approver = User(
            id=self.other_user_id,
            role=Role.APPROVER,
            username="approver",
            email="approver@test.com"
        )
        
        self.admin = User(
            id=uuid4(),
            role=Role.ADMIN,
            username="admin",
            email="admin@test.com"
        )
        
        self.revision = Revision(
            id=uuid4(),
            proposer_id=self.user_id,
            status=RevisionStatus.DRAFT
        )
    
    def test_can_view_revision_proposer(self):
        """Test proposer can view their revision"""
        can_view, reason = RevisionPermissionService.can_view_revision(
            self.proposer, self.revision
        )
        assert can_view is True
        assert reason is None
    
    def test_can_view_revision_admin(self):
        """Test admin can view any revision"""
        can_view, reason = RevisionPermissionService.can_view_revision(
            self.admin, self.revision
        )
        assert can_view is True
        assert reason is None
    
    def test_can_edit_revision_draft_proposer(self):
        """Test proposer can edit draft revision"""
        can_edit, reason = RevisionPermissionService.can_edit_revision(
            self.proposer, self.revision
        )
        assert can_edit is True
        assert reason is None
    
    def test_can_edit_revision_draft_non_proposer(self):
        """Test non-proposer cannot edit draft revision"""
        other_user = User(
            id=uuid4(),
            role=Role.GENERAL,
            username="other",
            email="other@test.com"
        )
        can_edit, reason = RevisionPermissionService.can_edit_revision(
            other_user, self.revision
        )
        assert can_edit is False
        assert "提案者のみ" in reason
    
    def test_can_approve_revision_approver(self):
        """Test approver can approve revision under review"""
        self.revision.status = RevisionStatus.UNDER_REVIEW
        can_approve, reason = RevisionPermissionService.can_approve_revision(
            self.approver, self.revision
        )
        assert can_approve is True
        assert reason is None
    
    def test_can_approve_revision_general_user(self):
        """Test general user cannot approve revision"""
        self.revision.status = RevisionStatus.UNDER_REVIEW
        can_approve, reason = RevisionPermissionService.can_approve_revision(
            self.proposer, self.revision
        )
        assert can_approve is False
        assert "承認権限がありません" in reason
    
    def test_get_available_actions_draft_proposer(self):
        """Test available actions for draft revision proposer"""
        actions = RevisionPermissionService.get_available_actions(
            self.proposer, self.revision
        )
        assert "view" in actions
        assert "edit" in actions
        assert "delete" in actions
        assert "submit" in actions
        assert "withdraw" in actions
        assert "approve" not in actions
    
    def test_get_available_actions_under_review_approver(self):
        """Test available actions for approver on revision under review"""
        self.revision.status = RevisionStatus.UNDER_REVIEW
        actions = RevisionPermissionService.get_available_actions(
            self.approver, self.revision
        )
        assert "view" in actions
        assert "edit" in actions
        assert "approve" in actions
        assert "reject" in actions
        assert "request_modification" in actions
        assert "submit" not in actions


if __name__ == "__main__":
    pytest.main([__file__])