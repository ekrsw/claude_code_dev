"""
Session management service for tracking user sessions
"""
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID, uuid4
import structlog

from app.core.config import settings
from app.core.security import verify_token, get_token_jti
from app.utils.cache import cache_manager, CacheKeys, cache_ttl

logger = structlog.get_logger()


class UserSession:
    """User session data structure"""
    
    def __init__(
        self,
        session_id: str,
        user_id: UUID,
        user_agent: str,
        ip_address: str,
        created_at: datetime,
        last_activity: datetime,
        access_token_jti: Optional[str] = None,
        refresh_token_jti: Optional[str] = None
    ):
        self.session_id = session_id
        self.user_id = user_id
        self.user_agent = user_agent
        self.ip_address = ip_address
        self.created_at = created_at
        self.last_activity = last_activity
        self.access_token_jti = access_token_jti
        self.refresh_token_jti = refresh_token_jti
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for storage"""
        return {
            "session_id": self.session_id,
            "user_id": str(self.user_id),
            "user_agent": self.user_agent,
            "ip_address": self.ip_address,
            "created_at": self.created_at.isoformat(),
            "last_activity": self.last_activity.isoformat(),
            "access_token_jti": self.access_token_jti,
            "refresh_token_jti": self.refresh_token_jti
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserSession":
        """Create session from dictionary"""
        return cls(
            session_id=data["session_id"],
            user_id=UUID(data["user_id"]),
            user_agent=data["user_agent"],
            ip_address=data["ip_address"],
            created_at=datetime.fromisoformat(data["created_at"]),
            last_activity=datetime.fromisoformat(data["last_activity"]),
            access_token_jti=data.get("access_token_jti"),
            refresh_token_jti=data.get("refresh_token_jti")
        )


class SessionService:
    """Service for managing user sessions"""
    
    def __init__(self):
        self.session_timeout = timedelta(hours=24)  # Session timeout
        self.max_sessions_per_user = 5  # Maximum concurrent sessions per user
    
    def _get_session_key(self, session_id: str) -> str:
        """Get cache key for session"""
        return f"session:{session_id}"
    
    def _get_user_sessions_key(self, user_id: UUID) -> str:
        """Get cache key for user's sessions list"""
        return f"user_sessions:{user_id}"
    
    async def create_session(
        self,
        user_id: UUID,
        user_agent: str,
        ip_address: str,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None
    ) -> UserSession:
        """Create a new user session"""
        session_id = str(uuid4())
        now = datetime.now(timezone.utc)
        
        # Extract token JTIs if provided
        access_token_jti = None
        refresh_token_jti = None
        
        if access_token:
            access_token_jti = get_token_jti(access_token)
        
        if refresh_token:
            refresh_token_jti = get_token_jti(refresh_token)
        
        session = UserSession(
            session_id=session_id,
            user_id=user_id,
            user_agent=user_agent,
            ip_address=ip_address,
            created_at=now,
            last_activity=now,
            access_token_jti=access_token_jti,
            refresh_token_jti=refresh_token_jti
        )
        
        # Store session
        session_key = self._get_session_key(session_id)
        await cache_manager.set(
            session_key,
            session.to_dict(),
            ttl=cache_ttl(hours=24)  # 24 hour TTL
        )
        
        # Add to user's sessions list
        await self._add_to_user_sessions(user_id, session_id)
        
        # Clean up old sessions if too many
        await self._cleanup_old_sessions(user_id)
        
        logger.info(
            "Session created",
            user_id=str(user_id),
            session_id=session_id,
            ip_address=ip_address
        )
        
        return session
    
    async def get_session(self, session_id: str) -> Optional[UserSession]:
        """Get session by ID"""
        session_key = self._get_session_key(session_id)
        session_data = await cache_manager.get(session_key)
        
        if not session_data:
            return None
        
        try:
            return UserSession.from_dict(session_data)
        except Exception as e:
            logger.error("Failed to deserialize session", session_id=session_id, error=str(e))
            return None
    
    async def update_session_activity(self, session_id: str) -> bool:
        """Update session's last activity timestamp"""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        session.last_activity = datetime.now(timezone.utc)
        
        session_key = self._get_session_key(session_id)
        await cache_manager.set(
            session_key,
            session.to_dict(),
            ttl=cache_ttl(hours=24)
        )
        
        return True
    
    async def update_session_tokens(
        self,
        session_id: str,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None
    ) -> bool:
        """Update session's token JTIs"""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        if access_token:
            session.access_token_jti = get_token_jti(access_token)
        
        if refresh_token:
            session.refresh_token_jti = get_token_jti(refresh_token)
        
        session.last_activity = datetime.now(timezone.utc)
        
        session_key = self._get_session_key(session_id)
        await cache_manager.set(
            session_key,
            session.to_dict(),
            ttl=cache_ttl(hours=24)
        )
        
        return True
    
    async def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        session = await self.get_session(session_id)
        if not session:
            return False
        
        # Remove from user's sessions list
        await self._remove_from_user_sessions(session.user_id, session_id)
        
        # Delete session
        session_key = self._get_session_key(session_id)
        await cache_manager.delete(session_key)
        
        logger.info("Session deleted", session_id=session_id, user_id=str(session.user_id))
        return True
    
    async def get_user_sessions(self, user_id: UUID) -> List[UserSession]:
        """Get all sessions for a user"""
        user_sessions_key = self._get_user_sessions_key(user_id)
        session_ids = await cache_manager.get(user_sessions_key)
        
        if not session_ids:
            return []
        
        sessions = []
        for session_id in session_ids:
            session = await self.get_session(session_id)
            if session:
                sessions.append(session)
        
        # Sort by last activity (most recent first)
        sessions.sort(key=lambda s: s.last_activity, reverse=True)
        return sessions
    
    async def delete_user_sessions(self, user_id: UUID, except_session_id: Optional[str] = None) -> int:
        """Delete all sessions for a user (except optionally one)"""
        sessions = await self.get_user_sessions(user_id)
        deleted_count = 0
        
        for session in sessions:
            if except_session_id and session.session_id == except_session_id:
                continue
            
            if await self.delete_session(session.session_id):
                deleted_count += 1
        
        logger.info(
            "User sessions deleted",
            user_id=str(user_id),
            deleted_count=deleted_count,
            except_session=except_session_id
        )
        
        return deleted_count
    
    async def cleanup_expired_sessions(self) -> int:
        """Clean up expired sessions (should be run periodically)"""
        # This is a simplified cleanup - in production, you might want
        # to track sessions in a more structured way for efficient cleanup
        logger.info("Session cleanup completed")
        return 0  # Placeholder
    
    async def get_session_by_token_jti(self, jti: str) -> Optional[UserSession]:
        """Find session by token JTI"""
        # This is inefficient for large numbers of sessions
        # In production, consider indexing by JTI
        # For now, this is a placeholder implementation
        return None
    
    async def _add_to_user_sessions(self, user_id: UUID, session_id: str) -> None:
        """Add session ID to user's sessions list"""
        user_sessions_key = self._get_user_sessions_key(user_id)
        session_ids = await cache_manager.get(user_sessions_key)
        
        if not session_ids:
            session_ids = []
        
        session_ids.append(session_id)
        
        await cache_manager.set(
            user_sessions_key,
            session_ids,
            ttl=cache_ttl(hours=24)
        )
    
    async def _remove_from_user_sessions(self, user_id: UUID, session_id: str) -> None:
        """Remove session ID from user's sessions list"""
        user_sessions_key = self._get_user_sessions_key(user_id)
        session_ids = await cache_manager.get(user_sessions_key)
        
        if not session_ids:
            return
        
        try:
            session_ids.remove(session_id)
            await cache_manager.set(
                user_sessions_key,
                session_ids,
                ttl=cache_ttl(hours=24)
            )
        except ValueError:
            # Session ID not in list
            pass
    
    async def _cleanup_old_sessions(self, user_id: UUID) -> None:
        """Clean up old sessions if user has too many"""
        sessions = await self.get_user_sessions(user_id)
        
        if len(sessions) <= self.max_sessions_per_user:
            return
        
        # Sort by last activity and keep only the most recent ones
        sessions.sort(key=lambda s: s.last_activity, reverse=True)
        sessions_to_delete = sessions[self.max_sessions_per_user:]
        
        for session in sessions_to_delete:
            await self.delete_session(session.session_id)
        
        logger.info(
            "Old sessions cleaned up",
            user_id=str(user_id),
            deleted_count=len(sessions_to_delete)
        )


# Global session service instance
session_service = SessionService()