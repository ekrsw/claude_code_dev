"""
Security audit logging service for tracking authentication and authorization events
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any
from uuid import UUID
import structlog

from app.utils.cache import cache_manager, cache_ttl

logger = structlog.get_logger()


class SecurityEventType(Enum):
    """Types of security events to log"""
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGE = "password_change"
    ACCOUNT_LOCKED = "account_locked"
    PERMISSION_DENIED = "permission_denied"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    SESSION_EXPIRED = "session_expired"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    TOKEN_REFRESH = "token_refresh"
    PRIVILEGE_ESCALATION = "privilege_escalation"


class SecurityAuditService:
    """Service for logging and monitoring security events"""
    
    def __init__(self):
        self.failed_login_threshold = 5  # Failed attempts before flagging
        self.suspicious_activity_window = 300  # 5 minutes in seconds
    
    async def log_security_event(
        self,
        event_type: SecurityEventType,
        user_id: Optional[UUID] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "info"
    ) -> None:
        """Log a security event"""
        event_data = {
            "event_type": event_type.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_id": str(user_id) if user_id else None,
            "username": username,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "details": details or {},
            "severity": severity
        }
        
        # Log to structured logger
        logger.bind(**event_data).info(
            f"Security event: {event_type.value}",
            severity=severity
        )
        
        # Store in cache for recent activity tracking
        await self._store_recent_event(event_data)
        
        # Check for suspicious patterns
        await self._check_suspicious_activity(event_data)
    
    async def log_login_success(
        self,
        user_id: UUID,
        username: str,
        ip_address: str,
        user_agent: str,
        session_info: Optional[Dict] = None
    ) -> None:
        """Log successful login"""
        details = {"session_info": session_info} if session_info else {}
        
        await self.log_security_event(
            event_type=SecurityEventType.LOGIN_SUCCESS,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            severity="info"
        )
        
        # Clear failed login counter on success
        await self._clear_failed_login_counter(ip_address, username)
    
    async def log_login_failed(
        self,
        username: str,
        ip_address: str,
        user_agent: str,
        reason: str = "invalid_credentials"
    ) -> None:
        """Log failed login attempt"""
        details = {"reason": reason}
        
        await self.log_security_event(
            event_type=SecurityEventType.LOGIN_FAILED,
            username=username,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details,
            severity="warning"
        )
        
        # Track failed attempts
        failed_count = await self._increment_failed_login_counter(ip_address, username)
        
        # Log suspicious activity if threshold exceeded
        if failed_count >= self.failed_login_threshold:
            await self.log_security_event(
                event_type=SecurityEventType.SUSPICIOUS_ACTIVITY,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                details={
                    "activity_type": "brute_force_attempt",
                    "failed_attempts": failed_count,
                    "threshold": self.failed_login_threshold
                },
                severity="critical"
            )
    
    async def log_logout(
        self,
        user_id: UUID,
        username: str,
        session_id: Optional[str] = None,
        logout_type: str = "normal"
    ) -> None:
        """Log user logout"""
        details = {
            "session_id": session_id,
            "logout_type": logout_type
        }
        
        await self.log_security_event(
            event_type=SecurityEventType.LOGOUT,
            user_id=user_id,
            username=username,
            details=details,
            severity="info"
        )
    
    async def log_password_change(
        self,
        user_id: UUID,
        username: str,
        changed_by_admin: bool = False,
        ip_address: Optional[str] = None
    ) -> None:
        """Log password change"""
        details = {
            "changed_by_admin": changed_by_admin,
            "password_strength_checked": True
        }
        
        await self.log_security_event(
            event_type=SecurityEventType.PASSWORD_CHANGE,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            details=details,
            severity="info"
        )
    
    async def log_permission_denied(
        self,
        user_id: UUID,
        username: str,
        resource: str,
        action: str,
        ip_address: Optional[str] = None
    ) -> None:
        """Log permission denied event"""
        details = {
            "resource": resource,
            "action": action,
            "required_permission": f"{action}:{resource}"
        }
        
        await self.log_security_event(
            event_type=SecurityEventType.PERMISSION_DENIED,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            details=details,
            severity="warning"
        )
    
    async def log_rate_limit_exceeded(
        self,
        ip_address: str,
        endpoint: str,
        user_id: Optional[UUID] = None,
        username: Optional[str] = None
    ) -> None:
        """Log rate limit exceeded"""
        details = {
            "endpoint": endpoint,
            "limit_type": "rate_limit"
        }
        
        await self.log_security_event(
            event_type=SecurityEventType.RATE_LIMIT_EXCEEDED,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            details=details,
            severity="warning"
        )
    
    async def get_recent_security_events(
        self,
        user_id: Optional[UUID] = None,
        event_type: Optional[SecurityEventType] = None,
        hours: int = 24
    ) -> list:
        """Get recent security events (placeholder - would need proper storage)"""
        # This is a placeholder implementation
        # In production, you'd want to use a proper logging storage system
        return []
    
    async def _store_recent_event(self, event_data: Dict[str, Any]) -> None:
        """Store event for recent activity tracking"""
        try:
            # Store in cache with timestamp key for easy retrieval
            timestamp_key = f"security_event:{int(datetime.now().timestamp())}"
            await cache_manager.set(
                timestamp_key,
                event_data,
                ttl=cache_ttl(hours=24)  # Keep for 24 hours
            )
        except Exception as e:
            logger.error("Failed to store security event", error=str(e))
    
    async def _increment_failed_login_counter(
        self,
        ip_address: str,
        username: str
    ) -> int:
        """Increment and return failed login counter"""
        # Track by both IP and username
        ip_key = f"failed_login:ip:{ip_address}"
        username_key = f"failed_login:username:{username}"
        
        try:
            # Increment IP-based counter
            ip_count_str = await cache_manager.get(ip_key)
            ip_count = int(ip_count_str) if ip_count_str else 0
            ip_count += 1
            await cache_manager.set(
                ip_key,
                str(ip_count),
                ttl=cache_ttl(hours=1)  # Reset after 1 hour
            )
            
            # Increment username-based counter
            username_count_str = await cache_manager.get(username_key)
            username_count = int(username_count_str) if username_count_str else 0
            username_count += 1
            await cache_manager.set(
                username_key,
                str(username_count),
                ttl=cache_ttl(hours=1)  # Reset after 1 hour
            )
            
            # Return the higher count for alerting
            return max(ip_count, username_count)
            
        except Exception as e:
            logger.error("Failed to increment failed login counter", error=str(e))
            return 0
    
    async def _clear_failed_login_counter(
        self,
        ip_address: str,
        username: str
    ) -> None:
        """Clear failed login counters on successful login"""
        try:
            ip_key = f"failed_login:ip:{ip_address}"
            username_key = f"failed_login:username:{username}"
            
            await cache_manager.delete(ip_key)
            await cache_manager.delete(username_key)
        except Exception as e:
            logger.error("Failed to clear failed login counter", error=str(e))
    
    async def _check_suspicious_activity(self, event_data: Dict[str, Any]) -> None:
        """Check for suspicious activity patterns"""
        # This is a simplified implementation
        # In production, you'd implement more sophisticated pattern detection
        
        event_type = event_data.get("event_type")
        severity = event_data.get("severity")
        
        # Alert on critical events
        if severity == "critical":
            logger.warning(
                "Critical security event detected",
                event_type=event_type,
                **event_data
            )


# Global security audit service instance
security_audit = SecurityAuditService()