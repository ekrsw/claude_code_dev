from typing import List, Optional
from functools import wraps

from fastapi import HTTPException, status
import structlog

from app.constants.enums import Role, RevisionStatus
from app.models.user import User
from app.models.revision import Revision

logger = structlog.get_logger()


class PermissionChecker:
    """Permission checking utilities"""
    
    @staticmethod
    def check_user_role(user: User, required_roles: List[Role]) -> bool:
        """Check if user has required role"""
        return user.role in required_roles
    
    @staticmethod
    def check_supervisor_access(user: User) -> bool:
        """Check if user has supervisor access"""
        return user.is_supervisor
    
    @staticmethod
    def check_admin_access(user: User) -> bool:
        """Check if user is admin"""
        return user.is_admin
    
    @staticmethod
    def check_approval_permission(user: User) -> bool:
        """Check if user can approve revisions"""
        return user.can_approve
    
    @staticmethod
    def can_view_revision(user: User, revision: Revision) -> bool:
        """Check if user can view a specific revision"""
        # Admin can view all
        if user.is_admin:
            return True
        
        # Proposer can always view their own revision
        if revision.proposer_id == user.id:
            return True
        
        # Approvers and supervisors can view non-draft revisions
        if user.can_approve and revision.status != RevisionStatus.DRAFT:
            return True
        
        # General users can only view approved revisions
        if revision.status == RevisionStatus.APPROVED:
            return True
        
        return False
    
    @staticmethod
    def can_edit_revision(user: User, revision: Revision) -> bool:
        """Check if user can edit a specific revision"""
        # Admin can edit all
        if user.is_admin:
            return True
        
        # Check status-based permissions
        if revision.status == RevisionStatus.DRAFT:
            # Only proposer can edit draft
            return revision.proposer_id == user.id
        
        elif revision.status == RevisionStatus.UNDER_REVIEW:
            # Only approvers/supervisors can edit under review
            return user.can_approve
        
        elif revision.status == RevisionStatus.REVISION_REQUESTED:
            # Proposer and approvers can edit
            return (revision.proposer_id == user.id) or user.can_approve
        
        else:
            # No editing for approved/rejected/withdrawn
            return False
    
    @staticmethod
    def can_approve_revision(user: User, revision: Revision) -> bool:
        """Check if user can approve/reject a revision"""
        if not user.can_approve:
            return False
        
        # Cannot approve own revision
        if revision.proposer_id == user.id:
            return False
        
        # Can only approve revisions under review or revision requested
        return revision.status in [
            RevisionStatus.UNDER_REVIEW,
            RevisionStatus.REVISION_REQUESTED
        ]
    
    @staticmethod
    def can_request_modification(user: User, revision: Revision) -> bool:
        """Check if user can request modification"""
        if not user.can_approve:
            return False
        
        # Cannot request modification on own revision
        if revision.proposer_id == user.id:
            return False
        
        # Can only request modification on under review revisions
        return revision.status == RevisionStatus.UNDER_REVIEW
    
    @staticmethod
    def can_withdraw_revision(user: User, revision: Revision) -> bool:
        """Check if user can withdraw a revision"""
        # Only proposer can withdraw their own draft/under review revision
        if revision.proposer_id != user.id:
            return False
        
        return revision.status in [
            RevisionStatus.DRAFT,
            RevisionStatus.UNDER_REVIEW,
            RevisionStatus.REVISION_REQUESTED
        ]


def require_roles(roles: List[Role]):
    """Decorator to require specific roles"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract current_user from kwargs
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            if not PermissionChecker.check_user_role(current_user, roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_supervisor():
    """Decorator to require supervisor access"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            if not PermissionChecker.check_supervisor_access(current_user):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Supervisor access required"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def require_admin():
    """Decorator to require admin access"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required"
                )
            
            if not PermissionChecker.check_admin_access(current_user):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin access required"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def check_revision_permission(action: str):
    """Decorator to check revision-specific permissions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get('current_user')
            revision = kwargs.get('revision')
            
            if not current_user or not revision:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing required parameters"
                )
            
            permission_granted = False
            
            if action == "view":
                permission_granted = PermissionChecker.can_view_revision(current_user, revision)
            elif action == "edit":
                permission_granted = PermissionChecker.can_edit_revision(current_user, revision)
            elif action == "approve":
                permission_granted = PermissionChecker.can_approve_revision(current_user, revision)
            elif action == "request_modification":
                permission_granted = PermissionChecker.can_request_modification(current_user, revision)
            elif action == "withdraw":
                permission_granted = PermissionChecker.can_withdraw_revision(current_user, revision)
            
            if not permission_granted:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Permission denied for action: {action}"
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator