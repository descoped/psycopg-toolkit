"""Custom per-field codecs (review finding M7c): field_codecs replaces a field's built-in handling."""

from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from psycopg_toolkit import BaseRepository, FieldCodec


class Money(BaseModel):
    id: int
    amount: Decimal
    meta: dict[str, Any]


class CentsCodec:
    """Stores Decimal amounts as integer cents."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, Any]] = []

    def encode(self, field_name: str, value: Any) -> Any:
        self.calls.append(("encode", field_name, value))
        return int(value * 100)

    def decode(self, field_name: str, value: Any) -> Any:
        self.calls.append(("decode", field_name, value))
        return Decimal(value) / 100


def test_satisfies_the_protocol() -> None:
    assert isinstance(CentsCodec(), FieldCodec)


def test_custom_codec_encodes_and_decodes() -> None:
    codec = CentsCodec()
    repo = BaseRepository(MagicMock(), "money", Money, field_codecs={"amount": codec})
    assert repo._preprocess_data({"id": 1, "amount": Decimal("12.34"), "meta": {}}) == {
        "id": 1,
        "amount": 1234,
        "meta": "{}",
    }
    assert repo.row_to_model({"id": 1, "amount": 1234, "meta": {}}) == Money(id=1, amount=Decimal("12.34"), meta={})
    assert codec.calls == [("encode", "amount", Decimal("12.34")), ("decode", "amount", 1234)]


def test_none_is_not_passed_to_the_codec() -> None:
    codec = CentsCodec()
    repo = BaseRepository(MagicMock(), "money", Money, field_codecs={"amount": codec})
    assert repo._preprocess_data({"amount": None}) == {"amount": None}
    assert repo._postprocess_data({"amount": None}) == {"amount": None}
    assert codec.calls == []


def test_custom_codec_replaces_builtin_json_handling() -> None:
    class Upper:
        def encode(self, field_name: str, value: Any) -> Any:
            return {k.upper(): v for k, v in value.items()}

        def decode(self, field_name: str, value: Any) -> Any:
            return {k.lower(): v for k, v in value.items()}

    repo = BaseRepository(MagicMock(), "money", Money, field_codecs={"meta": Upper()})
    # meta is auto-detected as JSON, but the custom codec runs instead of serialization
    assert "meta" in repo.json_fields
    assert repo._preprocess_data({"meta": {"a": 1}}) == {"meta": {"A": 1}}
    assert repo._postprocess_data({"meta": {"A": 1}}) == {"meta": {"a": 1}}


def test_custom_codec_field_is_not_wrapped_in_adapter_mode() -> None:
    class Identity:
        def encode(self, field_name: str, value: Any) -> Any:
            return value

        def decode(self, field_name: str, value: Any) -> Any:
            return value

    repo = BaseRepository(MagicMock(), "money", Money, auto_detect_json=False, field_codecs={"meta": Identity()})
    out = repo._preprocess_data({"meta": {"a": 1}})
    assert out == {"meta": {"a": 1}}
    assert type(out["meta"]) is dict


@pytest.mark.parametrize("field", ["amount", "unknown_column"])
def test_any_field_name_is_accepted(field: str) -> None:
    repo = BaseRepository(MagicMock(), "money", Money, field_codecs={field: CentsCodec()})
    assert repo._preprocess_data({field: Decimal("1")})[field] == 100


def test_adapter_mode_still_converts_date_fields() -> None:
    """Regression guard: in Json()-wrapping mode, date fields are converted and dict/list wrapped."""
    from datetime import datetime

    from psycopg.types.json import Json

    class Event(BaseModel):
        id: int
        at: str
        data: dict[str, Any]
        tags: list[str]

    repo = BaseRepository(
        MagicMock(), "events", Event, auto_detect_json=False, date_fields={"at"}, array_fields={"tags"}
    )
    out = repo._preprocess_data({"id": 1, "at": datetime(2020, 1, 2, 3, 4, 5), "data": {"a": 1}, "tags": ["x"]})
    assert out["at"] == "2020-01-02T03:04:05"
    assert isinstance(out["data"], Json) and out["data"].obj == {"a": 1}
    assert out["tags"] == ["x"]


class TestBuiltinCodecs:
    """Branches of the built-in codecs that the repository-level tests do not reach."""

    def test_vector_codec(self, caplog: pytest.LogCaptureFixture) -> None:
        import logging

        from psycopg_toolkit.repositories.codecs import VectorCodec

        codec = VectorCodec("t")
        caplog.set_level(logging.DEBUG, logger="psycopg_toolkit")
        assert codec.encode("v", [0.1]) == [0.1]
        assert codec.decode("v", [0.1, 0.2]) == [0.1, 0.2]  # already a list
        assert codec.decode("v", "[0.1, 0.2]") == [0.1, 0.2]
        assert codec.decode("v", "not json") == "not json"
        assert codec.decode("v", '{"a": 1}') == '{"a": 1}'
        messages = [r.getMessage() for r in caplog.records]
        assert "Parsed vector field 'v' from string to list[float] for t" in messages
        assert any(
            m.startswith("Failed to parse vector field 'v' in t:") and m.endswith("Keeping as string.")
            for m in messages
        )
        assert "Vector field 'v' parsed to dict instead of list for t" in messages
        assert {r.name for r in caplog.records} == {"psycopg_toolkit.repositories.base"}

    def test_psycopg_json_codec(self) -> None:
        from psycopg.types.json import Json

        from psycopg_toolkit.repositories.codecs import PsycopgJsonCodec

        codec = PsycopgJsonCodec()
        wrapped = codec.encode("f", {"a": 1})
        assert isinstance(wrapped, Json) and wrapped.obj == {"a": 1}
        assert codec.encode("f", "text") == "text"
        assert codec.decode("f", {"a": 1}) == {"a": 1}
