from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import structlog

from app.core.security import verify_token, get_token_jti
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.db.session import get_db
from app.models.user import User
from app.utils.cache import cache_manager, CacheKeys, cache_ttl

logger = structlog.get_logger()
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    if not credentials:
        raise AuthenticationError("Authorization header missing")
    
    token = credentials.credentials
    if not token:
        raise AuthenticationError("Token missing")
    
    # Verify token
    payload = verify_token(token)
    if not payload:
        raise AuthenticationError("Invalid or expired token")
    
    # Check if token is blacklisted
    jti = payload.get("jti")
    if jti:
        blacklist_key = CacheKeys.jwt_blacklist(jti)
        is_blacklisted = await cache_manager.exists(blacklist_key)
        if is_blacklisted:
            raise AuthenticationError("Token has been revoked")
    
    # Get user
    user_id = payload.get("user_id")
    if not user_id:
        raise AuthenticationError("Invalid token payload")
    
    # Try to get user from cache first
    cache_key = CacheKeys.user(user_id)
    cached_user = await cache_manager.get(cache_key)
    
    if cached_user:
        # Reconstruct user object from cached data
        user = User(**cached_user)
        user.id = user_id
    else:
        # Get user from database
        result = await db.execute(
            select(User).where(User.id == user_id, User.is_active == True)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            raise AuthenticationError("User not found or inactive")
        
        # Cache user data
        user_data = {
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role.value,
            "is_sv": user.is_sv,
            "is_active": user.is_active,
        }
        await cache_manager.set(
            cache_key, 
            user_data, 
            ttl=cache_ttl(minutes=30)
        )
    
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current active user"""
    if not current_user.is_active:
        raise AuthorizationError("User account is disabled")
    
    return current_user


async def get_current_supervisor(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current user with supervisor privileges"""
    if not current_user.is_supervisor:
        raise AuthorizationError("Supervisor privileges required")
    
    return current_user


async def get_current_approver(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current user with approval privileges"""
    if not current_user.can_approve:
        raise AuthorizationError("Approval privileges required")
    
    return current_user


async def get_current_admin(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current admin user"""
    if not current_user.is_admin:
        raise AuthorizationError("Admin privileges required")
    
    return current_user


async def blacklist_token(token: str) -> bool:
    """Add token to blacklist"""
    try:
        jti = get_token_jti(token)
        if not jti:
            return False
        
        # Add to blacklist with TTL equal to token expiration
        blacklist_key = CacheKeys.jwt_blacklist(jti)
        # Use a long TTL since we can't determine exact token expiration easily
        await cache_manager.set(
            blacklist_key, 
            "blacklisted", 
            ttl=cache_ttl(days=7)  # Use hardcoded value for now
        )
        
        logger.info("Token blacklisted", jti=jti)
        return True
    except Exception as e:
        logger.error("Failed to blacklist token", error=str(e))
        return False


# Optional authentication (for public endpoints that benefit from auth)
async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, None otherwise"""
    if not credentials:
        return None
    
    try:
        return await get_current_user(credentials, db)
    except (AuthenticationError, AuthorizationError):
        return None