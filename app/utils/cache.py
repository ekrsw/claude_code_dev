import json
from typing import Any, Optional, Union
from datetime import datetime, timedelta

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

import structlog

from app.core.config import settings

logger = structlog.get_logger()


class CacheManager:
    """Redis cache manager"""
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.url = str(settings.REDIS_URL)
        self.default_ttl = settings.REDIS_TTL_SECONDS
    
    async def connect(self) -> None:
        """Connect to Redis"""
        try:
            self.redis = aioredis.from_url(
                self.url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                retry_on_timeout=True,
                health_check_interval=30,
            )
            # Test connection
            await self.redis.ping()
            logger.info("Connected to Redis", url=self.url)
        except Exception as e:
            logger.error("Failed to connect to Redis", error=str(e), url=self.url)
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        if self.redis:
            await self.redis.close()
            logger.info("Disconnected from Redis")
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.redis:
            return None
        
        try:
            value = await self.redis.get(key)
            if value is None:
                return None
            
            # Try to parse as JSON, fallback to string
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception as e:
            logger.error("Cache get error", key=key, error=str(e))
            return None
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ) -> bool:
        """Set value in cache"""
        if not self.redis:
            return False
        
        try:
            # Serialize value to JSON if it's not a string
            if isinstance(value, str):
                serialized_value = value
            else:
                serialized_value = json.dumps(
                    value, 
                    default=self._json_serializer,
                    ensure_ascii=False
                )
            
            ttl = ttl or self.default_ttl
            await self.redis.setex(key, ttl, serialized_value)
            return True
        except Exception as e:
            logger.error("Cache set error", key=key, error=str(e))
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.redis:
            return False
        
        try:
            result = await self.redis.delete(key)
            return result > 0
        except Exception as e:
            logger.error("Cache delete error", key=key, error=str(e))
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete keys matching pattern"""
        if not self.redis:
            return 0
        
        try:
            keys = await self.redis.keys(pattern)
            if keys:
                return await self.redis.delete(*keys)
            return 0
        except Exception as e:
            logger.error("Cache delete pattern error", pattern=pattern, error=str(e))
            return 0
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self.redis:
            return False
        
        try:
            return await self.redis.exists(key) > 0
        except Exception as e:
            logger.error("Cache exists error", key=key, error=str(e))
            return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Set expiration for key"""
        if not self.redis:
            return False
        
        try:
            return await self.redis.expire(key, ttl)
        except Exception as e:
            logger.error("Cache expire error", key=key, ttl=ttl, error=str(e))
            return False
    
    async def get_ttl(self, key: str) -> int:
        """Get TTL for key"""
        if not self.redis:
            return -1
        
        try:
            return await self.redis.ttl(key)
        except Exception as e:
            logger.error("Cache get TTL error", key=key, error=str(e))
            return -1
    
    def _json_serializer(self, obj: Any) -> Any:
        """JSON serializer for datetime objects"""
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    def make_key(self, *parts: Union[str, int]) -> str:
        """Create cache key from parts"""
        return ":".join(str(part) for part in parts)


# Global cache manager instance
if REDIS_AVAILABLE and settings.REDIS_URL:
    try:
        cache_manager = CacheManager()
    except Exception:
        from app.utils.cache_fallback import FallbackCacheManager
        cache_manager = FallbackCacheManager()
else:
    from app.utils.cache_fallback import FallbackCacheManager
    cache_manager = FallbackCacheManager()


# Cache key generators
class CacheKeys:
    """Cache key generators"""
    
    @staticmethod
    def user(user_id: str) -> str:
        return f"user:{user_id}"
    
    @staticmethod
    def user_by_username(username: str) -> str:
        return f"user:username:{username}"
    
    @staticmethod
    def article(article_id: str) -> str:
        return f"article:{article_id}"
    
    @staticmethod
    def article_list(page: int, size: int, filters: str = "") -> str:
        return f"articles:list:{page}:{size}:{filters}"
    
    @staticmethod
    def revision(revision_id: str) -> str:
        return f"revision:{revision_id}"
    
    @staticmethod
    def revision_list(
        user_id: str, 
        status: str = "", 
        page: int = 1, 
        size: int = 20
    ) -> str:
        return f"revisions:list:{user_id}:{status}:{page}:{size}"
    
    @staticmethod
    def categories() -> str:
        return "categories:all"
    
    @staticmethod
    def jwt_blacklist(token_jti: str) -> str:
        return f"jwt:blacklist:{token_jti}"


# Cache decorators and utilities
def cache_ttl(hours: int = 0, minutes: int = 0, seconds: int = 0) -> int:
    """Calculate TTL in seconds"""
    return hours * 3600 + minutes * 60 + seconds