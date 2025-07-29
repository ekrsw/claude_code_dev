"""
Test cases for cache utilities
"""
import json
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.utils.cache import CacheManager, CacheKeys, cache_ttl


class TestCacheManager:
    """Test cases for CacheManager class"""
    
    def setup_method(self):
        """Setup test data"""
        self.cache_manager = CacheManager()
    
    @pytest.mark.asyncio
    async def test_init(self):
        """Test CacheManager initialization"""
        assert self.cache_manager.redis is None
        assert isinstance(self.cache_manager.url, str)
        assert isinstance(self.cache_manager.default_ttl, int)
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(True, reason="aioredis not available in test environment")
    async def test_connect_success(self):
        """Test successful Redis connection"""
        # Skip this test since aioredis is not available
        pass
    
    @pytest.mark.asyncio
    @pytest.mark.skipif(True, reason="aioredis not available in test environment")
    async def test_connect_failure(self):
        """Test Redis connection failure"""
        # Skip this test since aioredis is not available
        pass
    
    @pytest.mark.asyncio
    async def test_disconnect_with_redis(self):
        """Test disconnect when Redis connection exists"""
        mock_redis = AsyncMock()
        self.cache_manager.redis = mock_redis
        
        await self.cache_manager.disconnect()
        
        mock_redis.close.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_disconnect_without_redis(self):
        """Test disconnect when no Redis connection"""
        self.cache_manager.redis = None
        
        # Should not raise any exception
        await self.cache_manager.disconnect()
    
    @pytest.mark.asyncio
    async def test_get_no_redis(self):
        """Test get when Redis not available"""
        self.cache_manager.redis = None
        
        result = await self.cache_manager.get("test_key")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_json_value(self):
        """Test get with JSON value"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = '{"name": "test", "value": 123}'
        self.cache_manager.redis = mock_redis
        
        result = await self.cache_manager.get("test_key")
        
        assert result == {"name": "test", "value": 123}
        mock_redis.get.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_get_string_value(self):
        """Test get with string value"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "simple_string"
        self.cache_manager.redis = mock_redis
        
        result = await self.cache_manager.get("test_key")
        
        assert result == "simple_string"
    
    @pytest.mark.asyncio
    async def test_get_none_value(self):
        """Test get when key doesn't exist"""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None
        self.cache_manager.redis = mock_redis
        
        result = await self.cache_manager.get("test_key")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_error(self):
        """Test get with Redis error"""
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = Exception("Redis error")
        self.cache_manager.redis = mock_redis
        
        result = await self.cache_manager.get("test_key")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_set_no_redis(self):
        """Test set when Redis not available"""
        self.cache_manager.redis = None
        
        result = await self.cache_manager.set("test_key", "test_value")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_set_string_value(self):
        """Test set with string value"""
        mock_redis = AsyncMock()
        self.cache_manager.redis = mock_redis
        
        result = await self.cache_manager.set("test_key", "test_value")
        
        assert result is True
        mock_redis.setex.assert_called_once()
        args, kwargs = mock_redis.setex.call_args
        assert args[0] == "test_key"
        assert args[2] == "test_value"  # serialized value
    
    @pytest.mark.asyncio
    async def test_set_dict_value(self):
        """Test set with dictionary value"""
        mock_redis = AsyncMock()
        self.cache_manager.redis = mock_redis
        test_dict = {"name": "test", "value": 123}
        
        result = await self.cache_manager.set("test_key", test_dict)
        
        assert result is True
        mock_redis.setex.assert_called_once()
        args, kwargs = mock_redis.setex.call_args
        assert args[0] == "test_key"  # key
        assert json.loads(args[2]) == test_dict  # serialized value
    
    @pytest.mark.asyncio
    async def test_set_with_ttl(self):
        """Test set with custom TTL"""
        mock_redis = AsyncMock()
        self.cache_manager.redis = mock_redis
        
        result = await self.cache_manager.set("test_key", "test_value", ttl=300)
        
        assert result is True
        args, kwargs = mock_redis.setex.call_args
        assert args[1] == 300  # TTL
    
    @pytest.mark.asyncio
    async def test_set_error(self):
        """Test set with Redis error"""
        mock_redis = AsyncMock()
        mock_redis.setex.side_effect = Exception("Redis error")
        self.cache_manager.redis = mock_redis
        
        result = await self.cache_manager.set("test_key", "test_value")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_no_redis(self):
        """Test delete when Redis not available"""
        self.cache_manager.redis = None
        
        result = await self.cache_manager.delete("test_key")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_success(self):
        """Test successful delete"""
        mock_redis = AsyncMock()
        mock_redis.delete.return_value = 1
        self.cache_manager.redis = mock_redis
        
        result = await self.cache_manager.delete("test_key")
        
        assert result is True
        mock_redis.delete.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        """Test delete when key not found"""
        mock_redis = AsyncMock()
        mock_redis.delete.return_value = 0
        self.cache_manager.redis = mock_redis
        
        result = await self.cache_manager.delete("test_key")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_error(self):
        """Test delete with Redis error"""
        mock_redis = AsyncMock()
        mock_redis.delete.side_effect = Exception("Redis error")
        self.cache_manager.redis = mock_redis
        
        result = await self.cache_manager.delete("test_key")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_delete_pattern_no_redis(self):
        """Test delete_pattern when Redis not available"""
        self.cache_manager.redis = None
        
        result = await self.cache_manager.delete_pattern("test:*")
        
        assert result == 0
    
    @pytest.mark.asyncio
    async def test_delete_pattern_success(self):
        """Test successful delete_pattern"""
        mock_redis = AsyncMock()
        mock_redis.keys.return_value = ["test:1", "test:2"]
        mock_redis.delete.return_value = 2
        self.cache_manager.redis = mock_redis
        
        result = await self.cache_manager.delete_pattern("test:*")
        
        assert result == 2
        mock_redis.keys.assert_called_once_with("test:*")
        mock_redis.delete.assert_called_once_with("test:1", "test:2")
    
    @pytest.mark.asyncio
    async def test_delete_pattern_no_keys(self):
        """Test delete_pattern when no keys match"""
        mock_redis = AsyncMock()
        mock_redis.keys.return_value = []
        self.cache_manager.redis = mock_redis
        
        result = await self.cache_manager.delete_pattern("test:*")
        
        assert result == 0
        mock_redis.delete.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_exists_no_redis(self):
        """Test exists when Redis not available"""
        self.cache_manager.redis = None
        
        result = await self.cache_manager.exists("test_key")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_exists_true(self):
        """Test exists when key exists"""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 1
        self.cache_manager.redis = mock_redis
        
        result = await self.cache_manager.exists("test_key")
        
        assert result is True
        mock_redis.exists.assert_called_once_with("test_key")
    
    @pytest.mark.asyncio
    async def test_exists_false(self):
        """Test exists when key doesn't exist"""
        mock_redis = AsyncMock()
        mock_redis.exists.return_value = 0
        self.cache_manager.redis = mock_redis
        
        result = await self.cache_manager.exists("test_key")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_expire_no_redis(self):
        """Test expire when Redis not available"""
        self.cache_manager.redis = None
        
        result = await self.cache_manager.expire("test_key", 300)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_expire_success(self):
        """Test successful expire"""
        mock_redis = AsyncMock()
        mock_redis.expire.return_value = True
        self.cache_manager.redis = mock_redis
        
        result = await self.cache_manager.expire("test_key", 300)
        
        assert result is True
        mock_redis.expire.assert_called_once_with("test_key", 300)
    
    @pytest.mark.asyncio
    async def test_get_ttl_no_redis(self):
        """Test get_ttl when Redis not available"""
        self.cache_manager.redis = None
        
        result = await self.cache_manager.get_ttl("test_key")
        
        assert result == -1
    
    @pytest.mark.asyncio
    async def test_get_ttl_success(self):
        """Test successful get_ttl"""
        mock_redis = AsyncMock()
        mock_redis.ttl.return_value = 300
        self.cache_manager.redis = mock_redis
        
        result = await self.cache_manager.get_ttl("test_key")
        
        assert result == 300
        mock_redis.ttl.assert_called_once_with("test_key")
    
    def test_json_serializer_datetime(self):
        """Test JSON serializer with datetime"""
        test_datetime = datetime(2023, 1, 1, 12, 0, 0)
        
        result = self.cache_manager._json_serializer(test_datetime)
        
        assert result == "2023-01-01T12:00:00"
    
    def test_json_serializer_unsupported(self):
        """Test JSON serializer with unsupported type"""
        class UnsupportedType:
            pass
        
        with pytest.raises(TypeError):
            self.cache_manager._json_serializer(UnsupportedType())
    
    def test_make_key(self):
        """Test make_key method"""
        result = self.cache_manager.make_key("user", 123, "profile")
        
        assert result == "user:123:profile"


