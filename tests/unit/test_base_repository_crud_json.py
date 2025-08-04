"""Unit tests for BaseRepository CRUD operations with JSON support."""

import pytest
from contextlib import AbstractAsyncContextManager
from unittest.mock import AsyncMock, patch
from typing import Dict, List, Optional, Any
from uuid import UUID, uuid4
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field
from psycopg import Cursor

from psycopg_toolkit.repositories.base import BaseRepository
from psycopg_toolkit.exceptions import OperationError


class AsyncCursorContextManager:
    """Helper class to make cursor work as async context manager"""

    def __init__(self, cursor):
        self.cursor = cursor

    async def __aenter__(self):
        return self.cursor

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class MockCursor(AsyncMock):
    """Mock cursor with proper async support for all methods"""

    def __init__(self, *args, **kwargs):
        super().__init__(spec=Cursor)
        # Make execute return a coroutine that returns self
        self.execute = AsyncMock(return_value=self)
        self.fetchone = AsyncMock(return_value=None)
        self.fetchall = AsyncMock(return_value=[])
        self.rowcount = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class MockTransaction(AbstractAsyncContextManager):
    """Mock for psycopg Transaction that properly implements async context manager"""

    def __init__(self):
        self.__aenter__ = AsyncMock(return_value=self)
        self.__aexit__ = AsyncMock(return_value=None)

    async def __aenter__(self):
        return await self.__aenter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self.__aexit__(exc_type, exc_val, exc_tb)


