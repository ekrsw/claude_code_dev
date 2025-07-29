"""
Rate limiting middleware for API endpoints
"""
import time
from typing import Callable, Dict, Optional
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
import structlog

from app.core.config import settings
from app.utils.cache import cache_manager, cache_ttl

logger = structlog.get_logger()


class RateLimiter:
    """Rate limiter using Redis/cache for storage"""
    
    def __init__(
        self,
        requests_per_minute: int = settings.RATE_LIMIT_PER_MINUTE,
        window_seconds: int = 60
    ):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
    
    async def is_allowed(self, key: str) -> tuple[bool, Dict]:
        """Check if request is allowed and return rate limit info"""
        current_time = int(time.time())
        window_start = current_time - self.window_seconds
        
        # Use sliding window counter
        cache_key = f"rate_limit:{key}"
        
        # Get current request count
        count_str = await cache_manager.get(cache_key)
        if count_str is None:
            count = 0
            requests = []
        else:
            # Parse stored data: "count:timestamp1,timestamp2,..."
            parts = count_str.split(":")
            count = int(parts[0]) if parts[0] else 0
            requests = [int(t) for t in parts[1].split(",") if t and int(t) > window_start] if len(parts) > 1 else []
        
        # Clean old requests
        requests = [t for t in requests if t > window_start]
        count = len(requests)
        
        # Check if limit exceeded
        if count >= self.requests_per_minute:
            rate_limit_info = {
                "limit": self.requests_per_minute,
                "remaining": 0,
                "reset": window_start + self.window_seconds + 1,
                "window": self.window_seconds
            }
            return False, rate_limit_info
        
        # Add current request
        requests.append(current_time)
        count = len(requests)
        
        # Store updated data
        new_data = f"{count}:{','.join(map(str, requests))}"
        await cache_manager.set(
            cache_key, 
            new_data, 
            ttl=cache_ttl(seconds=self.window_seconds + 10)
        )
        
        rate_limit_info = {
            "limit": self.requests_per_minute,
            "remaining": max(0, self.requests_per_minute - count),
            "reset": window_start + self.window_seconds + 1,
            "window": self.window_seconds
        }
        
        return True, rate_limit_info
    
    def get_client_identifier(self, request: Request) -> str:
        """Get client identifier for rate limiting"""
        # Try to get user ID from request state (set by auth middleware)
        if hasattr(request.state, "user_id"):
            return f"user:{request.state.user_id}"
        
        # Fall back to IP address
        client_ip = request.client.host
        
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            client_ip = real_ip.strip()
        
        return f"ip:{client_ip}"


# Global rate limiter instance
rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
    """Rate limiting middleware"""
    if not settings.RATE_LIMIT_ENABLED:
        return await call_next(request)
    
    # Skip rate limiting for health checks and static files
    if request.url.path.startswith(("/health", "/docs", "/redoc", "/openapi")):
        return await call_next(request)
    
    client_id = rate_limiter.get_client_identifier(request)
    
    try:
        allowed, rate_info = await rate_limiter.is_allowed(client_id)
        
        if not allowed:
            logger.warning(
                "Rate limit exceeded",
                client_id=client_id,
                path=request.url.path,
                method=request.method
            )
            
            # Return rate limit exceeded response
            headers = {
                "X-RateLimit-Limit": str(rate_info["limit"]),
                "X-RateLimit-Remaining": str(rate_info["remaining"]),
                "X-RateLimit-Reset": str(rate_info["reset"]),
                "Retry-After": str(rate_info["reset"] - int(time.time()))
            }
            
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Too many requests."},
                headers=headers
            )
        
        # Process request
        response = await call_next(request)
        
        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rate_info["reset"])
        
        return response
        
    except Exception as e:
        logger.error("Rate limiting error", error=str(e), client_id=client_id)
        # Continue processing if rate limiting fails
        return await call_next(request)


class RateLimitException(HTTPException):
    """Rate limit exceeded exception"""
    
    def __init__(self, rate_info: Dict):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded"
        )
        self.rate_info = rate_info