"""BaseRepository.row_to_model(): the public way to turn a fetched row into the model."""

from collections.abc import Mapping
from datetime import date
from typing import Any

import pytest
from psycopg.rows import DictRow
from pydantic import BaseModel, ValidationError

from psycopg_toolkit import BaseRepository, JSONDeserializationError


class Item(BaseModel):
    id: int
    meta: dict[str, Any]
    tags: list[str]
    born: str | None = None
    embedding: list[float] | None = None


def repo(**kw: Any) -> BaseRepository[Item, int]:
    return BaseRepository(None, "items", Item, date_fields={"born"}, **kw)  # type: ignore[arg-type]


ROWS: list[Mapping[str, Any]] = [
    {"id": 1, "meta": {"a": 1}, "tags": ["x"], "born": date(2000, 1, 2), "embedding": "[0.5, 1.5]"},
    {"id": 2, "meta": '{"b": 2}', "tags": '["y"]', "born": None, "embedding": None},
]


@pytest.mark.parametrize("row", ROWS, ids=["decoded", "encoded"])
def test_same_result_as_the_private_pattern(row: Mapping[str, Any]) -> None:
    r = repo()
    assert r.row_to_model(row) == Item(**r._postprocess_data(dict(row)))


def test_converts_fields() -> None:
    got = repo().row_to_model(ROWS[0])
    assert got == Item(id=1, meta={"a": 1}, tags=["x"], born="2000-01-02", embedding=[0.5, 1.5])


def test_accepts_a_psycopg_dict_row() -> None:
    row = DictRow(ROWS[1])
    assert repo().row_to_model(row) == Item(id=2, meta={"b": 2}, tags=["y"])


def test_does_not_mutate_the_row() -> None:
    row = dict(ROWS[1])
    repo().row_to_model(row)
    assert row == ROWS[1]


def test_strict_decoding_error_propagates() -> None:
    with pytest.raises(JSONDeserializationError):
        repo(strict_json_processing=True).row_to_model({"id": 1, "meta": "{bad", "tags": []})


def test_validation_error_propagates() -> None:
    with pytest.raises(ValidationError):
        repo().row_to_model({"id": "not-an-int", "meta": {}, "tags": []})
