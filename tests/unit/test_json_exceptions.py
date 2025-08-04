"""Unit tests for JSON-specific exceptions."""

from psycopg_toolkit.exceptions import (
    JSONDeserializationError,
    JSONProcessingError,
    JSONSerializationError,
    PsycoDBException,
    RepositoryError,
)


class TestJSONExceptions:
    """Test JSON exception classes."""

    def test_json_processing_error_inheritance(self):
        """Test JSONProcessingError inherits from RepositoryError."""
        error = JSONProcessingError("Test error")

        assert isinstance(error, JSONProcessingError)
        assert isinstance(error, RepositoryError)
        assert isinstance(error, PsycoDBException)
        assert isinstance(error, Exception)

    def test_json_processing_error_basic(self):
        """Test basic JSONProcessingError functionality."""
        message = "JSON processing failed"
        error = JSONProcessingError(message)

        assert str(error) == message
        assert error.field_name is None
        assert error.original_error is None

    def test_json_processing_error_with_field_name(self):
        """Test JSONProcessingError with field name."""
        message = "JSON processing failed"
        field_name = "metadata"
        error = JSONProcessingError(message, field_name=field_name)

        assert str(error) == message
        assert error.field_name == field_name
        assert error.original_error is None

    def test_json_processing_error_with_original_error(self):
        """Test JSONProcessingError with original error."""
        message = "JSON processing failed"
        original_error = ValueError("Original error")
        error = JSONProcessingError(message, original_error=original_error)

        assert str(error) == message
        assert error.field_name is None
        assert error.original_error == original_error

    def test_json_processing_error_all_params(self):
        """Test JSONProcessingError with all parameters."""
        message = "JSON processing failed"
        field_name = "settings"
        original_error = TypeError("Type error")

        error = JSONProcessingError(message, field_name=field_name, original_error=original_error)

        assert str(error) == message
        assert error.field_name == field_name
        assert error.original_error == original_error

    def test_json_serialization_error_inheritance(self):
        """Test JSONSerializationError inherits from JSONProcessingError."""
        error = JSONSerializationError("Serialization failed")

        assert isinstance(error, JSONSerializationError)
        assert isinstance(error, JSONProcessingError)
        assert isinstance(error, RepositoryError)
        assert isinstance(error, PsycoDBException)
        assert isinstance(error, Exception)

    def test_json_serialization_error_basic(self):
        """Test basic JSONSerializationError functionality."""
        message = "Serialization failed"
        error = JSONSerializationError(message)

        assert str(error) == message
        assert error.field_name is None
        assert error.value is None
        assert error.original_error is None

    def test_json_serialization_error_with_value(self):
        """Test JSONSerializationError with value."""
        message = "Cannot serialize object"
        value = {"key": "value"}
        error = JSONSerializationError(message, value=value)

        assert str(error) == message
        assert error.field_name is None
        assert error.value == value
        assert error.original_error is None

    def test_json_serialization_error_all_params(self):
        """Test JSONSerializationError with all parameters."""
        message = "Cannot serialize object"
        field_name = "metadata"
        value = {"complex": "object"}
        original_error = TypeError("Object not serializable")

        error = JSONSerializationError(message, field_name=field_name, value=value, original_error=original_error)

        assert str(error) == message
        assert error.field_name == field_name
        assert error.value == value
        assert error.original_error == original_error

    def test_json_deserialization_error_inheritance(self):
        """Test JSONDeserializationError inherits from JSONProcessingError."""
        error = JSONDeserializationError("Deserialization failed")

        assert isinstance(error, JSONDeserializationError)
        assert isinstance(error, JSONProcessingError)
        assert isinstance(error, RepositoryError)
        assert isinstance(error, PsycoDBException)
        assert isinstance(error, Exception)

    def test_json_deserialization_error_basic(self):
        """Test basic JSONDeserializationError functionality."""
        message = "Deserialization failed"
        error = JSONDeserializationError(message)

        assert str(error) == message
        assert error.field_name is None
        assert error.json_data is None
        assert error.original_error is None

    def test_json_deserialization_error_with_json_data(self):
        """Test JSONDeserializationError with JSON data."""
        message = "Invalid JSON format"
        json_data = '{"invalid": json}'
        error = JSONDeserializationError(message, json_data=json_data)

        assert str(error) == message
        assert error.field_name is None
        assert error.json_data == json_data
        assert error.original_error is None

    def test_json_deserialization_error_all_params(self):
        """Test JSONDeserializationError with all parameters."""
        message = "Invalid JSON format"
        field_name = "tags"
        json_data = '{"invalid": json}'
        original_error = ValueError("Invalid JSON")

        error = JSONDeserializationError(
            message, field_name=field_name, json_data=json_data, original_error=original_error
        )

        assert str(error) == message
        assert error.field_name == field_name
        assert error.json_data == json_data
        assert error.original_error == original_error

    def test_exception_chaining(self):
        """Test that exceptions can be properly chained."""
        original_error = ValueError("Original JSON error")

        try:
            raise JSONSerializationError(
                "Failed to serialize data", field_name="metadata", original_error=original_error
            )
        except JSONSerializationError as e:
            assert e.original_error == original_error
            assert e.field_name == "metadata"

    def test_exception_context_preservation(self):
        """Test that exception context is properly preserved."""
        test_value = {"test": "data"}
        test_json = '{"malformed": json}'

        # Test serialization error context
        serialization_error = JSONSerializationError("Serialization failed", field_name="metadata", value=test_value)
        assert serialization_error.value == test_value
        assert serialization_error.field_name == "metadata"

        # Test deserialization error context
        deserialization_error = JSONDeserializationError(
            "Deserialization failed", field_name="settings", json_data=test_json
        )
        assert deserialization_error.json_data == test_json
        assert deserialization_error.field_name == "settings"

    def test_exception_str_representation(self):
        """Test string representation of exceptions."""
        message = "Test error message"

        processing_error = JSONProcessingError(message)
        serialization_error = JSONSerializationError(message)
        deserialization_error = JSONDeserializationError(message)

        assert str(processing_error) == message
        assert str(serialization_error) == message
        assert str(deserialization_error) == message
