"""
Tests for approval functionality
"""
import pytest
from unittest.mock import Mock, AsyncMock
from uuid import uuid4
from datetime import datetime

from app.services.approval import ApprovalService
from app.constants.enums import RevisionStatus, Role, ApprovalAction
from app.models.revision import Revision
from app.models.user import User
from app.models.approval import ApprovalHistory
from app.core.exceptions import NotFoundError, AuthorizationError, InvalidStateError


class TestApprovalService:
    """Test cases for ApprovalService"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.mock_db = Mock()
        self.service = ApprovalService(self.mock_db)
        self.service.approval_repo = Mock()
        self.service.revision_repo = Mock()
        
        self.revision_id = uuid4()
        self.approver_id = uuid4()
        self.proposer_id = uuid4()
        
        self.sample_revision = Revision(
            id=self.revision_id,
            proposer_id=self.proposer_id,
            status=RevisionStatus.UNDER_REVIEW
        )
    
    @pytest.mark.asyncio
    async def test_approve_revision_success(self):
        """Test successful revision approval"""
        # Setup
        self.service.revision_repo.get_by_id = AsyncMock(return_value=self.sample_revision)
        self.service.revision_repo.update = AsyncMock()
        self.service.approval_repo.create = AsyncMock()
        
        # Execute
        result = await self.service.approve_revision(
            revision_id=self.revision_id,
            approver_id=self.approver_id,
            approver_role=Role.APPROVER,
            comment="Looks good!"
        )
        
        # Verify
        assert result.status == RevisionStatus.APPROVED
        assert result.approver_id == self.approver_id
        assert result.approval_comment == "Looks good!"
        self.service.revision_repo.update.assert_called_once()
        self.service.approval_repo.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_approve_revision_not_found(self):
        """Test approval when revision not found"""
        # Setup
        self.service.revision_repo.get_by_id = AsyncMock(return_value=None)
        
        # Execute & Verify
        with pytest.raises(NotFoundError):
            await self.service.approve_revision(
                revision_id=self.revision_id,
                approver_id=self.approver_id,
                approver_role=Role.APPROVER
            )
    
    @pytest.mark.asyncio
    async def test_approve_revision_invalid_state(self):
        """Test approval when revision in invalid state"""
        # Setup
        self.sample_revision.status = RevisionStatus.APPROVED
        self.service.revision_repo.get_by_id = AsyncMock(return_value=self.sample_revision)
        
        # Execute & Verify
        with pytest.raises(InvalidStateError):
            await self.service.approve_revision(
                revision_id=self.revision_id,
                approver_id=self.approver_id,
                approver_role=Role.APPROVER
            )
    
    @pytest.mark.asyncio
    async def test_approve_revision_insufficient_permissions(self):
        """Test approval with insufficient permissions"""
        # Setup
        self.service.revision_repo.get_by_id = AsyncMock(return_value=self.sample_revision)
        
        # Execute & Verify
        with pytest.raises(AuthorizationError):
            await self.service.approve_revision(
                revision_id=self.revision_id,
                approver_id=self.approver_id,
                approver_role=Role.GENERAL  # General user cannot approve
            )
    
    @pytest.mark.asyncio
    async def test_reject_revision_success(self):
        """Test successful revision rejection"""
        # Setup
        self.service.revision_repo.get_by_id = AsyncMock(return_value=self.sample_revision)
        self.service.revision_repo.update = AsyncMock()
        self.service.approval_repo.create = AsyncMock()
        
        comment = "Needs improvement"
        
        # Execute
        result = await self.service.reject_revision(
            revision_id=self.revision_id,
            rejector_id=self.approver_id,
            rejector_role=Role.APPROVER,
            comment=comment
        )
        
        # Verify
        assert result.status == RevisionStatus.REJECTED
        assert result.approver_id == self.approver_id
        assert result.approval_comment == comment
        self.service.revision_repo.update.assert_called_once()
        self.service.approval_repo.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_reject_revision_empty_comment(self):
        """Test rejection with empty comment"""
        # Setup
        self.service.revision_repo.get_by_id = AsyncMock(return_value=self.sample_revision)
        
        # Execute & Verify
        with pytest.raises(ValueError):
            await self.service.reject_revision(
                revision_id=self.revision_id,
                rejector_id=self.approver_id,
                rejector_role=Role.APPROVER,
                comment=""  # Empty comment
            )
    
    @pytest.mark.asyncio
    async def test_withdraw_revision_by_proposer(self):
        """Test revision withdrawal by proposer"""
        # Setup
        self.sample_revision.status = RevisionStatus.DRAFT
        self.service.revision_repo.get_by_id = AsyncMock(return_value=self.sample_revision)
        self.service.revision_repo.update = AsyncMock()
        self.service.approval_repo.create = AsyncMock()
        
        # Execute
        result = await self.service.withdraw_revision(
            revision_id=self.revision_id,
            withdrawer_id=self.proposer_id,  # Same as proposer
            withdrawer_role=Role.GENERAL,
            comment="No longer needed"
        )
        
        # Verify
        assert result.status == RevisionStatus.WITHDRAWN
        self.service.revision_repo.update.assert_called_once()
        self.service.approval_repo.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_withdraw_revision_by_admin(self):
        """Test revision withdrawal by admin"""
        # Setup
        self.sample_revision.status = RevisionStatus.UNDER_REVIEW
        self.service.revision_repo.get_by_id = AsyncMock(return_value=self.sample_revision)
        self.service.revision_repo.update = AsyncMock()
        self.service.approval_repo.create = AsyncMock()
        
        # Execute
        result = await self.service.withdraw_revision(
            revision_id=self.revision_id,
            withdrawer_id=uuid4(),  # Different from proposer
            withdrawer_role=Role.ADMIN,  # Admin can withdraw
            comment="Admin withdrawal"
        )
        
        # Verify
        assert result.status == RevisionStatus.WITHDRAWN
        self.service.revision_repo.update.assert_called_once()
        self.service.approval_repo.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_withdraw_revision_unauthorized(self):
        """Test unauthorized withdrawal attempt"""
        # Setup
        self.sample_revision.status = RevisionStatus.UNDER_REVIEW
        self.service.revision_repo.get_by_id = AsyncMock(return_value=self.sample_revision)
        
        # Execute & Verify
        with pytest.raises(AuthorizationError):
            await self.service.withdraw_revision(
                revision_id=self.revision_id,
                withdrawer_id=uuid4(),  # Different from proposer
                withdrawer_role=Role.GENERAL,  # Not admin
            )
    
    @pytest.mark.asyncio
    async def test_request_modification_success(self):
        """Test successful modification request"""
        # Setup
        self.service.revision_repo.get_by_id = AsyncMock(return_value=self.sample_revision)
        self.service.revision_repo.update = AsyncMock()
        self.service.approval_repo.create = AsyncMock()
        
        instruction = "Please update the title"
        
        # Execute
        result = await self.service.request_modification(
            revision_id=self.revision_id,
            requester_id=self.approver_id,
            requester_role=Role.APPROVER,
            instruction_text=instruction,
            required_fields=["title"],
            priority="high"
        )
        
        # Verify
        assert result.status == RevisionStatus.REVISION_REQUESTED
        self.service.revision_repo.update.assert_called_once()
        self.service.approval_repo.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_request_modification_invalid_state(self):
        """Test modification request on invalid state"""
        # Setup
        self.sample_revision.status = RevisionStatus.APPROVED  # Cannot modify approved
        self.service.revision_repo.get_by_id = AsyncMock(return_value=self.sample_revision)
        
        # Execute & Verify
        with pytest.raises(InvalidStateError):
            await self.service.request_modification(
                revision_id=self.revision_id,
                requester_id=self.approver_id,
                requester_role=Role.APPROVER,
                instruction_text="Please update"
            )
    
    @pytest.mark.asyncio
    async def test_can_user_approve_admin(self):
        """Test admin can always approve"""
        # Setup
        self.sample_revision.status = RevisionStatus.UNDER_REVIEW
        
        # Execute
        can_approve = await self.service.can_user_approve(
            user_id=uuid4(),
            user_role=Role.ADMIN,
            revision=self.sample_revision
        )
        
        # Verify
        assert can_approve is True
    
    @pytest.mark.asyncio
    async def test_can_user_approve_approver_valid_state(self):
        """Test approver can approve in valid state"""
        # Setup
        self.sample_revision.status = RevisionStatus.UNDER_REVIEW
        
        # Execute
        can_approve = await self.service.can_user_approve(
            user_id=uuid4(),
            user_role=Role.APPROVER,
            revision=self.sample_revision
        )
        
        # Verify
        assert can_approve is True
    
    @pytest.mark.asyncio
    async def test_can_user_approve_general_user(self):
        """Test general user cannot approve"""
        # Setup
        self.sample_revision.status = RevisionStatus.UNDER_REVIEW
        
        # Execute
        can_approve = await self.service.can_user_approve(
            user_id=uuid4(),
            user_role=Role.GENERAL,
            revision=self.sample_revision
        )
        
        # Verify
        assert can_approve is False
    
    @pytest.mark.asyncio
    async def test_can_user_approve_invalid_state(self):
        """Test approver cannot approve in invalid state"""
        # Setup
        self.sample_revision.status = RevisionStatus.APPROVED
        
        # Execute
        can_approve = await self.service.can_user_approve(
            user_id=uuid4(),
            user_role=Role.APPROVER,
            revision=self.sample_revision
        )
        
        # Verify
        assert can_approve is False


if __name__ == "__main__":
    pytest.main([__file__])