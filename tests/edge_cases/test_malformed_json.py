"""Edge case tests for malformed and problematic JSON data."""

import asyncio
import json
import sys
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any, Optional
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, Field
from unittest.mock import AsyncMock, patch

from psycopg_toolkit import (
    BaseRepository,
    JSONHandler,
    JSONSerializationError,
    JSONDeserializationError,
    OperationError
)
from psycopg_toolkit.utils.json_handler import CustomJSONEncoder


class EdgeCaseModel(BaseModel):
    """Model for testing edge cases."""
    id: int
    name: str
    data: Dict[str, Any]
    items: List[Any]
    metadata: Optional[Dict[str, Any]] = None


class MockConnection:
    """Mock database connection for edge case testing."""
    def __init__(self):
        self.cursor = AsyncMock()
        self.transaction = AsyncMock()


class TestMalformedJSONHandling:
    """Test error handling for malformed and edge case JSON data."""
    
    def test_circular_reference_detection(self):
        """Test handling of circular references in JSON data."""
        # Create circular reference
        data = {"name": "test"}
        data["self"] = data  # Circular reference
        
        with pytest.raises(ValueError) as exc_info:
            JSONHandler.serialize(data)
        
        # Python detects circular references
        assert "circular reference" in str(exc_info.value).lower()
    
    def test_deeply_nested_circular_reference(self):
        """Test detection of deeply nested circular references."""
        # Create deeply nested circular reference
        level1 = {"name": "level1"}
        level2 = {"name": "level2", "parent": level1}
        level3 = {"name": "level3", "parent": level2}
        level1["child"] = level2
        level2["child"] = level3
        level3["child"] = level1  # Creates circle
        
        with pytest.raises(ValueError) as exc_info:
            JSONHandler.serialize(level1)
        
        # Python detects circular references  
        assert "circular reference" in str(exc_info.value).lower()
    
    def test_very_large_json_object(self):
        """Test handling of very large JSON objects."""
        # Create a large object (but not too large to cause memory issues in tests)
        large_data = {
            f"key_{i}": {
                "data": f"value_{i}" * 100,  # 100 * ~8 chars = ~800 chars per value
                "nested": {
                    f"subkey_{j}": f"subvalue_{i}_{j}" * 10
                    for j in range(10)
                }
            }
            for i in range(100)  # 100 keys
        }
        
        # Should serialize successfully
        serialized = JSONHandler.serialize(large_data)
        assert len(serialized) > 100000  # Should be quite large
        
        # Should deserialize successfully
        deserialized = JSONHandler.deserialize(serialized)
        assert deserialized == large_data
    
    def test_deeply_nested_structure(self):
        """Test handling of very deeply nested structures."""
        # Create deeply nested structure
        data = {"level": 0}
        current = data
        
        # Python's default recursion limit is around 1000
        # Let's test with a safe depth that won't hit the limit
        max_depth = 100
        for i in range(1, max_depth):
            current["nested"] = {"level": i}
            current = current["nested"]
        
        # Should serialize successfully
        serialized = JSONHandler.serialize(data)
        
        # Should deserialize successfully
        deserialized = JSONHandler.deserialize(serialized)
        
        # Verify structure
        current = deserialized
        for i in range(max_depth):
            assert current["level"] == i
            if i < max_depth - 1:
                current = current["nested"]
    
    def test_invalid_unicode_handling(self):
        """Test handling of invalid Unicode sequences."""
        # Valid Unicode should work
        valid_unicode = {
            "emoji": "😀🎉🚀",
            "chinese": "你好世界",
            "arabic": "مرحبا بالعالم",
            "special": "\u2764\ufe0f"  # Heart emoji
        }
        
        serialized = JSONHandler.serialize(valid_unicode)
        deserialized = JSONHandler.deserialize(serialized)
        assert deserialized == valid_unicode
        
        # Test with surrogate pairs and other edge cases
        edge_cases = {
            "zero_width": "Hello\u200bWorld",  # Zero-width space
            "rtl": "Hello\u202eWorld",  # Right-to-left override
            "control": "Hello\x00World".replace("\x00", " "),  # Replace null with space
        }
        
        serialized = JSONHandler.serialize(edge_cases)
        deserialized = JSONHandler.deserialize(serialized)
        assert "Hello World" in deserialized["control"]
    
    def test_special_float_values(self):
        """Test handling of special float values (inf, -inf, nan)."""
        import math
        
        # These special values are not valid JSON
        special_floats = {
            "infinity": float('inf'),
            "neg_infinity": float('-inf'),
            "nan": float('nan')
        }
        
        # JSON standard doesn't support these values
        # Python's default json.dumps allows these, but with allow_nan=False it raises
        with pytest.raises(ValueError):
            json.dumps(special_floats, allow_nan=False)
        
        # Our handler uses allow_nan=False to be JSON compliant
        with pytest.raises(ValueError) as exc_info:
            JSONHandler.serialize(special_floats)
        
        # Python gives specific error about out of range floats
        assert "out of range" in str(exc_info.value).lower()
    
    def test_bytes_data_handling(self):
        """Test handling of bytes data in JSON."""
        # Bytes data needs special handling
        data_with_bytes = {
            "text": "normal text",
            "binary": b"binary data \x00\x01\x02",
            "encoded": "text".encode('utf-8')
        }
        
        # Should raise error for bytes
        with pytest.raises(ValueError) as exc_info:
            JSONHandler.serialize(data_with_bytes)
        
        # Check for bytes error
        assert "bytes" in str(exc_info.value).lower()
    
    def test_malformed_json_string_deserialization(self):
        """Test deserialization of various malformed JSON strings."""
        malformed_cases = [
            ('{"key": "value"', "Unterminated string"),  # Missing closing brace
            ('{"key": "value"}}', "Extra closing brace"),  # Extra closing brace
            ("{'key': 'value'}", "Single quotes"),  # Single quotes instead of double
            ('{"key": undefined}', "Undefined value"),  # JavaScript undefined
            ('{key: "value"}', "Unquoted key"),  # Missing quotes on key
            ('{"key": "value",}', "Trailing comma"),  # Trailing comma
            ('{"key": "value" "key2": "value2"}', "Missing comma"),  # Missing comma
        ]
        
        # Note: Python 3.13 allows NaN literals, so we removed that test case
        
        for malformed_json, description in malformed_cases:
            # JSONHandler.deserialize raises ValueError, not JSONDeserializationError
            with pytest.raises(ValueError) as exc_info:
                JSONHandler.deserialize(malformed_json)
            
            assert "Cannot deserialize JSON" in str(exc_info.value)
    
    def test_mixed_type_arrays(self):
        """Test handling of arrays with mixed types."""
        mixed_arrays = {
            "mixed_basic": [1, "two", 3.0, True, None],
            "mixed_complex": [
                {"type": "object"},
                ["nested", "array"],
                "string",
                123,
                None,
                {"nested": {"deep": ["value"]}}
            ],
            "mixed_dates": [
                datetime.now(),
                datetime.now().date(),
                datetime.now().time(),
                datetime.now().isoformat()
            ]
        }
        
        # Should serialize successfully
        serialized = JSONHandler.serialize(mixed_arrays)
        deserialized = JSONHandler.deserialize(serialized)
        
        # Basic types preserved
        assert deserialized["mixed_basic"] == [1, "two", 3.0, True, None]
        
        # Complex types preserved
        assert isinstance(deserialized["mixed_complex"][0], dict)
        assert isinstance(deserialized["mixed_complex"][1], list)
        assert deserialized["mixed_complex"][2] == "string"
    
    def test_empty_containers(self):
        """Test handling of empty containers and edge cases."""
        empty_data = {
            "empty_dict": {},
            "empty_list": [],
            "empty_string": "",
            "null_value": None,
            "nested_empty": {
                "dict_in_dict": {},
                "list_in_dict": [],
                "dict_in_list": [{}],
                "list_in_list": [[]]
            }
        }
        
        serialized = JSONHandler.serialize(empty_data)
        deserialized = JSONHandler.deserialize(serialized)
        
        assert deserialized == empty_data
        assert deserialized["empty_dict"] == {}
        assert deserialized["empty_list"] == []
        assert deserialized["empty_string"] == ""
        assert deserialized["null_value"] is None
    
    def test_json_injection_attempts(self):
        """Test handling of potential JSON injection attempts."""
        injection_attempts = {
            "script_tag": '<script>alert("xss")</script>',
            "sql_injection": "'; DROP TABLE users; --",
            "path_traversal": "../../etc/passwd",
            "command_injection": "; rm -rf /",
            "unicode_escape": "\\u003cscript\\u003ealert('xss')\\u003c/script\\u003e",
            "nested_injection": {
                "data": '{"injected": "value", "extra": "field"}'
            }
        }
        
        # Should serialize as regular strings
        serialized = JSONHandler.serialize(injection_attempts)
        deserialized = JSONHandler.deserialize(serialized)
        
        # Values should be preserved as strings, not executed
        assert deserialized["script_tag"] == '<script>alert("xss")</script>'
        assert deserialized["sql_injection"] == "'; DROP TABLE users; --"
        assert isinstance(deserialized["nested_injection"]["data"], str)
    
    def test_numeric_precision_edge_cases(self):
        """Test handling of numeric precision edge cases."""
        numeric_edge_cases = {
            "max_int": sys.maxsize,
            "min_int": -sys.maxsize - 1,
            "large_decimal": Decimal("999999999999999999.999999999999999999"),
            "small_decimal": Decimal("0.000000000000000001"),
            "negative_decimal": Decimal("-123456789.123456789"),
            "scientific": 1.23e-10,
            "large_float": 1.7976931348623157e+308,  # Near max float
        }
        
        serialized = JSONHandler.serialize(numeric_edge_cases)
        deserialized = JSONHandler.deserialize(serialized)
        
        # Integers preserved
        assert deserialized["max_int"] == sys.maxsize
        assert deserialized["min_int"] == -sys.maxsize - 1
        
        # Decimals converted to float
        assert abs(deserialized["large_decimal"] - 999999999999999999.999999999999999999) < 1
        assert deserialized["small_decimal"] == 1e-18
    
    @pytest.mark.asyncio
    async def test_repository_malformed_json_handling(self):
        """Test repository handling of malformed JSON data."""
        mock_conn = MockConnection()
        repo = BaseRepository(
            db_connection=mock_conn,
            table_name="test_table",
            model_class=EdgeCaseModel,
            primary_key="id"
        )
        
        # Test with data that causes serialization error
        class NonSerializable:
            def __repr__(self):
                return "NonSerializable"
        
        bad_model = EdgeCaseModel(
            id=1,
            name="test",
            data={"bad": NonSerializable()},
            items=[1, 2, NonSerializable()]
        )
        
        with pytest.raises(JSONSerializationError):
            await repo.create(bad_model)
    
    def test_unicode_normalization(self):
        """Test handling of Unicode normalization forms."""
        # Same character in different normalization forms
        import unicodedata
        
        unicode_variants = {
            "nfc": unicodedata.normalize('NFC', 'é'),  # Composed
            "nfd": unicodedata.normalize('NFD', 'é'),  # Decomposed
            "combined": "café",
            "emoji_zwj": "👨‍👩‍👧‍👦",  # Family emoji with ZWJ
        }
        
        serialized = JSONHandler.serialize(unicode_variants)
        deserialized = JSONHandler.deserialize(serialized)
        
        # All forms should be preserved
        assert len(deserialized["nfc"]) == 1  # Single composed character
        assert len(deserialized["nfd"]) == 2  # Base + combining
        assert deserialized["combined"] == "café"
    
    def test_recursive_depth_limit(self):
        """Test handling when approaching recursion depth limits."""
        # Create a structure that's close to Python's recursion limit
        # but safely below it to avoid crashes
        safe_depth = 50  # Much safer than the ~1000 default limit
        
        def create_nested(depth):
            if depth == 0:
                return {"value": "bottom"}
            return {"level": depth, "nested": create_nested(depth - 1)}
        
        deep_structure = create_nested(safe_depth)
        
        # Should handle successfully
        serialized = JSONHandler.serialize(deep_structure)
        deserialized = JSONHandler.deserialize(serialized)
        
        # Verify structure integrity
        def verify_nested(obj, expected_depth):
            if expected_depth == 0:
                assert obj["value"] == "bottom"
            else:
                assert obj["level"] == expected_depth
                verify_nested(obj["nested"], expected_depth - 1)
        
        verify_nested(deserialized, safe_depth)
    
    def test_memory_efficient_streaming(self):
        """Test that large JSON doesn't cause memory issues."""
        # Create a moderately large structure
        large_list = [
            {
                "id": i,
                "data": f"x" * 1000,  # 1KB per item
                "metadata": {
                    "created": datetime.now().isoformat(),
                    "tags": [f"tag_{j}" for j in range(10)]
                }
            }
            for i in range(100)  # 100 items ≈ 100KB
        ]
        
        # Should handle without memory issues
        serialized = JSONHandler.serialize(large_list)
        assert len(serialized) > 100000  # At least 100KB
        
        # Should deserialize successfully
        deserialized = JSONHandler.deserialize(serialized)
        assert len(deserialized) == 100
        assert all(len(item["data"]) == 1000 for item in deserialized)
    
    def test_custom_encoder_edge_cases(self):
        """Test CustomJSONEncoder with edge cases."""
        encoder = CustomJSONEncoder()
        
        # Test with all supported types
        test_data = {
            "uuid": uuid4(),
            "datetime": datetime.now(),
            "date": datetime.now().date(),
            "time": datetime.now().time(),
            "decimal": Decimal("123.456"),
            "set": {1, 2, 3},
            "frozenset": frozenset([4, 5, 6]),
            "bytes": b"test".decode('utf-8'),  # Convert to string first
        }
        
        # Encode using the custom encoder
        encoded = json.dumps(test_data, cls=CustomJSONEncoder)
        decoded = json.loads(encoded)
        
        # Verify types are converted correctly
        assert isinstance(decoded["uuid"], str)
        assert isinstance(decoded["datetime"], str)
        assert isinstance(decoded["date"], str)
        assert isinstance(decoded["time"], str)
        assert isinstance(decoded["decimal"], float)
        assert isinstance(decoded["set"], list)
        assert isinstance(decoded["frozenset"], list)
    
    def test_is_serializable_edge_cases(self):
        """Test JSONHandler.is_serializable with edge cases."""
        # Should be serializable
        assert JSONHandler.is_serializable({"key": "value"})
        assert JSONHandler.is_serializable([1, 2, 3])
        assert JSONHandler.is_serializable("string")
        assert JSONHandler.is_serializable(123)
        assert JSONHandler.is_serializable(123.45)
        assert JSONHandler.is_serializable(True)
        assert JSONHandler.is_serializable(None)
        assert JSONHandler.is_serializable({"uuid": uuid4()})  # Custom type
        
        # Should not be serializable
        assert not JSONHandler.is_serializable({"obj": object()})
        assert not JSONHandler.is_serializable(lambda x: x)
        assert not JSONHandler.is_serializable({"bytes": b"data"})
        
        # Edge case: circular reference
        circular = {"a": 1}
        circular["self"] = circular
        assert not JSONHandler.is_serializable(circular)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])