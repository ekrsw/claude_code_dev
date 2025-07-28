from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.constants.enums import Role
from app.models.user import User
from app.repositories.base import BaseRepository

logger = structlog.get_logger()


class UserRepository(BaseRepository[User]):
    """User repository"""
    
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        return await self.get_by_field("username", username.lower())
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        return await self.get_by_field("email", email.lower())
    
    async def get_by_username_or_email(self, identifier: str) -> Optional[User]:
        """Get user by username or email"""
        query = select(User).where(
            or_(
                User.username == identifier.lower(),
                User.email == identifier.lower()
            )
        )
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def create_user(
        self,
        username: str,
        email: str,
        hashed_password: str,
        full_name: Optional[str] = None,
        role: Role = Role.GENERAL
    ) -> User:
        """Create a new user"""
        user_data = {
            "username": username.lower(),
            "email": email.lower(),
            "hashed_password": hashed_password,
            "full_name": full_name,
            "role": role,
            "is_active": True
        }
        return await self.create(**user_data)
    
    async def update_last_login(self, user_id: UUID) -> bool:
        """Update user's last login timestamp"""
        from datetime import datetime
        
        query = (
            update(User)
            .where(User.id == user_id)
            .values(last_login_at=datetime.utcnow())
        )
        
        result = await self.db.execute(query)
        return result.rowcount > 0
    
    async def update_profile(
        self,
        user_id: UUID,
        full_name: Optional[str] = None,
        sweet_name: Optional[str] = None,
        ctstage_name: Optional[str] = None
    ) -> Optional[User]:
        """Update user profile"""
        update_data = {}
        if full_name is not None:
            update_data["full_name"] = full_name
        if sweet_name is not None:
            update_data["sweet_name"] = sweet_name
        if ctstage_name is not None:
            update_data["ctstage_name"] = ctstage_name
        
        if not update_data:
            return await self.get(user_id)
        
        return await self.update(user_id, **update_data)
    
    async def update_role(
        self,
        user_id: UUID,
        role: Role,
        is_sv: bool = False
    ) -> Optional[User]:
        """Update user role and supervisor status"""
        return await self.update(user_id, role=role, is_sv=is_sv)
    
    async def update_password(
        self,
        user_id: UUID,
        hashed_password: str
    ) -> Optional[User]:
        """Update user password"""
        from datetime import datetime
        
        return await self.update(
            user_id,
            hashed_password=hashed_password,
            password_changed_at=datetime.utcnow()
        )
    
    async def activate_user(self, user_id: UUID) -> Optional[User]:
        """Activate user account"""
        return await self.update(user_id, is_active=True)
    
    async def deactivate_user(self, user_id: UUID) -> Optional[User]:
        """Deactivate user account"""
        return await self.update(user_id, is_active=False)
    
    async def get_active_users(
        self,
        skip: int = 0,
        limit: int = 100,
        role: Optional[Role] = None
    ) -> List[User]:
        """Get active users with optional role filter"""
        filters = {"is_active": True}
        if role:
            filters["role"] = role
        
        return await self.get_multi(
            skip=skip,
            limit=limit,
            filters=filters,
            order_by="username"
        )
    
    async def get_supervisors(self) -> List[User]:
        """Get all users with supervisor privileges"""
        query = select(User).where(
            and_(
                User.is_active == True,
                or_(
                    User.is_sv == True,
                    User.role.in_([Role.SUPERVISOR, Role.APPROVER, Role.ADMIN])
                )
            )
        ).order_by(User.username)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def get_approvers(self) -> List[User]:
        """Get all users who can approve revisions"""
        query = select(User).where(
            and_(
                User.is_active == True,
                or_(
                    User.role.in_([Role.APPROVER, Role.ADMIN]),
                    User.is_sv == True
                )
            )
        ).order_by(User.username)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def search_users(
        self,
        search_term: str,
        skip: int = 0,
        limit: int = 100,
        active_only: bool = True
    ) -> List[User]:
        """Search users by username, email, or full name"""
        search_pattern = f"%{search_term.lower()}%"
        
        query = select(User).where(
            or_(
                User.username.ilike(search_pattern),
                User.email.ilike(search_pattern),
                User.full_name.ilike(search_pattern)
            )
        )
        
        if active_only:
            query = query.where(User.is_active == True)
        
        query = query.order_by(User.username).offset(skip).limit(limit)
        
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def count_by_role(self, role: Role) -> int:
        """Count users by role"""
        return await self.count(filters={"role": role, "is_active": True})
    
    async def username_exists(self, username: str, exclude_id: Optional[UUID] = None) -> bool:
        """Check if username exists (excluding specific user ID)"""
        query = select(User.id).where(User.username == username.lower())
        if exclude_id:
            query = query.where(User.id != exclude_id)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
    
    async def email_exists(self, email: str, exclude_id: Optional[UUID] = None) -> bool:
        """Check if email exists (excluding specific user ID)"""
        query = select(User.id).where(User.email == email.lower())
        if exclude_id:
            query = query.where(User.id != exclude_id)
        
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None