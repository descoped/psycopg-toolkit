"""Unit tests for BaseRepository data preprocessing and postprocessing."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from psycopg_toolkit.repositories.base import BaseRepository
from psycopg_toolkit.exceptions import JSONSerializationError


class SampleJSONModel(BaseModel):
    """Sample model with JSON fields for testing."""
    id: UUID = Field(default_factory=uuid4)
    name: str
    value: int
    
    # JSON fields that should be processed
    metadata: Dict[str, Any]
    tags: List[str]
    settings: Optional[Dict[str, str]] = None


class NonJSONModel(BaseModel):
    """Sample model without JSON fields."""
    id: UUID = Field(default_factory=uuid4)
    name: str
    active: bool


class TestBaseRepositoryDataProcessing:
    """Test BaseRepository data preprocessing and postprocessing functionality."""
    
    @pytest.fixture
    def mock_connection(self):
        """Create a mock database connection."""
        return AsyncMock()
    
    @pytest.fixture
    def json_repo(self, mock_connection):
        """Create a repository with JSON fields."""
        return BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=SampleJSONModel,
            primary_key="id"
        )
    
    @pytest.fixture
    def non_json_repo(self, mock_connection):
        """Create a repository without JSON fields."""
        return BaseRepository(
            db_connection=mock_connection,
            table_name="simple_table",
            model_class=NonJSONModel,
            primary_key="id"
        )
    
    def test_preprocess_data_with_json_fields(self, json_repo):
        """Test preprocessing data with JSON fields."""
        test_data = {
            "name": "test_item",
            "value": 42,
            "metadata": {"key": "value", "number": 123},
            "tags": ["tag1", "tag2"],
            "settings": {"theme": "dark"}
        }
        
        processed = json_repo._preprocess_data(test_data)
        
        # Non-JSON fields should remain unchanged
        assert processed["name"] == "test_item"
        assert processed["value"] == 42
        
        # JSON fields should be serialized to strings
        assert isinstance(processed["metadata"], str)
        assert isinstance(processed["tags"], str)
        assert isinstance(processed["settings"], str)
        
        # Verify serialized content
        import json
        assert json.loads(processed["metadata"]) == {"key": "value", "number": 123}
        assert json.loads(processed["tags"]) == ["tag1", "tag2"]
        assert json.loads(processed["settings"]) == {"theme": "dark"}
    
    def test_preprocess_data_with_none_values(self, json_repo):
        """Test preprocessing data with None values in JSON fields."""
        test_data = {
            "name": "test_item",
            "value": 42,
            "metadata": {"key": "value"},
            "tags": ["tag1"],
            "settings": None  # None value should not be processed
        }
        
        processed = json_repo._preprocess_data(test_data)
        
        # None values should remain None
        assert processed["settings"] is None
        
        # Other JSON fields should be processed
        assert isinstance(processed["metadata"], str)
        assert isinstance(processed["tags"], str)
    
    def test_preprocess_data_missing_json_fields(self, json_repo):
        """Test preprocessing data with missing JSON fields."""
        test_data = {
            "name": "test_item",
            "value": 42,
            "metadata": {"key": "value"}
            # Missing 'tags' and 'settings' fields
        }
        
        processed = json_repo._preprocess_data(test_data)
        
        # Missing fields should not be added
        assert "tags" not in processed
        assert "settings" not in processed
        
        # Present JSON field should be processed
        assert isinstance(processed["metadata"], str)
    
    def test_preprocess_data_no_json_fields(self, non_json_repo):
        """Test preprocessing data when no JSON fields are configured."""
        test_data = {
            "name": "test_item",
            "active": True
        }
        
        processed = non_json_repo._preprocess_data(test_data)
        
        # Data should be unchanged but copied
        assert processed == test_data
        assert processed is not test_data  # Should be a copy
    
    def test_preprocess_data_complex_types(self, json_repo):
        """Test preprocessing with complex data types."""
        test_uuid = uuid4()
        test_datetime = datetime.now()
        test_decimal = Decimal("123.45")
        
        test_data = {
            "name": "complex_test",
            "value": 42,
            "metadata": {
                "uuid": test_uuid,
                "timestamp": test_datetime,
                "amount": test_decimal,
                "nested": {"deep": {"value": "test"}}
            },
            "tags": ["tag1", "tag2"]
        }
        
        processed = json_repo._preprocess_data(test_data)
        
        # Verify complex types are serialized correctly
        import json
        metadata_dict = json.loads(processed["metadata"])
        assert metadata_dict["uuid"] == str(test_uuid)
        assert metadata_dict["timestamp"] == test_datetime.isoformat()
        assert metadata_dict["amount"] == float(test_decimal)
        assert metadata_dict["nested"]["deep"]["value"] == "test"
    
    def test_preprocess_data_serialization_error(self, json_repo):
        """Test preprocessing with data that cannot be serialized."""
        # Create a non-serializable object
        class NonSerializable:
            pass
        
        test_data = {
            "name": "test_item",
            "value": 42,
            "metadata": {"bad_data": NonSerializable()}
        }
        
        with pytest.raises(JSONSerializationError, match="JSON serialization failed"):
            json_repo._preprocess_data(test_data)
    
    def test_postprocess_data_with_json_fields(self, json_repo):
        """Test postprocessing data with JSON fields."""
        test_data = {
            "name": "test_item",
            "value": 42,
            "metadata": '{"key": "value", "number": 123}',
            "tags": '["tag1", "tag2"]',
            "settings": '{"theme": "dark"}'
        }
        
        processed = json_repo._postprocess_data(test_data)
        
        # Non-JSON fields should remain unchanged
        assert processed["name"] == "test_item"
        assert processed["value"] == 42
        
        # JSON fields should be deserialized
        assert processed["metadata"] == {"key": "value", "number": 123}
        assert processed["tags"] == ["tag1", "tag2"]
        assert processed["settings"] == {"theme": "dark"}
    
    def test_postprocess_data_with_none_values(self, json_repo):
        """Test postprocessing data with None values in JSON fields."""
        test_data = {
            "name": "test_item",
            "value": 42,
            "metadata": '{"key": "value"}',
            "tags": '["tag1"]',
            "settings": None  # None value should not be processed
        }
        
        processed = json_repo._postprocess_data(test_data)
        
        # None values should remain None
        assert processed["settings"] is None
        
        # Other JSON fields should be processed
        assert processed["metadata"] == {"key": "value"}
        assert processed["tags"] == ["tag1"]
    
    def test_postprocess_data_missing_json_fields(self, json_repo):
        """Test postprocessing data with missing JSON fields."""
        test_data = {
            "name": "test_item",
            "value": 42,
            "metadata": '{"key": "value"}'
            # Missing 'tags' and 'settings' fields
        }
        
        processed = json_repo._postprocess_data(test_data)
        
        # Missing fields should not be added
        assert "tags" not in processed
        assert "settings" not in processed
        
        # Present JSON field should be processed
        assert processed["metadata"] == {"key": "value"}
    
    def test_postprocess_data_no_json_fields(self, non_json_repo):
        """Test postprocessing data when no JSON fields are configured."""
        test_data = {
            "name": "test_item",
            "active": True
        }
        
        processed = non_json_repo._postprocess_data(test_data)
        
        # Data should be unchanged but copied
        assert processed == test_data
        assert processed is not test_data  # Should be a copy
    
    def test_postprocess_data_invalid_json(self, json_repo):
        """Test postprocessing with invalid JSON data."""
        test_data = {
            "name": "test_item",
            "value": 42,
            "metadata": "invalid json {",  # Invalid JSON
            "tags": '["valid", "json"]'
        }
        
        # Should not raise an exception but log a warning
        processed = json_repo._postprocess_data(test_data)
        
        # Invalid JSON should be kept as-is
        assert processed["metadata"] == "invalid json {"
        
        # Valid JSON should be processed
        assert processed["tags"] == ["valid", "json"]
    
    def test_postprocess_data_non_string_values(self, json_repo):
        """Test postprocessing with non-string values in JSON fields."""
        test_data = {
            "name": "test_item",
            "value": 42,
            "metadata": 123,  # Not a string
            "tags": '["tag1", "tag2"]'
        }
        
        # Should handle gracefully
        processed = json_repo._postprocess_data(test_data)
        
        # Non-string value should be kept as-is
        assert processed["metadata"] == 123
        
        # Valid JSON string should be processed
        assert processed["tags"] == ["tag1", "tag2"]
    
    def test_roundtrip_processing(self, json_repo):
        """Test that preprocessing and postprocessing are reversible."""
        original_data = {
            "name": "test_item",
            "value": 42,
            "metadata": {"key": "value", "nested": {"deep": "data"}},
            "tags": ["tag1", "tag2", "tag3"],
            "settings": {"theme": "dark", "lang": "en"}
        }
        
        # Preprocess then postprocess
        preprocessed = json_repo._preprocess_data(original_data)
        postprocessed = json_repo._postprocess_data(preprocessed)
        
        # Should get back the original data
        assert postprocessed["name"] == original_data["name"]
        assert postprocessed["value"] == original_data["value"]
        assert postprocessed["metadata"] == original_data["metadata"]
        assert postprocessed["tags"] == original_data["tags"]
        assert postprocessed["settings"] == original_data["settings"]
    
    def test_data_immutability(self, json_repo):
        """Test that preprocessing and postprocessing don't modify original data."""
        original_data = {
            "name": "test_item",
            "value": 42,
            "metadata": {"key": "value"},
            "tags": ["tag1", "tag2"]
        }
        
        original_copy = original_data.copy()
        
        # Preprocessing should not modify original data
        preprocessed = json_repo._preprocess_data(original_data)
        assert original_data == original_copy
        
        # Postprocessing should not modify input data
        postprocessed = json_repo._postprocess_data(preprocessed)
        assert preprocessed["metadata"] != postprocessed["metadata"]  # Should be different
        
        # But original should still be unchanged
        assert original_data == original_copy
    
    @patch('psycopg_toolkit.repositories.base.logger')
    def test_preprocessing_logging(self, mock_logger, json_repo):
        """Test that preprocessing logs appropriately."""
        test_data = {
            "name": "test_item",
            "metadata": {"key": "value"},
            "tags": ["tag1"]
        }
        
        json_repo._preprocess_data(test_data)
        
        # Should log debug messages for each field processed
        mock_logger.debug.assert_called()
        debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
        
        assert any("Serialized JSON field 'metadata'" in call for call in debug_calls)
        assert any("Serialized JSON field 'tags'" in call for call in debug_calls)
        assert any("Preprocessed 3 JSON fields" in call for call in debug_calls)
    
    @patch('psycopg_toolkit.repositories.base.logger')
    def test_postprocessing_logging(self, mock_logger, json_repo):
        """Test that postprocessing logs appropriately."""
        test_data = {
            "name": "test_item",
            "metadata": '{"key": "value"}',
            "tags": '["tag1"]'
        }
        
        json_repo._postprocess_data(test_data)
        
        # Should log debug messages for each field processed
        mock_logger.debug.assert_called()
        debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
        
        assert any("Deserialized JSON field 'metadata'" in call for call in debug_calls)
        assert any("Deserialized JSON field 'tags'" in call for call in debug_calls)
        assert any("Postprocessed 3 JSON fields" in call for call in debug_calls)
    
    @patch('psycopg_toolkit.repositories.base.logger')
    def test_postprocessing_error_logging(self, mock_logger, json_repo):
        """Test that postprocessing logs warnings for errors."""
        test_data = {
            "name": "test_item",
            "metadata": "invalid json {",
            "tags": '["valid"]'
        }
        
        json_repo._postprocess_data(test_data)
        
        # Should log warning for failed deserialization
        mock_logger.warning.assert_called()
        warning_calls = [call[0][0] for call in mock_logger.warning.call_args_list]
        
        assert any("Failed to deserialize JSON field 'metadata'" in call for call in warning_calls)
        assert any("Keeping original value for field 'metadata'" in call for call in warning_calls)