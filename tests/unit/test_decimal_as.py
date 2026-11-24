"""Decimal serialization mode for JSON fields (review finding M4).

The default is ``"str"`` (since 0.5.0): every digit is kept by writing the Decimal as a JSON string.
``decimal_as="float"`` opts back into the previous, lossy float output.
"""

import json
from decimal import Decimal
from typing import Any

import pytest
from pydantic import BaseModel

from psycopg_toolkit import BaseRepository
from psycopg_toolkit.utils.json_handler import CustomJSONEncoder, JSONHandler

PRECISE = Decimal("123.456789012345678901")


class Priced(BaseModel):
    id: int
    meta: dict[str, Any]


class TestDefaultIsStr:
    def test_encoder_default_is_str(self) -> None:
        assert json.loads(json.dumps({"p": PRECISE}, cls=CustomJSONEncoder)) == {"p": "123.456789012345678901"}

    def test_handler_default_is_str(self) -> None:
        assert JSONHandler.serialize({"p": PRECISE}) == '{"p": "123.456789012345678901"}'

    def test_repository_default_is_str(self) -> None:
        repo = BaseRepository(None, "t", Priced)  # type: ignore[arg-type]
        assert repo._preprocess_data({"meta": {"p": Decimal("1.10")}})["meta"] == '{"p": "1.10"}'


class TestDecimalAsFloat:
    def test_encoder_float_is_lossy(self) -> None:
        out = json.dumps({"p": PRECISE}, cls=CustomJSONEncoder, decimal_as="float")
        assert json.loads(out) == {"p": float(PRECISE)}

    def test_handler_float(self) -> None:
        assert JSONHandler.serialize({"p": PRECISE}, decimal_as="float") == '{"p": 123.45678901234568}'

    def test_repository_float(self) -> None:
        repo = BaseRepository(None, "t", Priced, decimal_as="float")  # type: ignore[arg-type]
        assert repo._preprocess_data({"meta": {"p": Decimal("1.10")}})["meta"] == '{"p": 1.1}'


class TestDecimalAsStr:
    def test_encoder_str_keeps_digits(self) -> None:
        out = json.dumps({"p": PRECISE, "z": Decimal("1.10")}, cls=CustomJSONEncoder, decimal_as="str")
        assert json.loads(out) == {"p": "123.456789012345678901", "z": "1.10"}

    def test_handler_str_keeps_digits(self) -> None:
        assert JSONHandler.serialize([PRECISE], decimal_as="str") == '["123.456789012345678901"]'

    def test_handler_str_round_trips_through_decimal(self) -> None:
        back = JSONHandler.deserialize(JSONHandler.serialize({"p": PRECISE}, decimal_as="str"))
        assert Decimal(back["p"]) == PRECISE

    def test_other_types_unaffected(self) -> None:
        out = JSONHandler.serialize({"s": {1}, "n": 1.5}, decimal_as="str")
        assert json.loads(out) == {"s": [1], "n": 1.5}

    def test_repository_str(self) -> None:
        repo = BaseRepository(None, "t", Priced, decimal_as="str")  # type: ignore[arg-type]
        assert repo._preprocess_data({"meta": {"p": Decimal("1.10")}})["meta"] == '{"p": "1.10"}'

    def test_repository_str_non_container_value(self) -> None:
        repo = BaseRepository(None, "t", Priced, json_fields={"meta"}, decimal_as="str")  # type: ignore[arg-type]
        assert repo._preprocess_data({"meta": Decimal("2.50")})["meta"] == '"2.50"'


class TestInvalidMode:
    def test_encoder_rejects_unknown_mode(self) -> None:
        with pytest.raises(ValueError, match="decimal_as"):
            CustomJSONEncoder(decimal_as="int")  # type: ignore[arg-type]

    def test_repository_rejects_unknown_mode(self) -> None:
        with pytest.raises(ValueError, match="decimal_as"):
            BaseRepository(None, "t", Priced, decimal_as="int")  # type: ignore[arg-type]
