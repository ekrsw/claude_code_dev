from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.constants.enums import Role
from app.core.exceptions import ConflictError, NotFoundError, ValidationError, AuthorizationError
from app.core.security import get_password_hash, verify_password, validate_password_strength
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserUpdate, UserProfileUpdate, UserRoleUpdate
from app.utils.cache import cache_manager, CacheKeys

logger = structlog.get_logger()


class UserService:
    """User management service"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
    
    async def create_user(self, user_data: UserCreate) -> User:
        """Create a new user"""
        # Validate password strength
        password_validation = validate_password_strength(user_data.password)
        if not password_validation["is_valid"]:
            raise ValidationError(
                f"Password validation failed: {', '.join(password_validation['errors'])}"
            )
        
        # Check if username exists
        if await self.user_repo.username_exists(user_data.username):
            raise ConflictError(f"Username '{user_data.username}' already exists")
        
        # Check if email exists
        if await self.user_repo.email_exists(user_data.email):
            raise ConflictError(f"Email '{user_data.email}' already exists")
        
        # Hash password
        hashed_password = get_password_hash(user_data.password)
        
        # Create user
        user = await self.user_repo.create_user(
            username=user_data.username,
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            role=Role.GENERAL  # Default role
        )
        
        logger.info("User created", user_id=str(user.id), username=user.username)
        
        # Invalidate related caches
        await self._invalidate_user_caches(user.id)
        
        return user
    
    async def get_user(self, user_id: UUID) -> Optional[User]:
        """Get user by ID (active users only)"""
        user = await self.user_repo.get(user_id)
        if user and not user.is_active:
            return None
        return user
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        return await self.user_repo.get_by_username(username)
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return await self.user_repo.get_by_email(email)
    
    async def get_user_by_credentials(self, identifier: str) -> Optional[User]:
        """Get user by username or email"""
        return await self.user_repo.get_by_username_or_email(identifier)
    
    async def update_user(
        self,
        user_id: UUID,
        user_data: UserUpdate,
        current_user: User
    ) -> User:
        """Update user information"""
        user = await self.user_repo.get(user_id)
        if not user:
            raise NotFoundError("User not found")
        
        # Check permissions (users can only update themselves, admins can update anyone)
        if user_id != current_user.id and not current_user.is_admin:
            raise AuthorizationError("Not authorized to update this user")
        
        update_data = {}
        
        # Validate email uniqueness if changing
        if user_data.email and user_data.email != user.email:
            if await self.user_repo.email_exists(user_data.email, exclude_id=user_id):
                raise ConflictError(f"Email '{user_data.email}' already exists")
            update_data["email"] = user_data.email.lower()
        
        # Update other fields
        if user_data.full_name is not None:
            update_data["full_name"] = user_data.full_name
        
        # Only admins can change active status
        if user_data.is_active is not None and current_user.is_admin:
            update_data["is_active"] = user_data.is_active
        
        if not update_data:
            return user
        
        updated_user = await self.user_repo.update(user_id, **update_data)
        if not updated_user:
            raise NotFoundError("User not found")
        
        logger.info("User updated", user_id=str(user_id), updated_by=str(current_user.id))
        
        # Invalidate caches
        await self._invalidate_user_caches(user_id)
        
        return updated_user
    
    async def update_profile(
        self,
        user_id: UUID,
        profile_data: UserProfileUpdate,
        current_user: User
    ) -> User:
        """Update user profile"""
        # Check permissions
        if user_id != current_user.id and not current_user.is_admin:
            raise AuthorizationError("Not authorized to update this profile")
        
        user = await self.user_repo.update_profile(
            user_id=user_id,
            full_name=profile_data.full_name,
            sweet_name=profile_data.sweet_name,
            ctstage_name=profile_data.ctstage_name
        )
        
        if not user:
            raise NotFoundError("User not found")
        
        logger.info("User profile updated", user_id=str(user_id))
        
        # Invalidate caches
        await self._invalidate_user_caches(user_id)
        
        return user
    
    async def update_role(
        self,
        user_id: UUID,
        role_data: UserRoleUpdate,
        current_user: User
    ) -> User:
        """Update user role (admin only)"""
        if not current_user.is_admin:
            raise AuthorizationError("Admin access required")
        
        user = await self.user_repo.update_role(
            user_id=user_id,
            role=role_data.role,
            is_sv=role_data.is_sv
        )
        
        if not user:
            raise NotFoundError("User not found")
        
        logger.info(
            "User role updated",
            user_id=str(user_id),
            new_role=role_data.role,
            is_sv=role_data.is_sv,
            updated_by=str(current_user.id)
        )
        
        # Invalidate caches
        await self._invalidate_user_caches(user_id)
        
        return user
    
    async def change_password(
        self,
        user_id: UUID,
        current_password: str,
        new_password: str,
        current_user: User
    ) -> bool:
        """Change user password"""
        # Check permissions
        if user_id != current_user.id and not current_user.is_admin:
            raise AuthorizationError("Not authorized to change this password")
        
        user = await self.user_repo.get(user_id)
        if not user:
            raise NotFoundError("User not found")
        
        # Verify current password (except for admin)
        if not current_user.is_admin:
            if not verify_password(current_password, user.hashed_password):
                raise AuthorizationError("Current password is incorrect")
        
        # Validate new password strength
        password_validation = validate_password_strength(new_password)
        if not password_validation["is_valid"]:
            raise ValidationError(
                f"Password validation failed: {', '.join(password_validation['errors'])}"
            )
        
        # Update password
        hashed_password = get_password_hash(new_password)
        updated_user = await self.user_repo.update_password(user_id, hashed_password)
        
        if not updated_user:
            raise NotFoundError("User not found")
        
        logger.info("Password changed", user_id=str(user_id))
        
        # Invalidate user cache to force re-authentication
        await self._invalidate_user_caches(user_id)
        
        return True
    
    async def activate_user(self, user_id: UUID, current_user: User) -> User:
        """Activate user account (admin only)"""
        if not current_user.is_admin:
            raise AuthorizationError("Admin access required")
        
        user = await self.user_repo.activate_user(user_id)
        if not user:
            raise NotFoundError("User not found")
        
        logger.info("User activated", user_id=str(user_id), activated_by=str(current_user.id))
        
        await self._invalidate_user_caches(user_id)
        
        return user
    
    async def deactivate_user(self, user_id: UUID, current_user: User) -> User:
        """Deactivate user account (admin only)"""
        if not current_user.is_admin:
            raise AuthorizationError("Admin access required")
        
        # Cannot deactivate self
        if user_id == current_user.id:
            raise ValidationError("Cannot deactivate your own account")
        
        user = await self.user_repo.deactivate_user(user_id)
        if not user:
            raise NotFoundError("User not found")
        
        logger.info("User deactivated", user_id=str(user_id), deactivated_by=str(current_user.id))
        
        await self._invalidate_user_caches(user_id)
        
        return user
    
    async def delete_user(self, user_id: UUID, current_user: User) -> bool:
        """Delete user account (admin only)"""
        if not current_user.is_admin:
            raise AuthorizationError("Admin access required")
        
        # Cannot delete self
        if user_id == current_user.id:
            raise ValidationError("Cannot delete your own account")
        
        user = await self.user_repo.get(user_id)
        if not user:
            raise NotFoundError("User not found")
        
        # Soft delete by deactivating instead of hard delete
        # This preserves data integrity for revisions and history
        await self.user_repo.deactivate_user(user_id)
        
        logger.info("User deleted (deactivated)", user_id=str(user_id), deleted_by=str(current_user.id))
        
        await self._invalidate_user_caches(user_id)
        
        return True
    
    async def get_users(
        self,
        skip: int = 0,
        limit: int = 100,
        role: Optional[Role] = None,
        active_only: bool = True
    ) -> Tuple[List[User], int]:
        """Get users with pagination"""
        filters = {}
        if active_only:
            filters["is_active"] = True
        if role:
            filters["role"] = role
        
        users = await self.user_repo.get_multi(
            skip=skip,
            limit=limit,
            filters=filters,
            order_by="username"
        )
        
        total = await self.user_repo.count(filters)
        
        return users, total
    
    async def search_users(
        self,
        search_term: str,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = True
    ) -> List[User]:
        """Search users by username, email, or full name"""
        return await self.user_repo.search_users(
            search_term=search_term,
            skip=skip,
            limit=limit,
            active_only=active_only
        )
    
    async def get_supervisors(self) -> List[User]:
        """Get all users with supervisor privileges"""
        return await self.user_repo.get_supervisors()
    
    async def get_approvers(self) -> List[User]:
        """Get all users who can approve revisions"""
        return await self.user_repo.get_approvers()
    
    async def _invalidate_user_caches(self, user_id: UUID) -> None:
        """Invalidate user-related caches"""
        try:
            # Clear user cache
            user_cache_key = CacheKeys.user(str(user_id))
            await cache_manager.delete(user_cache_key)
            
            # Clear username cache pattern
            username_pattern = CacheKeys.user_by_username("*")
            await cache_manager.delete_pattern(username_pattern)
            
            logger.debug("User caches invalidated", user_id=str(user_id))
        except Exception as e:
            logger.warning("Failed to invalidate user caches", user_id=str(user_id), error=str(e))