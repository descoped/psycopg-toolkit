"""Unit tests for BaseRepository JSON field detection."""

import pytest
from unittest.mock import AsyncMock
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field
from uuid import UUID, uuid4

from psycopg_toolkit.repositories.base import BaseRepository


class SampleModel(BaseModel):
    """Sample model with mixed field types."""
    id: UUID = Field(default_factory=uuid4)
    name: str
    value: int
    
    # JSON fields that should be auto-detected
    metadata: Dict[str, Any]
    tags: List[str]
    settings: Optional[Dict[str, str]] = None


class SimpleModel(BaseModel):
    """Simple model without JSON fields."""
    id: UUID = Field(default_factory=uuid4)
    name: str
    active: bool


class TestBaseRepositoryJSONDetection:
    """Test BaseRepository JSON field detection functionality."""
    
    @pytest.fixture
    def mock_connection(self):
        """Create a mock database connection."""
        return AsyncMock()
    
    def test_auto_detect_json_fields(self, mock_connection):
        """Test automatic JSON field detection."""
        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=SampleModel,
            primary_key="id"
        )
        
        expected_json_fields = {"metadata", "tags", "settings"}
        assert repo.json_fields == expected_json_fields
    
    def test_explicit_json_fields(self, mock_connection):
        """Test explicit JSON field specification overrides auto-detection."""
        explicit_fields = {"metadata", "custom_field"}
        
        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=SampleModel,
            primary_key="id",
            json_fields=explicit_fields
        )
        
        assert repo.json_fields == explicit_fields
    
    def test_disable_auto_detection(self, mock_connection):
        """Test disabling auto-detection results in no JSON fields."""
        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=SampleModel,
            primary_key="id",
            auto_detect_json=False
        )
        
        assert repo.json_fields == set()
    
    def test_explicit_fields_override_auto_detect_false(self, mock_connection):
        """Test explicit fields work even when auto_detect_json=False."""
        explicit_fields = {"metadata"}
        
        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=SampleModel,
            primary_key="id",
            json_fields=explicit_fields,
            auto_detect_json=False
        )
        
        assert repo.json_fields == explicit_fields
    
    def test_simple_model_no_json_fields(self, mock_connection):
        """Test model without JSON fields returns empty set."""
        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="simple_table",
            model_class=SimpleModel,
            primary_key="id"
        )
        
        assert repo.json_fields == set()
    
    def test_empty_explicit_json_fields(self, mock_connection):
        """Test explicitly providing empty set of JSON fields."""
        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=SampleModel,
            primary_key="id",
            json_fields=set()
        )
        
        assert repo.json_fields == set()
    
    def test_json_fields_property_returns_copy(self, mock_connection):
        """Test that json_fields property returns a copy, not the original set."""
        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=SampleModel,
            primary_key="id"
        )
        
        json_fields_copy1 = repo.json_fields
        json_fields_copy2 = repo.json_fields
        
        # Should be equal but not the same object
        assert json_fields_copy1 == json_fields_copy2
        assert json_fields_copy1 is not json_fields_copy2
        
        # Modifying the copy should not affect the original
        json_fields_copy1.add("new_field")
        assert "new_field" not in repo.json_fields
    
    def test_repository_attributes(self, mock_connection):
        """Test that all repository attributes are properly set."""
        json_fields = {"metadata", "tags"}
        
        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=SampleModel,
            primary_key="custom_id",
            json_fields=json_fields,
            auto_detect_json=False
        )
        
        assert repo.db_connection == mock_connection
        assert repo.table_name == "test_table"
        assert repo.model_class == SampleModel
        assert repo.primary_key == "custom_id"
        assert repo.json_fields == json_fields
        assert repo._auto_detect_json is False
    
    def test_default_parameters(self, mock_connection):
        """Test repository with default parameters."""
        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=SampleModel
        )
        
        # Should use defaults
        assert repo.primary_key == "id"
        assert repo._auto_detect_json is True
        assert repo.json_fields == {"metadata", "tags", "settings"}
    
    def test_complex_model_json_detection(self, mock_connection):
        """Test JSON detection with complex model from test suite."""
        # Import here to avoid circular imports
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        
        from models.jsonb_models import UserProfile
        
        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="user_profiles",
            model_class=UserProfile,
            primary_key="id"
        )
        
        expected_fields = {
            "metadata", "preferences", "tags",
            "settings", "custom_fields", "profile_data"
        }
        assert repo.json_fields == expected_fields