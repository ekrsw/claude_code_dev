from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from app.core.config import settings
from app.core.exceptions import AuthenticationError, NotFoundError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    verify_password,
    verify_token,
    get_token_jti
)
from app.models.user import User
from app.repositories.user import UserRepository
from app.schemas.user import UserLogin, Token
from app.utils.cache import cache_manager, CacheKeys, cache_ttl

logger = structlog.get_logger()


class AuthService:
    """Authentication service"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
    
    async def authenticate_user(
        self, 
        credentials: UserLogin,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> Optional[User]:
        """Authenticate user with username/email and password"""
        # Get user by username or email
        user = await self.user_repo.get_by_username_or_email(credentials.username)
        
        if not user:
            logger.info("Authentication failed - user not found", identifier=credentials.username)
            # Log failed login attempt
            try:
                from app.services.security_audit import security_audit
                await security_audit.log_login_failed(
                    username=credentials.username,
                    ip_address=ip_address or "unknown",
                    user_agent=user_agent or "unknown",
                    reason="user_not_found"
                )
            except Exception as e:
                logger.warning("Failed to log security event", error=str(e))
            return None
        
        if not user.is_active:
            logger.info("Authentication failed - user inactive", user_id=str(user.id))
            # Log failed login attempt
            try:
                from app.services.security_audit import security_audit
                await security_audit.log_login_failed(
                    username=credentials.username,
                    ip_address=ip_address or "unknown",
                    user_agent=user_agent or "unknown",
                    reason="user_inactive"
                )
            except Exception as e:
                logger.warning("Failed to log security event", error=str(e))
            return None
        
        # Verify password
        if not verify_password(credentials.password, user.hashed_password):
            logger.info("Authentication failed - invalid password", user_id=str(user.id))
            # Log failed login attempt
            try:
                from app.services.security_audit import security_audit
                await security_audit.log_login_failed(
                    username=credentials.username,
                    ip_address=ip_address or "unknown",
                    user_agent=user_agent or "unknown",
                    reason="invalid_password"
                )
            except Exception as e:
                logger.warning("Failed to log security event", error=str(e))
            return None
        
        # Update last login timestamp
        await self.user_repo.update_last_login(user.id)
        
        logger.info("User authenticated successfully", user_id=str(user.id), username=user.username)
        
        return user
    
    async def create_tokens(self, user: User) -> Token:
        """Create access and refresh tokens for user"""
        # Create access token
        access_token = create_access_token(
            subject=user.username,
            user_id=str(user.id)
        )
        
        # Create refresh token
        refresh_token = create_refresh_token(
            subject=user.username,
            user_id=str(user.id)
        )
        
        return Token(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )
    
    async def login(
        self, 
        credentials: UserLogin, 
        user_agent: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Tuple[Token, User]:
        """Login user and return tokens"""
        # Authenticate user
        user = await self.authenticate_user(credentials, ip_address, user_agent)
        if not user:
            raise AuthenticationError("Invalid credentials")
        
        # Create tokens
        tokens = await self.create_tokens(user)
        
        # Create session if session management is available
        if user_agent and ip_address:
            try:
                from app.services.session import session_service
                await session_service.create_session(
                    user_id=user.id,
                    user_agent=user_agent,
                    ip_address=ip_address,
                    access_token=tokens.access_token,
                    refresh_token=tokens.refresh_token
                )
            except Exception as e:
                logger.warning("Failed to create session", error=str(e), user_id=str(user.id))
        
        # Log security event
        try:
            from app.services.security_audit import security_audit
            await security_audit.log_login_success(
                user_id=user.id,
                username=user.username,
                ip_address=ip_address or "unknown",
                user_agent=user_agent or "unknown"
            )
        except Exception as e:
            logger.warning("Failed to log security event", error=str(e))
        
        logger.info("User logged in", user_id=str(user.id), username=user.username)
        
        return tokens, user
    
    async def refresh_token(self, refresh_token: str) -> Token:
        """Refresh access token using refresh token"""
        # Verify refresh token
        payload = verify_token(refresh_token)
        if not payload:
            raise AuthenticationError("Invalid or expired refresh token")
        
        # Check token type
        if payload.get("type") != "refresh":
            raise AuthenticationError("Invalid token type")
        
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
        
        user = await self.user_repo.get(UUID(user_id))
        if not user or not user.is_active:
            raise AuthenticationError("User not found or inactive")
        
        # Create new tokens
        new_tokens = await self.create_tokens(user)
        
        # Blacklist old refresh token
        await self._blacklist_token(refresh_token)
        
        logger.info("Token refreshed", user_id=str(user.id))
        
        return new_tokens
    
    async def logout(
        self,
        access_token: str,
        refresh_token: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> bool:
        """Logout user by blacklisting tokens and removing session"""
        success = True
        
        # Delete session if session ID provided
        if session_id:
            try:
                from app.services.session import session_service
                await session_service.delete_session(session_id)
            except Exception as e:
                logger.warning("Failed to delete session", error=str(e), session_id=session_id)
        
        # Blacklist access token
        if not await self._blacklist_token(access_token):
            success = False
            logger.warning("Failed to blacklist access token")
        
        # Blacklist refresh token if provided
        if refresh_token:
            if not await self._blacklist_token(refresh_token):
                success = False
                logger.warning("Failed to blacklist refresh token")
        
        if success:
            logger.info("User logged out successfully")
        
        return success
    
    async def logout_all_sessions(self, user_id: UUID) -> bool:
        """Logout user from all sessions by invalidating user cache"""
        try:
            # Invalidate user cache to force token re-validation
            user_cache_key = CacheKeys.user(str(user_id))
            await cache_manager.delete(user_cache_key)
            
            # Note: In a production system, you might want to maintain
            # a per-user token registry for more precise control
            
            logger.info("All sessions invalidated", user_id=str(user_id))
            return True
        except Exception as e:
            logger.error("Failed to invalidate all sessions", user_id=str(user_id), error=str(e))
            return False
    
    async def verify_user_token(self, token: str) -> Optional[User]:
        """Verify token and return user"""
        # Verify token
        payload = verify_token(token)
        if not payload:
            return None
        
        # Check token type
        if payload.get("type") != "access":
            return None
        
        # Check if token is blacklisted
        jti = payload.get("jti")
        if jti:
            blacklist_key = CacheKeys.jwt_blacklist(jti)
            is_blacklisted = await cache_manager.exists(blacklist_key)
            if is_blacklisted:
                return None
        
        # Get user
        user_id = payload.get("user_id")
        if not user_id:
            return None
        
        user = await self.user_repo.get(UUID(user_id))
        if not user or not user.is_active:
            return None
        
        return user
    
    async def change_password_with_auth(
        self,
        user_id: UUID,
        current_password: str,
        new_password: str
    ) -> bool:
        """Change password with current password verification"""
        user = await self.user_repo.get(user_id)
        if not user:
            raise NotFoundError("User not found")
        
        # Verify current password
        if not verify_password(current_password, user.hashed_password):
            raise AuthenticationError("Current password is incorrect")
        
        # Use UserService to handle password change
        from app.services.user import UserService
        user_service = UserService(self.db)
        
        return await user_service.change_password(
            user_id=user_id,
            current_password=current_password,
            new_password=new_password,
            current_user=user
        )
    
    async def _blacklist_token(self, token: str) -> bool:
        """Add token to blacklist"""
        try:
            jti = get_token_jti(token)
            if not jti:
                return False
            
            # Calculate TTL based on token expiration
            payload = verify_token(token)
            if payload and payload.get("exp"):
                exp_timestamp = payload["exp"]
                current_timestamp = datetime.utcnow().timestamp()
                
                if exp_timestamp > current_timestamp:
                    ttl = int(exp_timestamp - current_timestamp)
                else:
                    # Token already expired, no need to blacklist
                    return True
            else:
                # Default TTL if we can't determine expiration
                ttl = cache_ttl(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
            
            # Add to blacklist
            blacklist_key = CacheKeys.jwt_blacklist(jti)
            await cache_manager.set(blacklist_key, "blacklisted", ttl=ttl)
            
            logger.debug("Token blacklisted", jti=jti, ttl=ttl)
            return True
        except Exception as e:
            logger.error("Failed to blacklist token", error=str(e))
            return False
    
    async def is_token_blacklisted(self, token: str) -> bool:
        """Check if token is blacklisted"""
        try:
            jti = get_token_jti(token)
            if not jti:
                return False
            
            blacklist_key = CacheKeys.jwt_blacklist(jti)
            return await cache_manager.exists(blacklist_key)
        except Exception as e:
            logger.error("Failed to check token blacklist", error=str(e))
            return False
    
    async def get_token_info(self, token: str) -> Optional[dict]:
        """Get token information"""
        payload = verify_token(token)
        if not payload:
            return None
        
        return {
            "user_id": payload.get("user_id"),
            "username": payload.get("sub"),
            "token_type": payload.get("type"),
            "jti": payload.get("jti"),
            "exp": payload.get("exp"),
            "is_blacklisted": await self.is_token_blacklisted(token)
        }
    
    async def get_user_sessions(self, user_id: UUID) -> List[dict]:
        """Get all active sessions for a user"""
        try:
            from app.services.session import session_service
            sessions = await session_service.get_user_sessions(user_id)
            
            return [
                {
                    "session_id": session.session_id,
                    "user_agent": session.user_agent,
                    "ip_address": session.ip_address,
                    "created_at": session.created_at.isoformat(),
                    "last_activity": session.last_activity.isoformat()
                }
                for session in sessions
            ]
        except Exception as e:
            logger.error("Failed to get user sessions", user_id=str(user_id), error=str(e))
            return []
    
    async def revoke_user_session(self, user_id: UUID, session_id: str) -> bool:
        """Revoke a specific user session"""
        try:
            from app.services.session import session_service
            return await session_service.delete_session(session_id)
        except Exception as e:
            logger.error("Failed to revoke session", user_id=str(user_id), session_id=session_id, error=str(e))
            return False