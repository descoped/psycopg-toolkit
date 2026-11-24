"""Per-field conversion between model values and database values.

A ``FieldCodec`` converts one field's value on the way to the database (``encode``) and on the way
back (``decode``). ``BaseRepository`` plans, once per repository, which codecs apply to which field
(date, vector, JSON) and runs them in that order. Pass ``field_codecs`` to ``BaseRepository`` to
replace the built-in handling of a field with your own codec.
"""

import logging
from datetime import date, datetime
from typing import Any, Protocol, runtime_checkable

from psycopg.types.json import Json

from ..exceptions import JSONDeserializationError, JSONSerializationError
from ..utils.json_handler import DecimalMode, JSONHandler

# The repository's logger, so existing logging configuration for
# "psycopg_toolkit.repositories.base" keeps covering field conversion messages.
logger = logging.getLogger("psycopg_toolkit.repositories.base")


@runtime_checkable
class FieldCodec(Protocol):
    """Converts one field's value to and from its database representation.

    Neither method is called for ``None``: a missing or NULL value passes through unchanged.
    """

    def encode(self, field_name: str, value: Any) -> Any:
        """Convert a model value into the value sent to the database."""
        ...

    def decode(self, field_name: str, value: Any) -> Any:
        """Convert a value read from the database into the model value."""
        ...


class DateCodec:
    """date/datetime to ISO strings, in both directions (for models that type these fields as str)."""

    def __init__(self, table_name: str) -> None:
        self.table_name = table_name

    def _to_iso(self, field_name: str, value: Any) -> Any:
        if isinstance(value, date | datetime):
            logger.debug(
                "Converted date field '%s' from %s to ISO string for %s",
                field_name,
                type(value).__name__,
                self.table_name,
            )
            return value.isoformat()
        return value

    def encode(self, field_name: str, value: Any) -> Any:
        return self._to_iso(field_name, value)

    def decode(self, field_name: str, value: Any) -> Any:
        return self._to_iso(field_name, value)


class VectorCodec:
    """pgvector columns: the text form ``'[0.1,0.2]'`` is parsed to ``list[float]`` on read."""

    def __init__(self, table_name: str) -> None:
        self.table_name = table_name

    def encode(self, field_name: str, value: Any) -> Any:
        return value

    def decode(self, field_name: str, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        try:
            parsed = JSONHandler.deserialize(value)
        except Exception as e:
            logger.warning(
                "Failed to parse vector field '%s' in %s: %s. Keeping as string.", field_name, self.table_name, e
            )
            return value
        if isinstance(parsed, list):
            logger.debug("Parsed vector field '%s' from string to list[float] for %s", field_name, self.table_name)
            return parsed
        logger.warning(
            "Vector field '%s' parsed to %s instead of list for %s",
            field_name,
            type(parsed).__name__,
            self.table_name,
        )
        return value


class JsonCodec:
    """The toolkit's own JSON processing: serialize to a JSON string on write, decode on read.

    Args:
        table_name: Used in log messages.
        decimal_as: How Decimal values are written.
        strict: Raise JSONDeserializationError on undecodable values instead of keeping them.
        accepts_str: The field's type admits a plain ``str``. Then a ``str`` is a JSON string value:
            serialized on write and not decoded again on read. Otherwise a ``str`` is an
            already-serialized JSON document.
    """

    def __init__(self, table_name: str, *, decimal_as: DecimalMode, strict: bool, accepts_str: bool) -> None:
        self.table_name = table_name
        self.decimal_as: DecimalMode = decimal_as
        self.strict = strict
        self.accepts_str = accepts_str

    def _serialize(self, field_name: str, value: Any) -> str:
        try:
            return JSONHandler.serialize(value, decimal_as=self.decimal_as)
        except Exception as e:
            raise JSONSerializationError(
                f"JSON serialization failed for field '{field_name}': {e}",
                field_name=field_name,
                value=value,
                original_error=e,
            ) from e

    def encode(self, field_name: str, value: Any) -> Any:
        if isinstance(value, dict | list):
            serialized = self._serialize(field_name, value)
            logger.debug("Serialized JSON field '%s' for %s", field_name, self.table_name)
            return serialized
        if not isinstance(value, str) or self.accepts_str:
            serialized = self._serialize(field_name, value)
            logger.debug("Serialized non-standard JSON field '%s' for %s", field_name, self.table_name)
            return serialized
        return value

    def decode(self, field_name: str, value: Any) -> Any:
        if not isinstance(value, str | bytes):
            # psycopg decodes json/jsonb columns itself, so anything else is already decoded
            return value
        if isinstance(value, str) and self.accepts_str:
            # A JSON string value psycopg has already decoded; decoding it again would turn
            # "123" into 123 or fail on "hello".
            return value
        try:
            decoded = JSONHandler.deserialize(value)
        except Exception as e:
            if self.strict:
                raise JSONDeserializationError(
                    f"JSON deserialization failed for field '{field_name}': {e}",
                    field_name=field_name,
                    json_data=str(value),
                    original_error=e,
                ) from e
            logger.warning("Failed to deserialize JSON field '%s' in %s: %s", field_name, self.table_name, e)
            # Keep the original value to prevent data loss
            logger.warning("Keeping original value for field '%s' in %s", field_name, self.table_name)
            return value
        logger.debug("Deserialized JSON field '%s' for %s", field_name, self.table_name)
        return decoded


class PsycopgJsonCodec:
    """psycopg adapter mode (``auto_detect_json=False``, no ``json_fields``): wrap dict/list in ``Json()``.

    Applied to every field that is not an array field; reads are left to psycopg's own decoding.
    """

    def encode(self, field_name: str, value: Any) -> Any:
        if isinstance(value, dict | list):
            logger.debug("Wrapped field '%s' with Json() for PostgreSQL JSONB handling", field_name)
            return Json(value)
        return value

    def decode(self, field_name: str, value: Any) -> Any:
        return value
