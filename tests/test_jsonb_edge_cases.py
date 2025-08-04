"""JSONB edge cases and error handling tests."""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from conftest import SimpleJSON
from repositories.jsonb_repositories import SimpleJSONRepository

from psycopg_toolkit import JSONSerializationError


@pytest.mark.asyncio
class TestJSONBEdgeCases:
    """Test JSONB edge cases and error handling."""

    async def test_large_jsonb_document(self, jsonb_tables):
        """Test handling of large JSONB documents."""
        repo = SimpleJSONRepository(jsonb_tables)

        # Create large nested structure
        large_data = {
            "level1": {
                f"key_{i}": {"level2": {f"subkey_{j}": list(range(10)) for j in range(10)}} for i in range(10)
            }
        }

        # Should handle large documents
        created = await repo.create(SimpleJSON(data=large_data))
        retrieved = await repo.get_by_id(created.id)

        assert retrieved.data == large_data

    async def test_deeply_nested_jsonb(self, jsonb_tables):
        """Test deeply nested JSONB structures."""
        repo = SimpleJSONRepository(jsonb_tables)

        # Create deeply nested structure
        nested = {"value": "deep"}
        for _i in range(20):
            nested = {"level": nested}

        # Should handle deep nesting
        created = await repo.create(SimpleJSON(data=nested))
        retrieved = await repo.get_by_id(created.id)

        # Verify deep value
        current = retrieved.data
        for _ in range(20):
            current = current["level"]
        assert current["value"] == "deep"

    async def test_special_json_values(self, jsonb_tables):
        """Test special JSON values (null, true, false)."""
        repo = SimpleJSONRepository(jsonb_tables)

        special_data = {
            "null_value": None,
            "true_value": True,
            "false_value": False,
            "empty_string": "",
            "zero": 0,
            "empty_array": [],
            "empty_object": {},
        }

        created = await repo.create(SimpleJSON(data=special_data))
        retrieved = await repo.get_by_id(created.id)

        assert retrieved.data["null_value"] is None
        assert retrieved.data["true_value"] is True
        assert retrieved.data["false_value"] is False
        assert retrieved.data["empty_string"] == ""
        assert retrieved.data["zero"] == 0
        assert retrieved.data["empty_array"] == []
        assert retrieved.data["empty_object"] == {}

    async def test_numeric_precision(self, jsonb_tables):
        """Test numeric precision in JSONB."""
        repo = SimpleJSONRepository(jsonb_tables)

        # Test various numeric values
        numeric_data = {
            "integer": 42,
            "float": 3.14159265359,
            "large_int": 9007199254740991,  # Max safe integer in JavaScript
            "negative": -123.456,
            "scientific": 1.23e-10,
        }

        created = await repo.create(SimpleJSON(data=numeric_data))
        retrieved = await repo.get_by_id(created.id)

        assert retrieved.data["integer"] == 42
        assert abs(retrieved.data["float"] - 3.14159265359) < 1e-10
        assert retrieved.data["large_int"] == 9007199254740991
        assert retrieved.data["negative"] == -123.456
        assert abs(retrieved.data["scientific"] - 1.23e-10) < 1e-15

    async def test_unicode_and_escaping(self, jsonb_tables):
        """Test Unicode and special character escaping."""
        repo = SimpleJSONRepository(jsonb_tables)

        unicode_data = {
            "chinese": "你好世界",
            "arabic": "مرحبا بالعالم",
            "emoji": "🚀🌟😀",
            "mixed": "Hello 世界 🌍",
            "escape_chars": "Line1\nLine2\tTab\r\nCRLF",
            "quotes": 'She said "Hello"',
            "backslash": "C:\\path\\to\\file",
            "url": "https://example.com/path?q=test&p=1",
        }

        created = await repo.create(SimpleJSON(data=unicode_data))
        retrieved = await repo.get_by_id(created.id)

        assert retrieved.data == unicode_data

    async def test_malformed_json_handling(self, jsonb_tables):
        """Test handling of malformed JSON data."""
        # Direct SQL insert of malformed data
        async with jsonb_tables.cursor() as cur:
            # JSONB will validate on insert
            with pytest.raises(Exception):
                await cur.execute("INSERT INTO jsonb_simple (data) VALUES (%s)", ["{invalid json}"])

    async def test_circular_reference_detection(self, jsonb_tables):
        """Test circular reference detection."""
        repo = SimpleJSONRepository(jsonb_tables)

        # Create circular reference
        data = {"key": "value"}
        data["self"] = data

        # Should raise serialization error
        with pytest.raises(JSONSerializationError):
            await repo.create(SimpleJSON(data=data))

    async def test_non_serializable_types(self, jsonb_tables):
        """Test handling of non-serializable Python types."""
        repo = SimpleJSONRepository(jsonb_tables)

        # Test with types that need conversion
        now = datetime.now()
        uid = uuid4()
        decimal_val = Decimal("123.45")

        # Convert to serializable types
        data = {
            "datetime": now.isoformat(),
            "uuid": str(uid),
            "decimal": float(decimal_val),
            "set": list({1, 2, 3}),  # Convert set to list
        }

        created = await repo.create(SimpleJSON(data=data))
        retrieved = await repo.get_by_id(created.id)

        assert retrieved.data["datetime"] == now.isoformat()
        assert retrieved.data["uuid"] == str(uid)
        assert retrieved.data["decimal"] == 123.45
        assert set(retrieved.data["set"]) == {1, 2, 3}

    async def test_jsonb_size_limits(self, jsonb_tables):
        """Test JSONB size limits."""
        repo = SimpleJSONRepository(jsonb_tables)

        # Create large string (but not too large for Postgres)
        large_string = "x" * 10000  # 10KB string
        data = {
            "large_field": large_string,
            "array": [large_string for _ in range(10)],  # ~100KB
        }

        # Should handle reasonable sizes
        created = await repo.create(SimpleJSON(data=data))
        retrieved = await repo.get_by_id(created.id)

        assert len(retrieved.data["large_field"]) == 10000
        assert len(retrieved.data["array"]) == 10

    async def test_jsonb_key_order(self, jsonb_tables):
        """Test that JSONB preserves logical structure but not key order."""
        repo = SimpleJSONRepository(jsonb_tables)

        # Create with specific key order
        ordered_data = {
            "z_last": "should not be last in JSONB",
            "a_first": "should not be first in JSONB",
            "m_middle": "somewhere in middle",
        }

        created = await repo.create(SimpleJSON(data=ordered_data))
        retrieved = await repo.get_by_id(created.id)

        # Values should be preserved
        assert retrieved.data["z_last"] == "should not be last in JSONB"
        assert retrieved.data["a_first"] == "should not be first in JSONB"
        assert retrieved.data["m_middle"] == "somewhere in middle"

        # All keys should exist (order doesn't matter in JSONB)
        assert set(retrieved.data.keys()) == {"z_last", "a_first", "m_middle"}

    async def test_jsonb_duplicate_keys(self, jsonb_tables):
        """Test JSONB handling of duplicate keys."""
        # JSONB automatically handles duplicates by keeping last value
        from psycopg.rows import dict_row

        async with jsonb_tables.cursor(row_factory=dict_row) as cur:
            # Insert JSON with duplicate keys (JSONB will deduplicate)
            await cur.execute(
                "INSERT INTO jsonb_simple (data) VALUES (%s::jsonb) RETURNING *", ['{"key": "value1", "key": "value2"}']
            )
            row = await cur.fetchone()

            # JSONB keeps the last value
            assert row["data"]["key"] == "value2"

    async def test_null_vs_missing_keys(self, jsonb_tables):
        """Test difference between null values and missing keys."""
        repo = SimpleJSONRepository(jsonb_tables)

        # Create with explicit null
        data_with_null = {"exists": "yes", "null_field": None}
        await repo.create(SimpleJSON(data=data_with_null))

        # Create without the field
        data_without = {"exists": "yes"}
        await repo.create(SimpleJSON(data=data_without))

        # Test existence queries
        async with jsonb_tables.cursor() as cur:
            # Check for key existence (includes null values)
            await cur.execute("SELECT COUNT(*) FROM jsonb_simple WHERE data ? 'null_field'")
            count = (await cur.fetchone())[0]
            assert count == 1  # Only first record has the key

            # Check for non-null values
            await cur.execute("SELECT COUNT(*) FROM jsonb_simple WHERE data->>'null_field' IS NOT NULL")
            count = (await cur.fetchone())[0]
            assert count == 0  # The field exists but is null
