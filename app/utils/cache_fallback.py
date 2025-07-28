"""Cache fallback for when Redis is not available"""
from typing import Any, Optional


class FallbackCacheManager:
    """Fallback cache manager that does nothing when Redis is unavailable"""
    
    def __init__(self):
        self.redis = None
    
    async def connect(self) -> None:
        """No-op connect"""
        pass
    
    async def disconnect(self) -> None:
        """No-op disconnect"""
        pass
    
    async def get(self, key: str) -> Optional[Any]:
        """Always return None"""
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Always return True (fake success)"""
        return True
    
    async def delete(self, key: str) -> bool:
        """Always return True (fake success)"""
        return True
    
    async def delete_pattern(self, pattern: str) -> int:
        """Always return 0"""
        return 0
    
    async def exists(self, key: str) -> bool:
        """Always return False"""
        return False
    
    async def expire(self, key: str, ttl: int) -> bool:
        """Always return True (fake success)"""
        return True
    
    async def get_ttl(self, key: str) -> int:
        """Always return -1"""
        return -1