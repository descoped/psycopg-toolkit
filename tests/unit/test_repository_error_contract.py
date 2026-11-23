"""Error and logging contract of BaseRepository's CRUD methods.

TestErrorContract pins the exception type, message and cause each method produces today; it must
keep passing across refactors. TestLogging describes the intended logging behaviour.
"""

import logging
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from psycopg import OperationalError
from pydantic import BaseModel

from psycopg_toolkit import (
    BaseRepository,
    JSONDeserializationError,
    JSONSerializationError,
    OperationError,
    RecordNotFoundError,
)


class Doc(BaseModel):
    id: int
    meta: dict[str, Any]


class NotJSON:
    pass


def make_repo(
    *,
    execute_error: Exception | None = None,
    fetchone: Any = None,
    fetchall: list[Any] | None = None,
    rowcount: int = 1,
    strict: bool = False,
) -> BaseRepository[Doc, int]:
    cursor = MagicMock()
    cursor.execute = AsyncMock(side_effect=execute_error)
    cursor.fetchone = AsyncMock(return_value=fetchone)
    cursor.fetchall = AsyncMock(return_value=fetchall or [])
    cursor.rowcount = rowcount

    @asynccontextmanager
    async def cursor_cm(*_args: Any, **_kwargs: Any):  # type: ignore[no-untyped-def]
        yield cursor

    @asynccontextmanager
    async def transaction_cm():  # type: ignore[no-untyped-def]
        yield None

    conn = MagicMock()
    conn.cursor = cursor_cm
    conn.transaction = transaction_cm
    return BaseRepository(conn, "docs", Doc, strict_json_processing=strict)


def unserializable() -> Doc:
    return Doc.model_construct(id=1, meta={"x": NotJSON()})


DB_DOWN = OperationalError("db down")

GENERIC_FAILURES = [
    ("create", lambda r: r.create(Doc(id=1, meta={})), "Failed to create record: db down"),
    ("create_bulk", lambda r: r.create_bulk([Doc(id=1, meta={})]), "Failed to create records in bulk: db down"),
    ("get_by_id", lambda r: r.get_by_id(1), "Failed to get record: db down"),
    ("get_all", lambda r: r.get_all(), "Failed to get all records: db down"),
    ("update", lambda r: r.update(1, {"meta": {}}), "Failed to update record: db down"),
    ("delete", lambda r: r.delete(1), "Failed to delete record: db down"),
    ("exists", lambda r: r.exists(1), "Failed to check record existence: db down"),
]


