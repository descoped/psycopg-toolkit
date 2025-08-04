"""Shared test data for JSONB tests.

This module contains commonly used test data to avoid duplication.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4


def get_simple_json_data() -> dict[str, Any]:
    """Get simple JSON test data."""
    return {
        "key": "value",
        "number": 123,
        "boolean": True,
        "null": None,
        "list": [1, 2, 3],
        "nested": {"inner": "value"},
    }


def get_complex_json_data() -> dict[str, Any]:
    """Get complex JSON test data with special types."""
    return {
        "uuid": uuid4(),
        "datetime": datetime.now(),
        "decimal": Decimal("123.45"),
        "nested": {"deep": {"values": [1, 2, 3], "data": {"key": "value"}}},
    }


def get_invalid_json_strings():
    """Get a list of invalid JSON strings for testing."""
    return [
        ('{"unclosed": "bracket"', "Missing closing brace"),
        ('{"key": undefined}', "JavaScript undefined"),
        ('{key: "value"}', "Unquoted key"),
        ('{"trailing": "comma",}', "Trailing comma"),
        ('{"a": "b" "c": "d"}', "Missing comma"),
        ("{", "Just opening brace"),
        ("", "Empty string"),
    ]


def create_circular_reference():
    """Create a dictionary with circular reference."""
    data = {"key": "value"}
    data["self"] = data
    return data


def create_non_serializable_object():
    """Create an object that cannot be JSON serialized."""

    class NonSerializable:
        def __repr__(self):
            return "NonSerializable"

    return NonSerializable()
