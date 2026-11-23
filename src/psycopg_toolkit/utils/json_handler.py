"""JSON handling utilities for JSONB field support."""

import json
import logging
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Literal, cast, get_args
from uuid import UUID

logger = logging.getLogger(__name__)

DecimalMode = Literal["float", "str"]
"""How Decimal values are written to JSON: ``"float"`` (default, may lose digits) or ``"str"`` (lossless)."""


def check_decimal_mode(decimal_as: str) -> DecimalMode:
    """Return ``decimal_as`` if it is a valid DecimalMode, else raise ValueError."""
    if decimal_as not in get_args(DecimalMode):
        raise ValueError(f"decimal_as must be one of {get_args(DecimalMode)}, got {decimal_as!r}")
    return cast("DecimalMode", decimal_as)


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for common Python types.

    Handles serialization of UUID, datetime, date, time, Decimal, set, frozenset, and Pydantic models
    that are commonly used in applications but not natively JSON serializable.

    Decimal is written as a float by default, which can lose digits (JSON numbers decode to float).
    Pass ``decimal_as="str"`` to write it as a string that keeps every digit, e.g.
    ``json.dumps(data, cls=CustomJSONEncoder, decimal_as="str")``.
    """

    def __init__(self, *args: Any, decimal_as: DecimalMode = "float", **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.decimal_as = check_decimal_mode(decimal_as)

    # The parameter keeps its public name `obj` (the base class calls it `o`); renaming it would
    # break callers that pass it by keyword.
    def default(self, obj: Any) -> Any:  # pyright: ignore[reportIncompatibleMethodOverride]
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
            return str(obj) if self.decimal_as == "str" else float(obj)
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
    def serialize(data: Any, *, decimal_as: DecimalMode = "float") -> str:
        """Serialize Python objects to JSON string.

        Args:
            data: The Python object to serialize
            decimal_as: How to write Decimal values: ``"float"`` (default) or ``"str"`` (lossless)

        Returns:
            JSON string representation of the data

        Raises:
            ValueError: If the serialization fails with descriptive error message
        """
        try:
            return json.dumps(data, cls=CustomJSONEncoder, ensure_ascii=False, allow_nan=False, decimal_as=decimal_as)
        except (TypeError, ValueError, OverflowError) as e:
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