class TestErrorContract:
    @pytest.mark.parametrize(("name", "call", "message"), GENERIC_FAILURES, ids=[g[0] for g in GENERIC_FAILURES])
    async def test_database_errors_become_operation_error(self, name: str, call: Any, message: str) -> None:
        with pytest.raises(OperationError) as excinfo:
            await call(make_repo(execute_error=DB_DOWN))
        assert type(excinfo.value) is OperationError
        assert str(excinfo.value) == message
        assert excinfo.value.__cause__ is DB_DOWN

    @pytest.mark.parametrize(
        ("name", "call", "kwargs"),
        [
            ("get_by_id", lambda r: r.get_by_id(7), {"fetchone": None}),
            ("update", lambda r: r.update(7, {"meta": {}}), {"fetchone": None}),
            ("delete", lambda r: r.delete(7), {"rowcount": 0}),
        ],
        ids=["get_by_id", "update", "delete"],
    )
    async def test_missing_record_raises_not_found(self, name: str, call: Any, kwargs: dict[str, Any]) -> None:
        with pytest.raises(RecordNotFoundError) as excinfo:
            await call(make_repo(**kwargs))
        assert type(excinfo.value) is RecordNotFoundError
        assert str(excinfo.value) == "Record with id 7 not found"

    async def test_create_without_returned_row(self) -> None:
        with pytest.raises(OperationError) as excinfo:
            await make_repo(fetchone=None).create(Doc(id=1, meta={}))
        assert str(excinfo.value) == "Failed to create docs record"
        assert excinfo.value.__cause__ is None

    async def test_create_passes_serialization_errors_through(self) -> None:
        with pytest.raises(JSONSerializationError):
            await make_repo().create(unserializable())

    async def test_update_passes_serialization_errors_through(self) -> None:
        with pytest.raises(JSONSerializationError):
            await make_repo().update(1, {"meta": {"x": NotJSON()}})

    async def test_create_bulk_wraps_serialization_errors(self) -> None:
        """Current behaviour (review finding M6): create_bulk wraps instead of passing through."""
        with pytest.raises(OperationError) as excinfo:
            await make_repo().create_bulk([unserializable()])
        assert type(excinfo.value) is OperationError
        assert str(excinfo.value).startswith("Failed to create records in bulk: JSON serialization failed")
        assert isinstance(excinfo.value.__cause__, JSONSerializationError)

    @pytest.mark.parametrize(
        ("name", "call", "kwargs"),
        [
            ("get_by_id", lambda r: r.get_by_id(1), {"fetchone": {"id": 1, "meta": "{not json"}}),
            ("get_all", lambda r: r.get_all(), {"fetchall": [{"id": 1, "meta": "{not json"}]}),
        ],
        ids=["get_by_id", "get_all"],
    )
    async def test_strict_deserialization_errors_pass_through(
        self, name: str, call: Any, kwargs: dict[str, Any]
    ) -> None:
        with pytest.raises(JSONDeserializationError):
            await call(make_repo(strict=True, **kwargs))

    async def test_success_paths_return_models(self) -> None:
        row = {"id": 1, "meta": {"a": 1}}
        assert await make_repo(fetchone=row).get_by_id(1) == Doc(id=1, meta={"a": 1})
        assert await make_repo(fetchall=[row]).get_all() == [Doc(id=1, meta={"a": 1})]
        assert await make_repo(fetchone=row).create(Doc(id=1, meta={"a": 1})) == Doc(id=1, meta={"a": 1})
        assert await make_repo(fetchall=[row]).create_bulk([Doc(id=1, meta={"a": 1})]) == [Doc(id=1, meta={"a": 1})]
        assert await make_repo(fetchone=row).update(1, {"meta": {"a": 1}}) == Doc(id=1, meta={"a": 1})
        assert await make_repo(fetchone=(1,)).exists(1) is True
        assert await make_repo(fetchone=None).exists(1) is False
        await make_repo(rowcount=1).delete(1)


def error_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.levelno >= logging.ERROR and r.name.startswith("psycopg_toolkit")]


class TestLogging:
    async def test_missing_record_is_not_logged_as_error(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.DEBUG, logger="psycopg_toolkit")
        with pytest.raises(RecordNotFoundError):
            await make_repo(fetchone=None).get_by_id(7)
        assert error_records(caplog) == []

    async def test_serialization_failure_is_logged_once(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.DEBUG, logger="psycopg_toolkit")
        with pytest.raises(JSONSerializationError):
            await make_repo().create(unserializable())
        assert len(error_records(caplog)) == 1

    async def test_database_failure_is_logged_once(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.DEBUG, logger="psycopg_toolkit")
        with pytest.raises(OperationError):
            await make_repo(execute_error=DB_DOWN).get_all()
        assert len(error_records(caplog)) == 1


class Vec(BaseModel):
    id: int
    embedding: list[float]
    tags: list[str]


def debug_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.levelno == logging.DEBUG]


class TestDebugMessages:
    """Rendered text of the lazily formatted debug messages on configuration paths."""

    def test_explicit_vector_fields(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.DEBUG, logger="psycopg_toolkit")
        BaseRepository(MagicMock(), "vecs", Vec, vector_fields={"embedding"})
        assert "Using explicit vector fields for vecs: {'embedding'}" in debug_messages(caplog)

    def test_vector_detection_disabled(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.DEBUG, logger="psycopg_toolkit")
        BaseRepository(MagicMock(), "vecs", Vec, auto_detect_vector=False)
        assert "Vector field detection disabled for vecs" in debug_messages(caplog)

    def test_array_field_preserved(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.DEBUG, logger="psycopg_toolkit")
        repo = BaseRepository(MagicMock(), "vecs", Vec, auto_detect_json=False, array_fields={"tags"})
        assert repo._preprocess_data({"tags": ["a"]}) == {"tags": ["a"]}
        assert "Preserving array field 'tags' for PostgreSQL array handling" in debug_messages(caplog)

    def test_non_container_json_value(self, caplog: pytest.LogCaptureFixture) -> None:
        caplog.set_level(logging.DEBUG, logger="psycopg_toolkit")
        repo = BaseRepository(MagicMock(), "docs", Doc, json_fields={"meta"})
        assert repo._preprocess_data({"meta": 5}) == {"meta": "5"}
        assert "Serialized non-standard JSON field 'meta' for docs" in debug_messages(caplog)
