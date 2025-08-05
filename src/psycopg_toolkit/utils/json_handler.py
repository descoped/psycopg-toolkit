"""JSON handling utilities for JSONB field support."""

import json
import logging
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for common Python types.

    Handles serialization of UUID, datetime, date, time, Decimal, set, frozenset, and Pydantic models
    that are commonly used in applications but not natively JSON serializable.
    """

    def default(self, obj: Any) -> Any:
        """Convert objects to JSON-serializable format.

        Args:
            obj: The object to serialize

        Returns:
            JSON-serializable representation of the object

        Raises:
            TypeError: If the object cannot be serialized
        """
        if isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, datetime | date | time):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, set | frozenset):
            return list(obj)
        elif hasattr(obj, "model_dump"):  # Pydantic model
            return obj.model_dump()

        # Let the base class handle the error for unsupported types
        return super().default(obj)


class JSONHandler:
    """Handle JSON serialization/deserialization for JSONB fields.

    Provides static methods for converting Python objects to/from JSON strings
    with proper error handling and support for common Python types via CustomJSONEncoder.
    """

    @staticmethod
    def serialize(data: Any) -> str:
        """Serialize Python objects to JSON string.

        Args:
            data: The Python object to serialize

        Returns:
            JSON string representation of the data

        Raises:
            ValueError: If the serialization fails with descriptive error message
        """
        try:
            return json.dumps(data, cls=CustomJSONEncoder, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError, OverflowError) as e:
            logger.error(f"JSON serialization failed for data type {type(data).__name__}: {e}")
            raise ValueError(f"Cannot serialize to JSON: {e}") from e

    @staticmethod
    def deserialize(json_str: str | bytes | None) -> Any:
        """Deserialize JSON string to Python objects.

        Args:
            json_str: JSON string, bytes, or None to deserialize

        Returns:
            Python object representation of the JSON data, or None if input is None

        Raises:
            ValueError: If the deserialization fails with descriptive error message
        """
        if json_str is None:
            return None

        try:
            if isinstance(json_str, bytes):
                json_str = json_str.decode("utf-8")
            return json.loads(json_str)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.error(f"JSON deserialization failed: {e}")
            raise ValueError(f"Cannot deserialize JSON: {e}") from e

    @staticmethod
    def is_serializable(data: Any) -> bool:
        """Check if data can be JSON serialized.

        Args:
            data: The data to test for JSON serializability

        Returns:
            True if the data can be serialized, False otherwise
        """
        try:
            JSONHandler.serialize(data)
            return True
        except (TypeError, ValueError):
            return False
