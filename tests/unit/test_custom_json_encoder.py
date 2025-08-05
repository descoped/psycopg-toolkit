"""Unit tests for CustomJSONEncoder."""

import json
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from psycopg_toolkit.utils.json_handler import CustomJSONEncoder


class SamplePydanticModel(BaseModel):
    """Sample Pydantic model for encoder testing."""

    id: UUID
    name: str
    value: int


class TestCustomJSONEncoder:
    """Test CustomJSONEncoder serialization capabilities."""

    def test_uuid_serialization(self):
        """Test UUID serialization to string."""
        test_uuid = uuid4()
        encoder = CustomJSONEncoder()
        result = encoder.default(test_uuid)
        assert result == str(test_uuid)
        assert isinstance(result, str)

    def test_datetime_serialization(self):
        """Test datetime serialization to ISO format."""
        test_datetime = datetime(2024, 1, 15, 10, 30, 45, 123456)
        encoder = CustomJSONEncoder()
        result = encoder.default(test_datetime)
        expected = test_datetime.isoformat()
        assert result == expected
        assert isinstance(result, str)
        # Verify it's a valid ISO format
        assert result == "2024-01-15T10:30:45.123456"

    def test_date_serialization(self):
        """Test date serialization to ISO format."""
        test_date = date(2024, 1, 15)
        encoder = CustomJSONEncoder()
        result = encoder.default(test_date)
        expected = test_date.isoformat()
        assert result == expected
        assert isinstance(result, str)
        assert result == "2024-01-15"

    def test_decimal_serialization(self):
        """Test Decimal serialization to float."""
        test_decimal = Decimal("123.45")
        encoder = CustomJSONEncoder()
        result = encoder.default(test_decimal)
        assert result == 123.45
        assert isinstance(result, float)

        # Test with high precision
        test_decimal_precise = Decimal("123.456789012345")
        result_precise = encoder.default(test_decimal_precise)
        assert isinstance(result_precise, float)
        assert abs(result_precise - 123.456789012345) < 1e-10

    def test_set_serialization(self):
        """Test set serialization to list."""
        test_set = {1, 2, 3, "a", "b"}
        encoder = CustomJSONEncoder()
        result = encoder.default(test_set)
        assert isinstance(result, list)
        assert set(result) == test_set
        assert len(result) == len(test_set)

    def test_pydantic_model_serialization(self):
        """Test Pydantic model serialization via model_dump()."""
        test_model = SamplePydanticModel(id=uuid4(), name="test_model", value=42)
        encoder = CustomJSONEncoder()
        result = encoder.default(test_model)

        expected = test_model.model_dump()
        assert result == expected
        assert isinstance(result, dict)
        assert result["name"] == "test_model"
        assert result["value"] == 42
        assert isinstance(result["id"], UUID)  # UUID not serialized yet

    def test_unsupported_type_raises_error(self):
        """Test that unsupported types raise TypeError."""

        class NonSerializable:
            pass

        encoder = CustomJSONEncoder()
        with pytest.raises(TypeError):
            encoder.default(NonSerializable())

    def test_none_handling(self):
        """Test that None values are handled by base encoder."""
        encoder = CustomJSONEncoder()
        # None should be handled by the base encoder, not our custom logic
        with pytest.raises(TypeError):
            encoder.default(None)

    def test_full_json_dumps_integration(self):
        """Test integration with json.dumps()."""
        test_data = {
            "uuid": uuid4(),
            "timestamp": datetime.now(),
            "date": date.today(),
            "price": Decimal("99.99"),
            "tags": {"python", "json", "test"},
            "model": SamplePydanticModel(id=uuid4(), name="integration_test", value=100),
        }

        # Should not raise any exceptions
        json_string = json.dumps(test_data, cls=CustomJSONEncoder)
        assert isinstance(json_string, str)

        # Verify we can parse it back
        parsed = json.loads(json_string)
        assert isinstance(parsed, dict)
        assert isinstance(parsed["uuid"], str)
        assert isinstance(parsed["timestamp"], str)
        assert isinstance(parsed["date"], str)
        assert isinstance(parsed["price"], float)
        assert isinstance(parsed["tags"], list)
        assert isinstance(parsed["model"], dict)

    def test_nested_complex_structure(self):
        """Test serialization of deeply nested structures."""
        test_uuid = uuid4()
        test_data = {
            "level1": {
                "level2": {
                    "uuid": test_uuid,
                    "timestamp": datetime(2024, 1, 15, 12, 0, 0),
                    "nested_list": [
                        {"price": Decimal("10.50"), "tags": {"a", "b"}},
                        {"price": Decimal("20.99"), "tags": {"c", "d"}},
                    ],
                }
            }
        }

        json_string = json.dumps(test_data, cls=CustomJSONEncoder)
        parsed = json.loads(json_string)

        # Verify nested structure is preserved
        assert parsed["level1"]["level2"]["uuid"] == str(test_uuid)
        assert parsed["level1"]["level2"]["timestamp"] == "2024-01-15T12:00:00"
        assert len(parsed["level1"]["level2"]["nested_list"]) == 2
        assert parsed["level1"]["level2"]["nested_list"][0]["price"] == 10.5
        assert isinstance(parsed["level1"]["level2"]["nested_list"][0]["tags"], list)

    def test_empty_collections(self):
        """Test serialization of empty collections."""
        encoder = CustomJSONEncoder()

        # Empty set
        empty_set = set()
        result = encoder.default(empty_set)
        assert result == []
        assert isinstance(result, list)

    def test_special_decimal_values(self):
        """Test serialization of special Decimal values."""
        encoder = CustomJSONEncoder()

        # Zero
        zero_decimal = Decimal("0")
        assert encoder.default(zero_decimal) == 0.0

        # Negative
        negative_decimal = Decimal("-123.45")
        assert encoder.default(negative_decimal) == -123.45

        # Very small
        small_decimal = Decimal("0.0001")
        assert encoder.default(small_decimal) == 0.0001

    def test_datetime_with_timezone_info(self):
        """Test datetime serialization preserves timezone info."""
        import datetime as dt

        # Create timezone-aware datetime
        tz = dt.timezone(dt.timedelta(hours=5))
        test_datetime = datetime(2024, 1, 15, 10, 30, 45, tzinfo=tz)

        encoder = CustomJSONEncoder()
        result = encoder.default(test_datetime)

        assert isinstance(result, str)
        assert "+05:00" in result  # Timezone info preserved

        # Verify it's still valid ISO format
        parsed_back = datetime.fromisoformat(result)
        assert parsed_back == test_datetime
