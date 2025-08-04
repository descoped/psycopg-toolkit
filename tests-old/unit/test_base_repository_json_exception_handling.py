"""Unit tests for BaseRepository JSON exception handling."""

from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, Field

from psycopg_toolkit.exceptions import JSONDeserializationError, JSONSerializationError
from psycopg_toolkit.repositories.base import BaseRepository


class SampleJSONModel(BaseModel):
    """Test model with JSON fields."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    metadata: dict[str, Any]
    tags: list[str]
    settings: dict[str, str] | None = None


class TestBaseRepositoryJSONExceptionHandling:
    """Test JSON exception handling in BaseRepository."""

    @pytest.fixture
    def mock_connection(self):
        """Create a mock database connection."""
        return AsyncMock()

    @pytest.fixture
    def strict_repo(self, mock_connection):
        """Create a repository with strict JSON processing enabled."""
        return BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=SampleJSONModel,
            primary_key="id",
            strict_json_processing=True,
        )

    @pytest.fixture
    def lenient_repo(self, mock_connection):
        """Create a repository with strict JSON processing disabled (default)."""
        return BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=SampleJSONModel,
            primary_key="id",
            strict_json_processing=False,
        )

    def test_strict_json_processing_attribute(self, strict_repo, lenient_repo):
        """Test that strict_json_processing attribute is properly set."""
        assert strict_repo._strict_json_processing is True
        assert lenient_repo._strict_json_processing is False

    def test_preprocess_serialization_error_strict_mode(self, strict_repo):
        """Test that preprocessing raises JSONSerializationError in strict mode."""

        # Create a non-serializable object
        class NonSerializable:
            pass

        test_data = {"name": "test_item", "metadata": {"bad_data": NonSerializable()}, "tags": ["tag1"]}

        with pytest.raises(JSONSerializationError) as exc_info:
            strict_repo._preprocess_data(test_data)

        error = exc_info.value
        assert error.field_name == "metadata"
        assert error.value == {"bad_data": test_data["metadata"]["bad_data"]}
        assert error.original_error is not None
        assert "JSON serialization failed for field 'metadata'" in str(error)

    def test_preprocess_serialization_error_propagation(self, strict_repo):
        """Test that JSONSerializationError contains all expected details."""
        test_data = {
            "name": "test_item",
            "metadata": {"func": lambda x: x},  # Non-serializable lambda
            "tags": ["tag1"],
        }

        with pytest.raises(JSONSerializationError) as exc_info:
            strict_repo._preprocess_data(test_data)

        error = exc_info.value
        assert error.field_name == "metadata"
        assert "func" in error.value
        assert isinstance(error.original_error, ValueError)

    def test_postprocess_deserialization_error_strict_mode(self, strict_repo):
        """Test that postprocessing raises JSONDeserializationError in strict mode."""
        test_data = {
            "name": "test_item",
            "metadata": "invalid json {",  # Invalid JSON
            "tags": '["tag1", "tag2"]',
            "settings": '{"theme": "dark"}',
        }

        with pytest.raises(JSONDeserializationError) as exc_info:
            strict_repo._postprocess_data(test_data)

        error = exc_info.value
        assert error.field_name == "metadata"
        assert error.json_data == "invalid json {"
        assert error.original_error is not None
        assert "JSON deserialization failed for field 'metadata'" in str(error)

    def test_postprocess_deserialization_error_lenient_mode(self, lenient_repo):
        """Test that postprocessing logs warnings but doesn't raise errors in lenient mode."""
        test_data = {
            "name": "test_item",
            "metadata": "invalid json {",  # Invalid JSON
            "tags": '["tag1", "tag2"]',
            "settings": '{"theme": "dark"}',
        }

        with patch("psycopg_toolkit.repositories.base.logger") as mock_logger:
            result = lenient_repo._postprocess_data(test_data)

            # Should not raise an exception
            assert result["name"] == "test_item"
            assert result["metadata"] == "invalid json {"  # Kept as-is
            assert result["tags"] == ["tag1", "tag2"]  # Valid JSON processed
            assert result["settings"] == {"theme": "dark"}  # Valid JSON processed

            # Should log warnings
            mock_logger.warning.assert_called()
            warning_calls = [call[0][0] for call in mock_logger.warning.call_args_list]
            assert any("Failed to deserialize JSON field 'metadata'" in call for call in warning_calls)
            assert any("Keeping original value for field 'metadata'" in call for call in warning_calls)

    def test_postprocess_partial_failure_strict_mode(self, strict_repo):
        """Test strict mode fails on first deserialization error."""
        test_data = {
            "name": "test_item",
            "metadata": '{"valid": "json"}',  # Valid JSON
            "tags": "invalid json [",  # Invalid JSON - should fail here
            "settings": '{"theme": "dark"}',  # Valid but won't be processed due to failure
        }

        with pytest.raises(JSONDeserializationError) as exc_info:
            strict_repo._postprocess_data(test_data)

        # The exact field that fails first depends on iteration order
        # But we should get a JSONDeserializationError
        error = exc_info.value
        assert error.field_name in ["tags", "metadata", "settings"]
        assert error.original_error is not None

    def test_postprocess_partial_failure_lenient_mode(self, lenient_repo):
        """Test lenient mode processes valid fields and skips invalid ones."""
        test_data = {
            "name": "test_item",
            "metadata": '{"valid": "json"}',  # Valid JSON
            "tags": "invalid json [",  # Invalid JSON
            "settings": '{"theme": "dark"}',  # Valid JSON
        }

        with patch("psycopg_toolkit.repositories.base.logger") as mock_logger:
            result = lenient_repo._postprocess_data(test_data)

            # Valid JSON should be processed
            assert result["metadata"] == {"valid": "json"}
            assert result["settings"] == {"theme": "dark"}
            # Invalid JSON should be kept as-is
            assert result["tags"] == "invalid json ["

            # Should log warnings for invalid JSON
            mock_logger.warning.assert_called()

    def test_nested_exception_chaining(self, strict_repo):
        """Test that original exceptions are properly chained."""
        test_data = {"name": "test_item", "metadata": "malformed json }"}

        try:
            strict_repo._postprocess_data(test_data)
            pytest.fail("Expected JSONDeserializationError")
        except JSONDeserializationError as e:
            # Check that the original JSON parsing error is preserved
            assert e.original_error is not None
            assert e.__cause__ is e.original_error

    def test_exception_context_preservation(self, strict_repo):
        """Test that exceptions preserve context information."""
        # Test serialization error context
        non_serializable_data = {"name": "test", "metadata": {"func": lambda: None}}

        try:
            strict_repo._preprocess_data(non_serializable_data)
            pytest.fail("Expected JSONSerializationError")
        except JSONSerializationError as e:
            assert e.field_name == "metadata"
            assert "func" in e.value
            assert e.original_error is not None

        # Test deserialization error context
        invalid_json_data = {"name": "test", "metadata": "{invalid json"}

        try:
            strict_repo._postprocess_data(invalid_json_data)
            pytest.fail("Expected JSONDeserializationError")
        except JSONDeserializationError as e:
            assert e.field_name == "metadata"
            assert e.json_data == "{invalid json"
            assert e.original_error is not None

    def test_mixed_valid_invalid_data_strict(self, strict_repo):
        """Test strict mode with mix of valid and invalid data."""
        # Preprocessing with mixed data
        test_data = {
            "name": "test",
            "metadata": {"valid": "data"},
            "tags": ["valid", "list"],
            "settings": {"bad": lambda: None},  # Non-serializable
        }

        with pytest.raises(JSONSerializationError) as exc_info:
            strict_repo._preprocess_data(test_data)

        # Should fail on the non-serializable field
        assert exc_info.value.field_name == "settings"

    def test_mixed_valid_invalid_data_lenient(self, lenient_repo):
        """Test lenient mode with mix of valid and invalid JSON."""
        test_data = {
            "name": "test",
            "metadata": '{"valid": "json"}',
            "tags": '["valid", "array"]',
            "settings": "invalid json {",
        }

        with patch("psycopg_toolkit.repositories.base.logger"):
            result = lenient_repo._postprocess_data(test_data)

            # Valid JSON should be processed
            assert result["metadata"] == {"valid": "json"}
            assert result["tags"] == ["valid", "array"]
            # Invalid JSON should be preserved
            assert result["settings"] == "invalid json {"

    @patch("psycopg_toolkit.repositories.base.logger")
    def test_error_logging_strict_mode(self, mock_logger, strict_repo):
        """Test that strict mode logs errors before raising exceptions."""
        test_data = {"name": "test", "metadata": "invalid json"}

        with pytest.raises(JSONDeserializationError):
            strict_repo._postprocess_data(test_data)

        # Should log error (not warning) in strict mode
        mock_logger.error.assert_called()
        error_calls = [call[0][0] for call in mock_logger.error.call_args_list]
        assert any("Failed to deserialize JSON field 'metadata'" in call for call in error_calls)

    @patch("psycopg_toolkit.repositories.base.logger")
    def test_warning_logging_lenient_mode(self, mock_logger, lenient_repo):
        """Test that lenient mode logs warnings for JSON errors."""
        test_data = {"name": "test", "metadata": "invalid json"}

        lenient_repo._postprocess_data(test_data)

        # Should log warnings (not errors) in lenient mode
        mock_logger.warning.assert_called()
        # Should not log errors
        mock_logger.error.assert_not_called()

    def test_none_values_handling_both_modes(self, strict_repo, lenient_repo):
        """Test that None values are handled correctly in both modes."""
        test_data = {
            "name": "test",
            "metadata": '{"valid": "json"}',
            "tags": None,  # None values should not be processed
            "settings": None,
        }

        # Both modes should handle None values the same way
        strict_result = strict_repo._postprocess_data(test_data)
        lenient_result = lenient_repo._postprocess_data(test_data)

        assert strict_result == lenient_result
        assert strict_result["metadata"] == {"valid": "json"}
        assert strict_result["tags"] is None
        assert strict_result["settings"] is None
