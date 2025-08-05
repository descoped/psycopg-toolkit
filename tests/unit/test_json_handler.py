"""Unit tests for JSONHandler."""

import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from psycopg_toolkit.utils.json_handler import JSONHandler


class SampleModel(BaseModel):
    """Sample Pydantic model for testing."""

    id: UUID
    name: str
    value: int


class TestJSONHandler:
    """Test JSONHandler serialization and deserialization capabilities."""

    def test_basic_serialization(self):
        """Test basic data type serialization."""
        data = {"name": "test", "value": 123, "active": True, "null_field": None}
        result = JSONHandler.serialize(data)
        assert isinstance(result, str)
        assert '"name": "test"' in result
        assert '"value": 123' in result
        assert '"active": true' in result
        assert '"null_field": null' in result

    def test_complex_serialization(self):
        """Test complex nested structure serialization."""
        test_uuid = uuid4()
        test_datetime = datetime(2024, 1, 15, 10, 30, 45)

        data = {
            "user": {
                "id": test_uuid,
                "created": test_datetime,
                "balance": Decimal("100.50"),
                "tags": {"admin", "user"},
            },
            "settings": {"notifications": True, "theme": "dark"},
            "permissions": ["read", "write", "admin"],
        }

        result = JSONHandler.serialize(data)
        assert isinstance(result, str)

        # Should not raise any exceptions
        parsed = json.loads(result)
        assert parsed["user"]["id"] == str(test_uuid)
        assert parsed["user"]["created"] == test_datetime.isoformat()
        assert parsed["user"]["balance"] == 100.5
        assert isinstance(parsed["user"]["tags"], list)
        assert set(parsed["user"]["tags"]) == {"admin", "user"}

    def test_pydantic_model_serialization(self):
        """Test Pydantic model serialization."""
        model = SampleModel(id=uuid4(), name="test_model", value=42)

        result = JSONHandler.serialize(model)
        assert isinstance(result, str)

        parsed = json.loads(result)
        assert parsed["name"] == "test_model"
        assert parsed["value"] == 42
        assert isinstance(parsed["id"], str)  # UUID serialized to string

    def test_basic_deserialization(self):
        """Test basic JSON string deserialization."""
        json_str = '{"name": "test", "value": 123, "active": true, "null_field": null}'
        result = JSONHandler.deserialize(json_str)

        expected = {"name": "test", "value": 123, "active": True, "null_field": None}
        assert result == expected

    def test_complex_deserialization(self):
        """Test complex nested structure deserialization."""
        json_str = """
        {
            "user": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "John Doe",
                "tags": ["admin", "user"],
                "metadata": {
                    "created": "2024-01-15T10:30:45",
                    "preferences": {
                        "theme": "dark",
                        "notifications": true
                    }
                }
            },
            "items": [1, 2, 3, {"nested": "value"}]
        }
        """

        result = JSONHandler.deserialize(json_str)
        assert isinstance(result, dict)
        assert result["user"]["name"] == "John Doe"
        assert result["user"]["tags"] == ["admin", "user"]
        assert result["user"]["metadata"]["preferences"]["theme"] == "dark"
        assert result["items"][-1]["nested"] == "value"

    def test_none_deserialization(self):
        """Test None input handling."""
        result = JSONHandler.deserialize(None)
        assert result is None

    def test_bytes_deserialization(self):
        """Test bytes input deserialization."""
        json_bytes = b'{"test": "value", "number": 42}'
        result = JSONHandler.deserialize(json_bytes)
        assert result == {"test": "value", "number": 42}

    def test_empty_string_deserialization_error(self):
        """Test empty string deserialization raises error."""
        with pytest.raises(ValueError, match="Cannot deserialize JSON"):
            JSONHandler.deserialize("")

    def test_malformed_json_deserialization_error(self):
        """Test malformed JSON string deserialization raises error."""
        malformed_cases = [
            '{"unclosed": "object"',
            '{"trailing": "comma",}',
            '{invalid: "no quotes on key"}',
            '{"number": 123.45.67}',
            "null null",
            '{"nested": {"unclosed": "object"}',
        ]

        for malformed_json in malformed_cases:
            with pytest.raises(ValueError, match="Cannot deserialize JSON"):
                JSONHandler.deserialize(malformed_json)

    def test_invalid_bytes_deserialization_error(self):
        """Test invalid bytes deserialization raises error."""
        invalid_bytes = b'\xff\xfe{"invalid": "utf8"}'
        with pytest.raises(ValueError, match="Cannot deserialize JSON"):
            JSONHandler.deserialize(invalid_bytes)

    def test_serialization_error_handling(self):
        """Test error handling for non-serializable objects."""

        class NonSerializable:
            def __init__(self):
                self.circular = self

        with pytest.raises(ValueError, match="Cannot serialize to JSON"):
            JSONHandler.serialize({"obj": NonSerializable()})

    def test_circular_reference_error(self):
        """Test handling of circular references."""
        data = {"key": "value"}
        data["self"] = data  # Circular reference

        with pytest.raises(ValueError, match="Cannot serialize to JSON"):
            JSONHandler.serialize(data)

    def test_roundtrip_serialization(self):
        """Test serialization and deserialization roundtrip."""
        original_data = {
            "string": "test",
            "number": 123,
            "float": 123.45,
            "boolean": True,
            "null": None,
            "array": [1, 2, 3, "string"],
            "object": {"nested": "value", "number": 42},
        }

        serialized = JSONHandler.serialize(original_data)
        deserialized = JSONHandler.deserialize(serialized)
        assert deserialized == original_data

    def test_special_types_roundtrip(self):
        """Test roundtrip with special types that get converted."""
        test_uuid = uuid4()
        test_datetime = datetime(2024, 1, 15, 10, 30, 45)

        original_data = {
            "uuid": test_uuid,
            "datetime": test_datetime,
            "decimal": Decimal("123.45"),
            "set": {"a", "b", "c"},
            "date": date(2024, 1, 15),
        }

        serialized = JSONHandler.serialize(original_data)
        deserialized = JSONHandler.deserialize(serialized)

        # These types get converted during serialization
        assert deserialized["uuid"] == str(test_uuid)
        assert deserialized["datetime"] == test_datetime.isoformat()
        assert deserialized["decimal"] == 123.45
        assert set(deserialized["set"]) == {"a", "b", "c"}
        assert deserialized["date"] == "2024-01-15"

    def test_is_serializable_true_cases(self):
        """Test is_serializable returns True for valid data."""
        valid_cases = [
            {"key": "value"},
            [1, 2, 3],
            "string",
            123,
            123.45,
            True,
            None,
            uuid4(),
            datetime.now(),
            Decimal("123.45"),
            {"a", "b", "c"},
            SampleModel(id=uuid4(), name="test", value=42),
        ]

        for case in valid_cases:
            assert JSONHandler.is_serializable(case) is True

    def test_is_serializable_false_cases(self):
        """Test is_serializable returns False for invalid data."""

        class NonSerializable:
            def __init__(self):
                self.circular = self

        invalid_cases = [
            NonSerializable(),
            lambda x: x,  # Function
            object(),  # Generic object
        ]

        # Circular reference case
        circular_data = {"key": "value"}
        circular_data["self"] = circular_data
        invalid_cases.append(circular_data)

        for case in invalid_cases:
            assert JSONHandler.is_serializable(case) is False

    def test_unicode_handling(self):
        """Test Unicode string handling."""
        unicode_data = {
            "english": "Hello World",
            "chinese": "你好世界",
            "japanese": "こんにちは世界",
            "emoji": "🚀🎉🌟",
            "mixed": "Hello 世界 🌍",
        }

        serialized = JSONHandler.serialize(unicode_data)
        deserialized = JSONHandler.deserialize(serialized)

        assert deserialized == unicode_data
        # Verify ensure_ascii=False preserves Unicode
        assert "你好世界" in serialized
        assert "🚀🎉🌟" in serialized

    def test_large_data_handling(self):
        """Test handling of reasonably large data structures."""
        large_data = {
            "large_list": list(range(1000)),
            "large_dict": {f"key_{i}": f"value_{i}" for i in range(100)},
            "nested_data": {"level1": {"level2": {"level3": {"content": "deep nesting test"}}}},
        }

        serialized = JSONHandler.serialize(large_data)
        deserialized = JSONHandler.deserialize(serialized)

        assert len(deserialized["large_list"]) == 1000
        assert len(deserialized["large_dict"]) == 100
        assert deserialized["nested_data"]["level1"]["level2"]["level3"]["content"] == "deep nesting test"

    def test_empty_data_handling(self):
        """Test handling of empty data structures."""
        empty_cases = [{}, [], "", set(), None]

        for case in empty_cases:
            serialized = JSONHandler.serialize(case)
            deserialized = JSONHandler.deserialize(serialized)

            if isinstance(case, set):
                # Sets become lists
                assert deserialized == []
            else:
                assert deserialized == case

    def test_numeric_edge_cases(self):
        """Test numeric edge cases."""
        numeric_data = {
            "zero": 0,
            "negative": -123,
            "large_int": 999999999999999999,
            "small_float": 0.000001,
            "negative_float": -123.456,
            "decimal_zero": Decimal("0"),
            "decimal_negative": Decimal("-123.45"),
        }

        serialized = JSONHandler.serialize(numeric_data)
        deserialized = JSONHandler.deserialize(serialized)

        assert deserialized["zero"] == 0
        assert deserialized["negative"] == -123
        assert deserialized["large_int"] == 999999999999999999
        assert deserialized["small_float"] == 0.000001
        assert deserialized["negative_float"] == -123.456
        assert deserialized["decimal_zero"] == 0.0
        assert deserialized["decimal_negative"] == -123.45
