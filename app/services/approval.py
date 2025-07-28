"""
Approval service for managing revision approval workflow and history
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.approval import ApprovalHistory
from app.models.revision import Revision
from app.models.user import User
from app.constants.enums import ApprovalAction, RevisionStatus, Role
from app.core.exceptions import NotFoundError, AuthorizationError, InvalidStateError
from app.repositories.approval import ApprovalHistoryRepository
from app.repositories.revision import RevisionRepository


class ApprovalService:
    """Service for managing approval workflow and history"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.approval_repo = ApprovalHistoryRepository(db)
        self.revision_repo = RevisionRepository(db)
    
    async def approve_revision(
        self,
        revision_id: UUID,
        approver_id: UUID,
        approver_role: Role,
        comment: Optional[str] = None
    ) -> Revision:
        """
        Approve a revision
        
        Args:
            revision_id: ID of revision to approve
            approver_id: ID of user approving
            approver_role: Role of approver
            comment: Optional approval comment
            
        Returns:
            Updated revision
            
        Raises:
            NotFoundError: If revision not found
            AuthorizationError: If user cannot approve
            InvalidStateError: If revision cannot be approved
        """
        # Get revision
        revision = await self.revision_repo.get_by_id(revision_id)
        if not revision:
            raise NotFoundError(f"Revision {revision_id} not found")
        
        # Check if revision can be approved
        if revision.status not in [RevisionStatus.UNDER_REVIEW, RevisionStatus.REVISION_REQUESTED]:
            raise InvalidStateError(f"Cannot approve revision in status: {revision.status}")
        
        # Check approver permissions
        if approver_role not in [Role.APPROVER, Role.SUPERVISOR, Role.ADMIN]:
            raise AuthorizationError("User does not have approval permissions")
        
        # Update revision status
        revision.status = RevisionStatus.APPROVED
        revision.approver_id = approver_id
        revision.approved_at = datetime.utcnow()
        revision.approval_comment = comment
        
        await self.revision_repo.update(revision)
        
        # Create approval history record
        approval_history = ApprovalHistory(
            revision_id=revision_id,
            actor_id=approver_id,
            action=ApprovalAction.APPROVED,
            comment=comment
        )
        await self.approval_repo.create(approval_history)
        
        return revision
    
    async def reject_revision(
        self,
        revision_id: UUID,
        rejector_id: UUID,
        rejector_role: Role,
        comment: str
    ) -> Revision:
        """
        Reject a revision
        
        Args:
            revision_id: ID of revision to reject
            rejector_id: ID of user rejecting
            rejector_role: Role of rejector
            comment: Required rejection comment
            
        Returns:
            Updated revision
            
        Raises:
            NotFoundError: If revision not found
            AuthorizationError: If user cannot reject
            InvalidStateError: If revision cannot be rejected
            ValueError: If comment is empty
        """
        if not comment or not comment.strip():
            raise ValueError("Rejection comment is required")
        
        # Get revision
        revision = await self.revision_repo.get_by_id(revision_id)
        if not revision:
            raise NotFoundError(f"Revision {revision_id} not found")
        
        # Check if revision can be rejected
        if revision.status not in [RevisionStatus.UNDER_REVIEW, RevisionStatus.REVISION_REQUESTED]:
            raise InvalidStateError(f"Cannot reject revision in status: {revision.status}")
        
        # Check rejector permissions
        if rejector_role not in [Role.APPROVER, Role.SUPERVISOR, Role.ADMIN]:
            raise AuthorizationError("User does not have rejection permissions")
        
        # Update revision status
        revision.status = RevisionStatus.REJECTED
        revision.approver_id = rejector_id
        revision.approved_at = datetime.utcnow()
        revision.approval_comment = comment
        
        await self.revision_repo.update(revision)
        
        # Create approval history record
        approval_history = ApprovalHistory(
            revision_id=revision_id,
            actor_id=rejector_id,
            action=ApprovalAction.REJECTED,
            comment=comment
        )
        await self.approval_repo.create(approval_history)
        
        return revision
    
    async def withdraw_revision(
        self,
        revision_id: UUID,
        withdrawer_id: UUID,
        withdrawer_role: Role,
        comment: Optional[str] = None
    ) -> Revision:
        """
        Withdraw a revision
        
        Args:
            revision_id: ID of revision to withdraw
            withdrawer_id: ID of user withdrawing
            withdrawer_role: Role of withdrawer
            comment: Optional withdrawal comment
            
        Returns:
            Updated revision
            
        Raises:
            NotFoundError: If revision not found
            AuthorizationError: If user cannot withdraw
            InvalidStateError: If revision cannot be withdrawn
        """
        # Get revision
        revision = await self.revision_repo.get_by_id(revision_id)
        if not revision:
            raise NotFoundError(f"Revision {revision_id} not found")
        
        # Check if revision can be withdrawn
        if revision.status not in [RevisionStatus.DRAFT, RevisionStatus.UNDER_REVIEW, RevisionStatus.REVISION_REQUESTED]:
            raise InvalidStateError(f"Cannot withdraw revision in status: {revision.status}")
        
        # Check withdrawal permissions (proposer or admin can withdraw)
        if withdrawer_role != Role.ADMIN and revision.proposer_id != withdrawer_id:
            raise AuthorizationError("Only proposer or admin can withdraw revision")
        
        # Update revision status
        revision.status = RevisionStatus.WITHDRAWN
        
        await self.revision_repo.update(revision)
        
        # Create approval history record
        approval_history = ApprovalHistory(
            revision_id=revision_id,
            actor_id=withdrawer_id,
            action=ApprovalAction.WITHDRAWN,
            comment=comment
        )
        await self.approval_repo.create(approval_history)
        
        return revision
    
    async def request_modification(
        self,
        revision_id: UUID,
        requester_id: UUID,
        requester_role: Role,
        instruction_text: str,
        required_fields: Optional[List[str]] = None,
        priority: str = "normal"
    ) -> Revision:
        """
        Request modification for a revision
        
        Args:
            revision_id: ID of revision to request modification for
            requester_id: ID of user requesting modification
            requester_role: Role of requester
            instruction_text: Instruction text for modification
            required_fields: List of fields that need modification
            priority: Priority level (low, normal, high, urgent)
            
        Returns:
            Updated revision
            
        Raises:
            NotFoundError: If revision not found
            AuthorizationError: If user cannot request modification
            InvalidStateError: If revision cannot be modified
        """
        # Get revision
        revision = await self.revision_repo.get_by_id(revision_id)
        if not revision:
            raise NotFoundError(f"Revision {revision_id} not found")
        
        # Check if revision can have modification requested
        if revision.status != RevisionStatus.UNDER_REVIEW:
            raise InvalidStateError(f"Cannot request modification for revision in status: {revision.status}")
        
        # Check requester permissions
        if requester_role not in [Role.APPROVER, Role.SUPERVISOR, Role.ADMIN]:
            raise AuthorizationError("User does not have modification request permissions")
        
        # Update revision status
        revision.status = RevisionStatus.REVISION_REQUESTED
        
        await self.revision_repo.update(revision)
        
        # Create approval history record
        approval_history = ApprovalHistory(
            revision_id=revision_id,
            actor_id=requester_id,
            action=ApprovalAction.REVISION_REQUESTED,
            comment=f"修正指示: {instruction_text}"
        )
        await self.approval_repo.create(approval_history)
        
        return revision
    
    async def get_approval_history(
        self,
        revision_id: UUID,
        user_id: UUID,
        user_role: Role
    ) -> List[ApprovalHistory]:
        """
        Get approval history for a revision
        
        Args:
            revision_id: ID of revision
            user_id: ID of requesting user
            user_role: Role of requesting user
            
        Returns:
            List of approval history records
            
        Raises:
            NotFoundError: If revision not found
            AuthorizationError: If user cannot view history
        """
        # Get revision to check permissions
        revision = await self.revision_repo.get_by_id(revision_id)
        if not revision:
            raise NotFoundError(f"Revision {revision_id} not found")
        
        # Check if user can view approval history
        can_view = (
            user_role == Role.ADMIN or
            user_role in [Role.APPROVER, Role.SUPERVISOR] or
            revision.proposer_id == user_id
        )
        
        if not can_view:
            raise AuthorizationError("User does not have permission to view approval history")
        
        # Get approval history
        query = select(ApprovalHistory).where(
            ApprovalHistory.revision_id == revision_id
        ).options(
            selectinload(ApprovalHistory.actor)
        ).order_by(ApprovalHistory.created_at.desc())
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def can_user_approve(
        self,
        user_id: UUID,
        user_role: Role,
        revision: Revision
    ) -> bool:
        """
        Check if user can approve a revision
        
        Args:
            user_id: ID of user
            user_role: Role of user
            revision: Revision to check
            
        Returns:
            True if user can approve, False otherwise
        """
        # Admin can always approve
        if user_role == Role.ADMIN:
            return True
        
        # Approvers and supervisors can approve if revision is under review or revision requested
        if user_role in [Role.APPROVER, Role.SUPERVISOR]:
            return revision.status in [RevisionStatus.UNDER_REVIEW, RevisionStatus.REVISION_REQUESTED]
        
        return False
    
    async def get_revision_status_counts(self, user_role: Role) -> dict:
        """
        Get counts of revisions by status for dashboard
        
        Args:
            user_role: Role of requesting user
            
        Returns:
            Dictionary with status counts
        """
        if user_role not in [Role.APPROVER, Role.SUPERVISOR, Role.ADMIN]:
            return {}
        
        # Count revisions by status that need approval attention
        query = select(Revision.status, Revision.id).where(
            Revision.status.in_([
                RevisionStatus.UNDER_REVIEW,
                RevisionStatus.REVISION_REQUESTED,
                RevisionStatus.APPROVED,
                RevisionStatus.REJECTED
            ])
        )
        
        result = await self.db.execute(query)
        revisions = result.all()
        
        counts = {
            "under_review": 0,
            "revision_requested": 0,
            "approved": 0,
            "rejected": 0
        }
        
        for status, _ in revisions:
            if status == RevisionStatus.UNDER_REVIEW:
                counts["under_review"] += 1
            elif status == RevisionStatus.REVISION_REQUESTED:
                counts["revision_requested"] += 1
            elif status == RevisionStatus.APPROVED:
                counts["approved"] += 1
            elif status == RevisionStatus.REJECTED:
                counts["rejected"] += 1
        
        return counts