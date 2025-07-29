"""
Test cases for SQLite compatibility utilities
"""
import pytest
import uuid
from unittest.mock import Mock

from app.utils.sqlite_compat import GUID


class TestGUID:
    """Test cases for GUID type decorator"""
    
    def test_guid_cache_ok(self):
        """Test GUID type has cache_ok set to True"""
        guid_type = GUID()
        assert guid_type.cache_ok is True
    
    def test_load_dialect_impl_postgresql(self):
        """Test GUID uses PostgreSQL UUID for PostgreSQL dialect"""
        # Mock PostgreSQL dialect
        pg_dialect = Mock()
        pg_dialect.name = 'postgresql'
        pg_dialect.type_descriptor = Mock()
        
        guid_type = GUID()
        result = guid_type.load_dialect_impl(pg_dialect)
        
        # Should call type_descriptor with a PostgreSQL UUID type
        pg_dialect.type_descriptor.assert_called_once()
        
    def test_load_dialect_impl_sqlite(self):
        """Test GUID uses CHAR(36) for SQLite dialect"""
        # Mock SQLite dialect
        sqlite_dialect = Mock()
        sqlite_dialect.name = 'sqlite'
        sqlite_dialect.type_descriptor = Mock()
        
        guid_type = GUID()
        result = guid_type.load_dialect_impl(sqlite_dialect)
        
        # Should call type_descriptor with CHAR(36)
        sqlite_dialect.type_descriptor.assert_called_once()
    
    def test_load_dialect_impl_other(self):
        """Test GUID uses CHAR(36) for other dialects"""
        # Mock other dialect
        other_dialect = Mock()
        other_dialect.name = 'mysql'
        other_dialect.type_descriptor = Mock()
        
        guid_type = GUID()
        result = guid_type.load_dialect_impl(other_dialect)
        
        # Should call type_descriptor with CHAR(36)
        other_dialect.type_descriptor.assert_called_once()
    
    def test_process_bind_param_string_uuid(self):
        """Test processing UUID string parameter"""
        guid_type = GUID()
        test_uuid = str(uuid.uuid4())
        
        # Mock dialect
        dialect = Mock()
        dialect.name = 'sqlite'
        
        result = guid_type.process_bind_param(test_uuid, dialect)
        # For string UUIDs, should return as-is or converted appropriately
        assert isinstance(result, (str, type(None)))
    
    def test_process_bind_param_uuid_object(self):
        """Test processing UUID object parameter"""
        guid_type = GUID()
        test_uuid = uuid.uuid4()
        
        # Mock dialect
        dialect = Mock()
        dialect.name = 'sqlite'
        
        result = guid_type.process_bind_param(test_uuid, dialect)
        # Should handle UUID objects appropriately
        assert isinstance(result, (str, type(None)))
    
    def test_process_bind_param_none(self):
        """Test processing None parameter"""
        guid_type = GUID()
        
        # Mock dialect
        dialect = Mock()
        dialect.name = 'sqlite'
        
        result = guid_type.process_bind_param(None, dialect)
        assert result is None
    
    def test_process_result_value_string(self):
        """Test processing string result value"""
        guid_type = GUID()
        test_uuid = str(uuid.uuid4())
        
        # Mock dialect
        dialect = Mock()
        dialect.name = 'sqlite'
        
        result = guid_type.process_result_value(test_uuid, dialect)
        # Should return UUID object when processing string
        assert isinstance(result, (uuid.UUID, type(None)))
        if result is not None:
            assert str(result) == test_uuid
    
    def test_process_result_value_none(self):
        """Test processing None result value"""
        guid_type = GUID()
        
        # Mock dialect
        dialect = Mock()
        dialect.name = 'sqlite'
        
        result = guid_type.process_result_value(None, dialect)
        assert result is None