class TestCacheKeys:
    """Test cases for CacheKeys class"""
    
    def test_user_key(self):
        """Test user cache key generation"""
        result = CacheKeys.user("user123")
        assert result == "user:user123"
    
    def test_user_by_username_key(self):
        """Test user by username cache key generation"""
        result = CacheKeys.user_by_username("john_doe")
        assert result == "user:username:john_doe"
    
    def test_article_key(self):
        """Test article cache key generation"""
        result = CacheKeys.article("ARTICLE001")
        assert result == "article:ARTICLE001"
    
    def test_article_list_key(self):
        """Test article list cache key generation"""
        result = CacheKeys.article_list(1, 10, "status=active")
        assert result == "articles:list:1:10:status=active"
    
    def test_article_list_key_no_filters(self):
        """Test article list cache key without filters"""
        result = CacheKeys.article_list(2, 20)
        assert result == "articles:list:2:20:"
    
    def test_revision_key(self):
        """Test revision cache key generation"""
        result = CacheKeys.revision("rev123")
        assert result == "revision:rev123"
    
    def test_revision_list_key(self):
        """Test revision list cache key generation"""
        result = CacheKeys.revision_list("user123", "DRAFT", 1, 20)
        assert result == "revisions:list:user123:DRAFT:1:20"
    
    def test_revision_list_key_defaults(self):
        """Test revision list cache key with defaults"""
        result = CacheKeys.revision_list("user123")
        assert result == "revisions:list:user123::1:20"
    
    def test_categories_key(self):
        """Test categories cache key generation"""
        result = CacheKeys.categories()        
        assert result == "categories:all"
    
    def test_jwt_blacklist_key(self):
        """Test JWT blacklist cache key generation"""
        result = CacheKeys.jwt_blacklist("token_jti_123")
        assert result == "jwt:blacklist:token_jti_123"


class TestCacheTTL:
    """Test cases for cache_ttl function"""
    
    def test_cache_ttl_hours(self):
        """Test cache_ttl with hours"""
        result = cache_ttl(hours=2)
        assert result == 7200  # 2 * 3600
    
    def test_cache_ttl_minutes(self):
        """Test cache_ttl with minutes"""
        result = cache_ttl(minutes=30)
        assert result == 1800  # 30 * 60
    
    def test_cache_ttl_seconds(self):
        """Test cache_ttl with seconds"""
        result = cache_ttl(seconds=45)
        assert result == 45
    
    def test_cache_ttl_combined(self):
        """Test cache_ttl with combined time units"""
        result = cache_ttl(hours=1, minutes=30, seconds=45)
        assert result == 5445  # 3600 + 1800 + 45
    
    def test_cache_ttl_zero(self):
        """Test cache_ttl with zero values"""
        result = cache_ttl()
        assert result == 0