class MockConnection(AsyncMock):
    """Mock for psycopg Connection with proper transaction and cursor support"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._cursor = MockCursor()
        self._transaction = MockTransaction()

        # Override the cursor method to return a context manager instead of coroutine
        self.cursor = self._cursor_factory
        
        # Override the transaction method to return a context manager
        self.transaction = self._transaction_factory

    def _cursor_factory(self, *args, **kwargs):
        """Returns async cursor context manager directly"""
        return AsyncCursorContextManager(self._cursor)
    
    def _transaction_factory(self, *args, **kwargs):
        """Returns async transaction context manager directly"""
        return self._transaction


class JSONTestModel(BaseModel):
    """Test model with JSON fields for CRUD testing."""
    id: UUID = Field(default_factory=uuid4)
    name: str
    value: int
    
    # JSON fields
    metadata: Dict[str, Any]
    tags: List[str]
    settings: Optional[Dict[str, str]] = None


class NonJSONModel(BaseModel):
    """Sample model without JSON fields."""
    id: UUID = Field(default_factory=uuid4)
    name: str
    active: bool


class TestBaseRepositoryCRUDWithJSON:
    """Test BaseRepository CRUD operations with JSON field support."""
    
    @pytest.fixture
    def mock_connection(self):
        """Create a mock database connection."""
        return MockConnection()
    
    @pytest.fixture
    def json_repo(self, mock_connection):
        """Create a repository with JSON fields."""
        return BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=JSONTestModel,
            primary_key="id"
        )
    
    @pytest.fixture
    def sample_model(self):
        """Create a sample model instance with JSON data."""
        return JSONTestModel(
            name="test_item",
            value=42,
            metadata={"key": "value", "number": 123},
            tags=["tag1", "tag2"],
            settings={"theme": "dark"}
        )
    
    async def test_create_with_json_fields(self, json_repo, sample_model):
        """Test create method with JSON field preprocessing and postprocessing."""
        # Mock the database result with serialized JSON
        db_result = {
            "id": sample_model.id,
            "name": "test_item",
            "value": 42,
            "metadata": '{"key": "value", "number": 123}',  # Serialized JSON
            "tags": '["tag1", "tag2"]',                     # Serialized JSON
            "settings": '{"theme": "dark"}'                 # Serialized JSON
        }
        
        json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        # Call create method
        result = await json_repo.create(sample_model)
        
        # Verify the result
        assert result.name == sample_model.name
        assert result.value == sample_model.value
        assert result.metadata == sample_model.metadata  # Should be deserialized
        assert result.tags == sample_model.tags          # Should be deserialized
        assert result.settings == sample_model.settings  # Should be deserialized
        
        # Verify cursor was called with processed data
        json_repo.db_connection._cursor.execute.assert_called_once()
        execute_args = json_repo.db_connection._cursor.execute.call_args[0]
        execute_values = execute_args[1]
        
        # The values passed to execute should have JSON fields serialized
        assert '"key": "value"' in str(execute_values) or '{"key": "value"}' in str(execute_values)
    
    async def test_create_with_none_json_fields(self, json_repo):
        """Test create method with None values in JSON fields."""
        model = JSONTestModel(
            name="test_item",
            value=42,
            metadata={"key": "value"},
            tags=["tag1"],
            settings=None  # None value
        )
        
        # Mock database result
        db_result = {
            "id": model.id,
            "name": "test_item", 
            "value": 42,
            "metadata": '{"key": "value"}',
            "tags": '["tag1"]',
            "settings": None  # None remains None
        }
        
        json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        result = await json_repo.create(model)
        
        assert result.settings is None
        assert result.metadata == {"key": "value"}
        assert result.tags == ["tag1"]
    
    async def test_create_with_complex_json_data(self, json_repo):
        """Test create method with complex JSON data types."""
        test_uuid = uuid4()
        test_datetime = datetime.now()
        test_decimal = Decimal("123.45")
        
        model = JSONTestModel(
            name="complex_test",
            value=42,
            metadata={
                "uuid": test_uuid,
                "timestamp": test_datetime,
                "amount": test_decimal,
                "nested": {"deep": {"value": "test"}}
            },
            tags=["tag1", "tag2"]
        )
        
        # Mock database result with serialized complex types
        db_result = {
            "id": model.id,
            "name": "complex_test",
            "value": 42,
            "metadata": f'{{"uuid": "{test_uuid}", "timestamp": "{test_datetime.isoformat()}", "amount": {float(test_decimal)}, "nested": {{"deep": {{"value": "test"}}}}}}',
            "tags": '["tag1", "tag2"]',
            "settings": None
        }
        
        json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        result = await json_repo.create(model)
        
        # Complex types should be properly deserialized
        assert result.metadata["uuid"] == str(test_uuid)
        assert result.metadata["timestamp"] == test_datetime.isoformat()
        assert result.metadata["amount"] == float(test_decimal)
        assert result.metadata["nested"]["deep"]["value"] == "test"
    
    async def test_create_json_serialization_error(self, json_repo):
        """Test create method when JSON serialization fails."""
        from psycopg_toolkit.exceptions import JSONSerializationError
        
        # Create a model with non-serializable data
        class NonSerializable:
            pass
        
        model = JSONTestModel(
            name="test_item",
            value=42,
            metadata={"bad_data": NonSerializable()},  # This will fail serialization
            tags=["tag1"]
        )
        
        with pytest.raises(JSONSerializationError, match="JSON serialization failed"):
            await json_repo.create(model)
    
    async def test_create_database_error(self, json_repo, sample_model):
        """Test create method when database operation fails."""
        # Mock database error
        json_repo.db_connection._cursor.execute.side_effect = Exception("Database connection failed")
        
        with pytest.raises(OperationError, match="Failed to create record"):
            await json_repo.create(sample_model)
    
    async def test_create_no_result_error(self, json_repo, sample_model):
        """Test create method when database doesn't return a result."""
        # Mock no result from database
        json_repo.db_connection._cursor.fetchone.return_value = None
        
        with pytest.raises(OperationError, match="Failed to create test_table record"):
            await json_repo.create(sample_model)
    
    async def test_create_without_json_fields(self, mock_connection):
        """Test create method with a model that has no JSON fields."""
        
        non_json_repo = BaseRepository(
            db_connection=mock_connection,
            table_name="simple_table",
            model_class=NonJSONModel,
            primary_key="id"
        )
        
        model = NonJSONModel(name="test", active=True)
        
        db_result = {
            "id": model.id,
            "name": "test",
            "active": True
        }
        
        non_json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        result = await non_json_repo.create(model)
        
        assert result.name == "test"
        assert result.active is True
        assert result.id == model.id
    
    async def test_create_preserves_original_model(self, json_repo, sample_model):
        """Test that create method doesn't modify the original model."""
        # Store original values
        original_metadata = sample_model.metadata.copy()
        original_tags = sample_model.tags.copy()
        
        # Mock database result
        db_result = {
            "id": sample_model.id,
            "name": sample_model.name,
            "value": sample_model.value,
            "metadata": '{"key": "value", "number": 123}',
            "tags": '["tag1", "tag2"]',
            "settings": '{"theme": "dark"}'
        }
        
        json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        await json_repo.create(sample_model)
        
        # Original model should be unchanged
        assert sample_model.metadata == original_metadata
        assert sample_model.tags == original_tags
    
    async def test_create_with_explicit_json_fields_config(self, mock_connection):
        """Test create with explicit JSON fields configuration."""
        # For this test, let's use a simpler model to demonstrate the concept clearly
        class MixedFieldModel(BaseModel):
            id: UUID = Field(default_factory=uuid4)
            name: str
            # This will be explicitly marked as JSON
            config: Dict[str, Any]
            # This won't be marked as JSON even though it could be
            simple_list: List[str]
            
        sample = MixedFieldModel(
            name="test",
            config={"key": "value", "number": 123},
            simple_list=["item1", "item2"]
        )
        
        # Create repo with explicit JSON fields
        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=MixedFieldModel,
            primary_key="id",
            json_fields={"config"},  # Only config should be processed as JSON
            auto_detect_json=False
        )
        
        # In the database, if we're using text columns for JSON with custom processing:
        # - config would be stored as serialized JSON text
        # - simple_list might be stored as PostgreSQL array or serialized text
        # For this test, let's assume simple_list is stored as a PostgreSQL array
        db_result = {
            "id": sample.id,
            "name": sample.name,
            "config": '{"key": "value", "number": 123}',  # Serialized JSON (will be deserialized)
            "simple_list": ["item1", "item2"]             # PostgreSQL array (not processed)
        }
        
        repo.db_connection._cursor.fetchone.return_value = db_result
        
        result = await repo.create(sample)
        
        # Only config should be deserialized
        assert result.config == {"key": "value", "number": 123}  # Deserialized
        assert result.simple_list == ["item1", "item2"]          # Unchanged
    
    @patch('psycopg_toolkit.repositories.base.logger')
    async def test_create_logging_behavior(self, mock_logger, json_repo, sample_model):
        """Test that create method logs appropriately."""
        db_result = {
            "id": sample_model.id,
            "name": sample_model.name,
            "value": sample_model.value,
            "metadata": '{"key": "value", "number": 123}',
            "tags": '["tag1", "tag2"]',
            "settings": '{"theme": "dark"}'
        }
        
        json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        await json_repo.create(sample_model)
        
        # Should log preprocessing and postprocessing
        debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
        
        # Should have preprocessing logs
        assert any("Serialized JSON field" in call for call in debug_calls)
        assert any("Preprocessed 3 JSON fields" in call for call in debug_calls)
        
        # Should have postprocessing logs  
        assert any("Deserialized JSON field" in call for call in debug_calls)
        assert any("Postprocessed 3 JSON fields" in call for call in debug_calls)
    
    # Tests for create_bulk() method
    
    async def test_create_bulk_with_json_fields(self, json_repo):
        """Test create_bulk method with JSON field preprocessing and postprocessing."""
        models = [
            JSONTestModel(
                name=f"test_item_{i}",
                value=i * 10,
                metadata={"key": f"value_{i}", "number": i},
                tags=[f"tag_{i}_1", f"tag_{i}_2"],
                settings={"theme": "dark" if i % 2 == 0 else "light"}
            )
            for i in range(3)
        ]
        
        # Mock database results for each batch (batch_size=2 means 2 batches: [0,1] and [2])
        batch_1_results = [
            {
                "id": models[0].id,
                "name": models[0].name,
                "value": models[0].value,
                "metadata": '{"key": "value_0", "number": 0}',
                "tags": '["tag_0_1", "tag_0_2"]',
                "settings": '{"theme": "dark"}'
            },
            {
                "id": models[1].id,
                "name": models[1].name,
                "value": models[1].value,
                "metadata": '{"key": "value_1", "number": 1}',
                "tags": '["tag_1_1", "tag_1_2"]',
                "settings": '{"theme": "light"}'
            }
        ]
        
        batch_2_results = [
            {
                "id": models[2].id,
                "name": models[2].name,
                "value": models[2].value,
                "metadata": '{"key": "value_2", "number": 2}',
                "tags": '["tag_2_1", "tag_2_2"]',
                "settings": '{"theme": "dark"}'
            }
        ]
        
        # Mock fetchall to return different results for each call
        json_repo.db_connection._cursor.fetchall.side_effect = [batch_1_results, batch_2_results]
        
        # Call create_bulk method
        results = await json_repo.create_bulk(models, batch_size=2)
        
        # Verify the results
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.name == models[i].name
            assert result.value == models[i].value
            assert result.metadata == models[i].metadata  # Should be deserialized
            assert result.tags == models[i].tags          # Should be deserialized
            assert result.settings == models[i].settings  # Should be deserialized
    
    async def test_create_bulk_with_different_batch_sizes(self, json_repo):
        """Test create_bulk with different batch sizes."""
        models = [
            JSONTestModel(
                name=f"test_item_{i}",
                value=i,
                metadata={"index": i},
                tags=[f"tag_{i}"]
            )
            for i in range(5)
        ]
        
        # Mock database results
        db_results = [
            {
                "id": model.id,
                "name": model.name,
                "value": model.value,
                "metadata": f'{{"index": {i}}}',
                "tags": f'["tag_{i}"]',
                "settings": None
            }
            for i, model in enumerate(models)
        ]
        
        # Since we have 5 items with batch_size=2, we'll have 3 batches: [0,1], [2,3], [4]
        json_repo.db_connection._cursor.fetchall.side_effect = [
            db_results[0:2],  # First batch
            db_results[2:4],  # Second batch  
            db_results[4:5]   # Third batch
        ]
        
        # Test with batch_size=2 (should create 3 batches: 2+2+1)
        results = await json_repo.create_bulk(models, batch_size=2)
        
        assert len(results) == 5
        for i, result in enumerate(results):
            assert result.metadata == {"index": i}
            assert result.tags == [f"tag_{i}"]
    
    async def test_create_bulk_empty_list(self, json_repo):
        """Test create_bulk with empty list."""
        results = await json_repo.create_bulk([])
        assert results == []
    
    async def test_create_bulk_json_serialization_error(self, json_repo):
        """Test create_bulk when JSON serialization fails."""
        class NonSerializable:
            pass
        
        models = [
            JSONTestModel(
                name="test_item_1",
                value=42,
                metadata={"good_data": "value"},
                tags=["tag1"]
            ),
            JSONTestModel(
                name="test_item_2",
                value=43,
                metadata={"bad_data": NonSerializable()},  # This will fail serialization
                tags=["tag2"]
            )
        ]
        
        with pytest.raises(OperationError, match="Failed to create records in bulk"):
            await json_repo.create_bulk(models)
    
    async def test_create_bulk_database_transaction_error(self, json_repo):
        """Test create_bulk when database transaction fails."""
        models = [
            JSONTestModel(
                name="test_item",
                value=42,
                metadata={"key": "value"},
                tags=["tag1"]
            )
        ]
        
        # Mock transaction error
        json_repo.db_connection._transaction.__aenter__.side_effect = Exception("Transaction failed")
        
        with pytest.raises(OperationError, match="Failed to create records in bulk"):
            await json_repo.create_bulk(models)
    
    async def test_create_bulk_without_json_fields(self, mock_connection):
        """Test create_bulk with a model that has no JSON fields."""
        non_json_repo = BaseRepository(
            db_connection=mock_connection,
            table_name="simple_table",
            model_class=NonJSONModel,
            primary_key="id"
        )
        
        models = [
            NonJSONModel(name=f"test_{i}", active=i % 2 == 0)
            for i in range(3)
        ]
        
        db_results = [
            {
                "id": model.id,
                "name": model.name,
                "active": model.active
            }
            for model in models
        ]
        
        # Single batch since we have 3 items with default batch size
        non_json_repo.db_connection._cursor.fetchall.return_value = db_results
        
        results = await non_json_repo.create_bulk(models)
        
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.name == models[i].name
            assert result.active == models[i].active
    
    async def test_create_bulk_preserves_original_models(self, json_repo):
        """Test that create_bulk doesn't modify the original models."""
        models = [
            JSONTestModel(
                name="test_item",
                value=42,
                metadata={"key": "value"},
                tags=["tag1", "tag2"]
            )
        ]
        
        # Store original values
        original_metadata = models[0].metadata.copy()
        original_tags = models[0].tags.copy()
        
        # Mock database result
        db_results = [{
            "id": models[0].id,
            "name": "test_item",
            "value": 42,
            "metadata": '{"key": "value"}',
            "tags": '["tag1", "tag2"]',
            "settings": None
        }]
        
        # Single batch since we have 1 item
        json_repo.db_connection._cursor.fetchall.return_value = db_results
        
        await json_repo.create_bulk(models)
        
        # Original models should be unchanged
        assert models[0].metadata == original_metadata
        assert models[0].tags == original_tags
    
    @patch('psycopg_toolkit.repositories.base.logger')
    async def test_create_bulk_logging_behavior(self, mock_logger, json_repo):
        """Test that create_bulk logs preprocessing and postprocessing appropriately."""
        models = [
            JSONTestModel(
                name="test_item",
                value=42,
                metadata={"key": "value"},
                tags=["tag1"]
            )
        ]
        
        db_results = [{
            "id": models[0].id,
            "name": "test_item",
            "value": 42,
            "metadata": '{"key": "value"}',
            "tags": '["tag1"]',
            "settings": None
        }]
        
        # Single batch since we have 1 item
        json_repo.db_connection._cursor.fetchall.return_value = db_results
        
        await json_repo.create_bulk(models)
        
        # Should log preprocessing and postprocessing for each item
        debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
        
        # Should have preprocessing logs
        assert any("Serialized JSON field" in call for call in debug_calls)
        assert any("Preprocessed 3 JSON fields" in call for call in debug_calls)
        
        # Should have postprocessing logs
        assert any("Deserialized JSON field" in call for call in debug_calls)
        assert any("Postprocessed 3 JSON fields" in call for call in debug_calls)
    
    # Tests for get_by_id() method
    
    async def test_get_by_id_with_json_fields(self, json_repo, sample_model):
        """Test get_by_id method with JSON field postprocessing."""
        # Mock database result with serialized JSON
        db_result = {
            "id": sample_model.id,
            "name": "test_item",
            "value": 42,
            "metadata": '{"key": "value", "number": 123}',  # Serialized JSON
            "tags": '["tag1", "tag2"]',                     # Serialized JSON
            "settings": '{"theme": "dark"}'                 # Serialized JSON
        }
        
        json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        # Call get_by_id method
        result = await json_repo.get_by_id(sample_model.id)
        
        # Verify the result
        assert result is not None
        assert result.name == "test_item"
        assert result.value == 42
        assert result.metadata == {"key": "value", "number": 123}  # Should be deserialized
        assert result.tags == ["tag1", "tag2"]                     # Should be deserialized
        assert result.settings == {"theme": "dark"}                # Should be deserialized
    
    async def test_get_by_id_with_none_json_fields(self, json_repo, sample_model):
        """Test get_by_id method with None values in JSON fields."""
        db_result = {
            "id": sample_model.id,
            "name": "test_item",
            "value": 42,
            "metadata": '{"key": "value"}',
            "tags": '["tag1"]',
            "settings": None  # None value should remain None
        }
        
        json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        result = await json_repo.get_by_id(sample_model.id)
        
        assert result is not None
        assert result.settings is None
        assert result.metadata == {"key": "value"}
        assert result.tags == ["tag1"]
    
    async def test_get_by_id_not_found(self, json_repo):
        """Test get_by_id method when record is not found."""
        from psycopg_toolkit.exceptions import RecordNotFoundError
        from uuid import uuid4
        
        # Mock no result from database
        json_repo.db_connection._cursor.fetchone.return_value = None
        
        with pytest.raises(RecordNotFoundError):
            await json_repo.get_by_id(uuid4())
    
    async def test_get_by_id_database_error(self, json_repo):
        """Test get_by_id method when database operation fails."""
        from uuid import uuid4
        
        # Mock database error
        json_repo.db_connection._cursor.execute.side_effect = Exception("Database connection failed")
        
        with pytest.raises(OperationError, match="Failed to get record"):
            await json_repo.get_by_id(uuid4())
    
    async def test_get_by_id_with_complex_json_data(self, json_repo):
        """Test get_by_id method with complex JSON data types."""
        from uuid import uuid4
        from datetime import datetime
        from decimal import Decimal
        
        test_uuid = uuid4()
        test_datetime = datetime.now()
        test_decimal = Decimal("123.45")
        
        db_result = {
            "id": test_uuid,
            "name": "complex_test",
            "value": 42,
            "metadata": f'{{"uuid": "{test_uuid}", "timestamp": "{test_datetime.isoformat()}", "amount": {float(test_decimal)}, "nested": {{"deep": {{"value": "test"}}}}}}',
            "tags": '["tag1", "tag2"]',
            "settings": None
        }
        
        json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        result = await json_repo.get_by_id(test_uuid)
        
        # Complex types should be properly deserialized
        assert result is not None
        assert result.metadata["uuid"] == str(test_uuid)
        assert result.metadata["timestamp"] == test_datetime.isoformat()
        assert result.metadata["amount"] == float(test_decimal)
        assert result.metadata["nested"]["deep"]["value"] == "test"
    
    async def test_get_by_id_without_json_fields(self, mock_connection):
        """Test get_by_id method with a model that has no JSON fields."""
        from uuid import uuid4
        
        non_json_repo = BaseRepository(
            db_connection=mock_connection,
            table_name="simple_table",
            model_class=NonJSONModel,
            primary_key="id"
        )
        
        test_id = uuid4()
        db_result = {
            "id": test_id,
            "name": "test",
            "active": True
        }
        
        non_json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        result = await non_json_repo.get_by_id(test_id)
        
        assert result is not None
        assert result.name == "test"
        assert result.active is True
        assert result.id == test_id
    
    async def test_get_by_id_with_invalid_json_data(self, json_repo):
        """Test get_by_id method with invalid JSON data (should raise validation error)."""
        from uuid import uuid4
        
        test_id = uuid4()
        db_result = {
            "id": test_id,
            "name": "test_item",
            "value": 42,
            "metadata": "invalid json {",  # Invalid JSON will cause Pydantic validation error
            "tags": '["tag1", "tag2"]',   # Valid JSON should be processed
            "settings": None
        }
        
        json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        # Should raise OperationError due to Pydantic validation failure
        with pytest.raises(OperationError, match="Failed to get record"):
            await json_repo.get_by_id(test_id)
    
    async def test_get_by_id_with_explicit_json_fields_config(self, mock_connection, sample_model):
        """Test get_by_id with explicit JSON fields configuration."""
        # Create repo with explicit JSON fields (subset of actual JSON fields)
        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=JSONTestModel,
            primary_key="id",
            json_fields={"metadata"},  # Only metadata should be processed as JSON
            auto_detect_json=False
        )
        
        db_result = {
            "id": sample_model.id,
            "name": sample_model.name,
            "value": sample_model.value,
            "metadata": '{"key": "value", "number": 123}',  # Should be deserialized
            "tags": ["tag1", "tag2"],                        # Should remain as-is
            "settings": {"theme": "dark"}                    # Should remain as-is
        }
        
        repo.db_connection._cursor.fetchone.return_value = db_result
        
        result = await repo.get_by_id(sample_model.id)
        
        # Only metadata should be deserialized, others should remain as-is
        assert result.metadata == {"key": "value", "number": 123}  # Deserialized
        assert result.tags == ["tag1", "tag2"]                     # Unchanged
        assert result.settings == {"theme": "dark"}                # Unchanged
    
    @patch('psycopg_toolkit.repositories.base.logger')
    async def test_get_by_id_logging_behavior(self, mock_logger, json_repo, sample_model):
        """Test that get_by_id method logs postprocessing appropriately."""
        db_result = {
            "id": sample_model.id,
            "name": sample_model.name,
            "value": sample_model.value,
            "metadata": '{"key": "value", "number": 123}',
            "tags": '["tag1", "tag2"]',
            "settings": '{"theme": "dark"}'
        }
        
        json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        await json_repo.get_by_id(sample_model.id)
        
        # Should log postprocessing
        debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
        
        # Should have postprocessing logs
        assert any("Deserialized JSON field" in call for call in debug_calls)
        assert any("Postprocessed 3 JSON fields" in call for call in debug_calls)
    
    # Tests for get_all() method
    
    async def test_get_all_with_json_fields(self, json_repo):
        """Test get_all method with JSON field postprocessing."""
        # Mock database results with serialized JSON for multiple records
        db_results = [
            {
                "id": uuid4(),
                "name": "test_item_1",
                "value": 10,
                "metadata": '{"key": "value_1", "number": 1}',
                "tags": '["tag1_1", "tag1_2"]',
                "settings": '{"theme": "dark"}'
            },
            {
                "id": uuid4(),
                "name": "test_item_2", 
                "value": 20,
                "metadata": '{"key": "value_2", "number": 2}',
                "tags": '["tag2_1", "tag2_2"]',
                "settings": '{"theme": "light"}'
            },
            {
                "id": uuid4(),
                "name": "test_item_3",
                "value": 30,
                "metadata": '{"key": "value_3", "number": 3}',
                "tags": '["tag3_1", "tag3_2"]',
                "settings": None
            }
        ]
        
        json_repo.db_connection._cursor.fetchall.return_value = db_results
        
        # Call get_all method
        results = await json_repo.get_all()
        
        # Verify the results
        assert len(results) == 3
        
        for i, result in enumerate(results, 1):
            assert result.name == f"test_item_{i}"
            assert result.value == i * 10
            assert result.metadata == {"key": f"value_{i}", "number": i}  # Should be deserialized
            assert result.tags == [f"tag{i}_1", f"tag{i}_2"]              # Should be deserialized
            if i < 3:
                expected_theme = "dark" if i == 1 else "light"
                assert result.settings == {"theme": expected_theme}        # Should be deserialized
            else:
                assert result.settings is None
    
    async def test_get_all_empty_table(self, json_repo):
        """Test get_all method with empty table."""
        json_repo.db_connection._cursor.fetchall.return_value = []
        
        results = await json_repo.get_all()
        
        assert results == []
    
    async def test_get_all_database_error(self, json_repo):
        """Test get_all method when database operation fails."""
        # Mock database error
        json_repo.db_connection._cursor.execute.side_effect = Exception("Database connection failed")
        
        with pytest.raises(OperationError, match="Failed to get all records"):
            await json_repo.get_all()
    
    async def test_get_all_with_mixed_valid_invalid_json(self, json_repo):
        """Test get_all method with mix of valid and invalid JSON data."""
        db_results = [
            {
                "id": uuid4(),
                "name": "test_item_1",
                "value": 10,
                "metadata": '{"key": "value_1"}',  # Valid JSON
                "tags": '["tag1"]',               # Valid JSON
                "settings": None
            },
            {
                "id": uuid4(),
                "name": "test_item_2",
                "value": 20,
                "metadata": "invalid json {",     # Invalid JSON
                "tags": '["tag2"]',               # Valid JSON
                "settings": None
            }
        ]
        
        json_repo.db_connection._cursor.fetchall.return_value = db_results
        
        # Should raise OperationError due to Pydantic validation failure on invalid JSON
        with pytest.raises(OperationError, match="Failed to get all records"):
            await json_repo.get_all()
    
    async def test_get_all_without_json_fields(self, mock_connection):
        """Test get_all method with a model that has no JSON fields."""
        non_json_repo = BaseRepository(
            db_connection=mock_connection,
            table_name="simple_table",
            model_class=NonJSONModel,
            primary_key="id"
        )
        
        db_results = [
            {"id": uuid4(), "name": "test_1", "active": True},
            {"id": uuid4(), "name": "test_2", "active": False},
            {"id": uuid4(), "name": "test_3", "active": True}
        ]
        
        non_json_repo.db_connection._cursor.fetchall.return_value = db_results
        
        results = await non_json_repo.get_all()
        
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result.name == db_results[i]["name"]
            assert result.active == db_results[i]["active"]
            assert result.id == db_results[i]["id"]
    
    async def test_get_all_with_complex_json_data(self, json_repo):
        """Test get_all method with complex JSON data types."""
        test_uuid = uuid4()
        test_datetime = datetime.now()
        test_decimal = Decimal("123.45")
        
        db_results = [
            {
                "id": uuid4(),
                "name": "complex_test",
                "value": 42,
                "metadata": f'{{"uuid": "{test_uuid}", "timestamp": "{test_datetime.isoformat()}", "amount": {float(test_decimal)}, "nested": {{"deep": {{"value": "test"}}}}}}',
                "tags": '["tag1", "tag2"]',
                "settings": None
            }
        ]
        
        json_repo.db_connection._cursor.fetchall.return_value = db_results
        
        results = await json_repo.get_all()
        
        assert len(results) == 1
        result = results[0]
        
        # Complex types should be properly deserialized
        assert result.metadata["uuid"] == str(test_uuid)
        assert result.metadata["timestamp"] == test_datetime.isoformat()
        assert result.metadata["amount"] == float(test_decimal)
        assert result.metadata["nested"]["deep"]["value"] == "test"
    
    async def test_get_all_with_explicit_json_fields_config(self, mock_connection):
        """Test get_all with explicit JSON fields configuration."""
        # Create repo with explicit JSON fields (subset of actual JSON fields)
        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=JSONTestModel,
            primary_key="id",
            json_fields={"metadata"},  # Only metadata should be processed as JSON
            auto_detect_json=False
        )
        
        db_results = [
            {
                "id": uuid4(),
                "name": "test_item",
                "value": 42,
                "metadata": '{"key": "value", "number": 123}',  # Should be deserialized
                "tags": ["tag1", "tag2"],                        # Should remain as-is
                "settings": {"theme": "dark"}                    # Should remain as-is
            }
        ]
        
        repo.db_connection._cursor.fetchall.return_value = db_results
        
        results = await repo.get_all()
        
        assert len(results) == 1
        result = results[0]
        
        # Only metadata should be deserialized, others should remain as-is
        assert result.metadata == {"key": "value", "number": 123}  # Deserialized
        assert result.tags == ["tag1", "tag2"]                     # Unchanged
        assert result.settings == {"theme": "dark"}                # Unchanged
    
    @patch('psycopg_toolkit.repositories.base.logger')
    async def test_get_all_logging_behavior(self, mock_logger, json_repo):
        """Test that get_all method logs postprocessing appropriately."""
        db_results = [
            {
                "id": uuid4(),
                "name": "test_item_1",
                "value": 10,  
                "metadata": '{"key": "value_1"}',
                "tags": '["tag1"]',
                "settings": '{"theme": "dark"}'
            },
            {
                "id": uuid4(),
                "name": "test_item_2", 
                "value": 20,
                "metadata": '{"key": "value_2"}',
                "tags": '["tag2"]',
                "settings": None
            }
        ]
        
        json_repo.db_connection._cursor.fetchall.return_value = db_results
        
        await json_repo.get_all()
        
        # Should log postprocessing for each record
        debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
        
        # Should have postprocessing logs for each record
        assert any("Deserialized JSON field" in call for call in debug_calls)
        assert any("Postprocessed 3 JSON fields" in call for call in debug_calls)
    
    # Tests for update() method
    
    async def test_update_with_json_fields(self, json_repo, sample_model):
        """Test update method with JSON field preprocessing and postprocessing."""
        update_data = {
            "name": "updated_item",
            "metadata": {"key": "updated_value", "new_field": "added"},
            "tags": ["new_tag1", "new_tag2", "new_tag3"],
            "settings": {"theme": "light", "language": "es"}
        }
        
        # Mock database result with serialized JSON
        db_result = {
            "id": sample_model.id,
            "name": "updated_item",
            "value": sample_model.value,  # Unchanged
            "metadata": '{"key": "updated_value", "new_field": "added"}',
            "tags": '["new_tag1", "new_tag2", "new_tag3"]',
            "settings": '{"theme": "light", "language": "es"}'
        }
        
        json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        # Call update method
        result = await json_repo.update(sample_model.id, update_data)
        
        # Verify the result
        assert result.name == "updated_item"
        assert result.value == sample_model.value  # Unchanged
        assert result.metadata == {"key": "updated_value", "new_field": "added"}  # Deserialized
        assert result.tags == ["new_tag1", "new_tag2", "new_tag3"]              # Deserialized
        assert result.settings == {"theme": "light", "language": "es"}          # Deserialized
        
        # Verify cursor was called with processed data
        json_repo.db_connection._cursor.execute.assert_called_once()
        execute_args = json_repo.db_connection._cursor.execute.call_args[0]
        execute_values = execute_args[1]
        
        # The values passed to execute should have JSON fields serialized
        assert '"key": "updated_value"' in str(execute_values) or '{"key": "updated_value"}' in str(execute_values)
    
    async def test_update_partial_json_fields(self, json_repo, sample_model):
        """Test update method with partial JSON field updates."""
        # Only update some fields, including some JSON fields
        update_data = {
            "name": "partially_updated",
            "metadata": {"partial": "update"}
            # Not updating tags or settings
        }
        
        db_result = {
            "id": sample_model.id,
            "name": "partially_updated",
            "value": sample_model.value,
            "metadata": '{"partial": "update"}',
            "tags": '["original", "tags"]',      # From existing record
            "settings": '{"original": "setting"}'  # From existing record
        }
        
        json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        result = await json_repo.update(sample_model.id, update_data)
        
        assert result.name == "partially_updated"
        assert result.metadata == {"partial": "update"}     # Updated
        assert result.tags == ["original", "tags"]          # Not updated
        assert result.settings == {"original": "setting"}   # Not updated
    
    async def test_update_with_none_json_fields(self, json_repo, sample_model):
        """Test update method with None values in JSON fields."""
        update_data = {
            "metadata": {"key": "value"},
            "tags": ["tag1"],
            "settings": None  # Setting to None
        }
        
        db_result = {
            "id": sample_model.id,
            "name": sample_model.name,
            "value": sample_model.value,
            "metadata": '{"key": "value"}',
            "tags": '["tag1"]',
            "settings": None
        }
        
        json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        result = await json_repo.update(sample_model.id, update_data)
        
        assert result.settings is None
        assert result.metadata == {"key": "value"}
        assert result.tags == ["tag1"]
    
    async def test_update_not_found(self, json_repo):
        """Test update method when record is not found."""
        from psycopg_toolkit.exceptions import RecordNotFoundError
        from uuid import uuid4
        
        # Mock no result from database
        json_repo.db_connection._cursor.fetchone.return_value = None
        
        with pytest.raises(RecordNotFoundError):
            await json_repo.update(uuid4(), {"name": "test"})
    
    async def test_update_database_error(self, json_repo):
        """Test update method when database operation fails."""
        from uuid import uuid4
        
        # Mock database error
        json_repo.db_connection._cursor.execute.side_effect = Exception("Database connection failed")
        
        with pytest.raises(OperationError, match="Failed to update record"):
            await json_repo.update(uuid4(), {"name": "test"})
    
    async def test_update_json_serialization_error(self, json_repo, sample_model):
        """Test update method when JSON serialization fails."""
        from psycopg_toolkit.exceptions import JSONSerializationError
        
        class NonSerializable:
            pass
        
        update_data = {
            "metadata": {"bad_data": NonSerializable()}  # This will fail serialization
        }
        
        with pytest.raises(JSONSerializationError, match="JSON serialization failed"):
            await json_repo.update(sample_model.id, update_data)
    
    async def test_update_with_complex_json_data(self, json_repo):
        """Test update method with complex JSON data types."""
        from uuid import uuid4
        from datetime import datetime
        from decimal import Decimal
        
        test_id = uuid4()
        test_uuid = uuid4()
        test_datetime = datetime.now()
        test_decimal = Decimal("456.78")
        
        update_data = {
            "metadata": {
                "uuid": test_uuid,
                "timestamp": test_datetime,
                "amount": test_decimal,
                "nested": {"deep": {"updated": "value"}}
            }
        }
        
        db_result = {
            "id": test_id,
            "name": "test_item",
            "value": 42,
            "metadata": f'{{"uuid": "{test_uuid}", "timestamp": "{test_datetime.isoformat()}", "amount": {float(test_decimal)}, "nested": {{"deep": {{"updated": "value"}}}}}}',
            "tags": '["tag1"]',
            "settings": None
        }
        
        json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        result = await json_repo.update(test_id, update_data)
        
        # Complex types should be properly deserialized
        assert result.metadata["uuid"] == str(test_uuid)
        assert result.metadata["timestamp"] == test_datetime.isoformat()
        assert result.metadata["amount"] == float(test_decimal)
        assert result.metadata["nested"]["deep"]["updated"] == "value"
    
    async def test_update_without_json_fields(self, mock_connection):
        """Test update method with a model that has no JSON fields."""
        from uuid import uuid4
        
        non_json_repo = BaseRepository(
            db_connection=mock_connection,
            table_name="simple_table",
            model_class=NonJSONModel,
            primary_key="id"
        )
        
        test_id = uuid4()
        update_data = {"name": "updated_test", "active": False}
        
        db_result = {
            "id": test_id,
            "name": "updated_test",
            "active": False
        }
        
        non_json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        result = await non_json_repo.update(test_id, update_data)
        
        assert result.name == "updated_test"
        assert result.active is False
        assert result.id == test_id
    
    async def test_update_preserves_original_data(self, json_repo, sample_model):
        """Test that update method doesn't modify the original update data."""
        update_data = {
            "metadata": {"key": "value"},
            "tags": ["tag1", "tag2"]
        }
        
        # Store original values
        original_metadata = update_data["metadata"].copy()
        original_tags = update_data["tags"].copy()
        
        db_result = {
            "id": sample_model.id,
            "name": sample_model.name,
            "value": sample_model.value,
            "metadata": '{"key": "value"}',
            "tags": '["tag1", "tag2"]',
            "settings": None
        }
        
        json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        await json_repo.update(sample_model.id, update_data)
        
        # Original data should be unchanged
        assert update_data["metadata"] == original_metadata
        assert update_data["tags"] == original_tags
    
    async def test_update_with_explicit_json_fields_config(self, mock_connection, sample_model):
        """Test update with explicit JSON fields configuration."""
        # Create repo with explicit JSON fields (subset of actual JSON fields)
        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=JSONTestModel,
            primary_key="id",
            json_fields={"metadata"},  # Only metadata should be processed as JSON
            auto_detect_json=False
        )
        
        update_data = {
            "metadata": {"key": "updated_value"},
            "tags": ["new_tag1", "new_tag2"],
            "settings": {"theme": "updated"}
        }
        
        db_result = {
            "id": sample_model.id,
            "name": sample_model.name,
            "value": sample_model.value,
            "metadata": '{"key": "updated_value"}',  # Should be deserialized
            "tags": ["new_tag1", "new_tag2"],       # Should remain as-is
            "settings": {"theme": "updated"}        # Should remain as-is
        }
        
        repo.db_connection._cursor.fetchone.return_value = db_result
        
        result = await repo.update(sample_model.id, update_data)
        
        # Only metadata should be deserialized, others should remain as-is
        assert result.metadata == {"key": "updated_value"}  # Deserialized
        assert result.tags == ["new_tag1", "new_tag2"]      # Unchanged
        assert result.settings == {"theme": "updated"}      # Unchanged
    
    @patch('psycopg_toolkit.repositories.base.logger')
    async def test_update_logging_behavior(self, mock_logger, json_repo, sample_model):
        """Test that update method logs preprocessing and postprocessing appropriately."""
        update_data = {
            "metadata": {"key": "updated_value"},
            "tags": ["new_tag"]
        }
        
        db_result = {
            "id": sample_model.id,
            "name": sample_model.name,
            "value": sample_model.value,
            "metadata": '{"key": "updated_value"}',
            "tags": '["new_tag"]',
            "settings": None
        }
        
        json_repo.db_connection._cursor.fetchone.return_value = db_result
        
        await json_repo.update(sample_model.id, update_data)
        
        # Should log preprocessing and postprocessing
        debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
        
        # Should have preprocessing logs
        assert any("Serialized JSON field" in call for call in debug_calls)
        assert any("Preprocessed 3 JSON fields" in call for call in debug_calls)
        
        # Should have postprocessing logs
        assert any("Deserialized JSON field" in call for call in debug_calls)
        assert any("Postprocessed 3 JSON fields" in call for call in debug_calls)