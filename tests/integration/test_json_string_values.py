"""str values in JSON fields round-trip as JSON strings when the field accepts str.

Fields typed only as dict/list keep treating a str as already-serialized JSON (for example a
JSON document passed to update()), which is pinned here too.
"""

from typing import Any

import pytest
from psycopg import AsyncConnection
from pydantic import BaseModel

from psycopg_toolkit import BaseRepository


class Flexible(BaseModel):
    id: int
    payload: dict[str, Any] | str


class Strict(BaseModel):
    id: int
    payload: dict[str, Any]


async def make_table(conn: AsyncConnection) -> None:
    await conn.execute("CREATE TEMP TABLE docs (id int PRIMARY KEY, payload jsonb NOT NULL) ON COMMIT DROP")


async def stored(conn: AsyncConnection) -> str:
    row = await (await conn.execute("SELECT payload::text FROM docs WHERE id = 1")).fetchone()
    assert row is not None
    return str(row[0])


@pytest.mark.parametrize("text", ["hello", "123", '{"a": 1}', "", "null"])
async def test_str_round_trips_when_field_accepts_str(jsonb_tables: AsyncConnection, text: str) -> None:
    await make_table(jsonb_tables)
    repo = BaseRepository(jsonb_tables, "docs", Flexible)
    created = await repo.create(Flexible(id=1, payload=text))
    assert created.payload == text
    assert (await repo.get_by_id(1)).payload == text
    assert (await repo.get_all())[0].payload == text


@pytest.mark.parametrize("text", ["hello", "123"])
async def test_str_round_trips_in_strict_mode(jsonb_tables: AsyncConnection, text: str) -> None:
    await make_table(jsonb_tables)
    repo = BaseRepository(jsonb_tables, "docs", Flexible, strict_json_processing=True)
    await repo.create(Flexible(id=1, payload=text))
    assert (await repo.get_by_id(1)).payload == text


async def test_str_update_when_field_accepts_str(jsonb_tables: AsyncConnection) -> None:
    await make_table(jsonb_tables)
    repo = BaseRepository(jsonb_tables, "docs", Flexible)
    await repo.create(Flexible(id=1, payload={"a": 1}))
    updated = await repo.update(1, {"payload": "42"})
    assert updated.payload == "42"
    assert await stored(jsonb_tables) == '"42"'


async def test_dict_still_works_when_field_accepts_str(jsonb_tables: AsyncConnection) -> None:
    await make_table(jsonb_tables)
    repo = BaseRepository(jsonb_tables, "docs", Flexible)
    await repo.create(Flexible(id=1, payload={"a": 1}))
    assert (await repo.get_by_id(1)).payload == {"a": 1}
    assert await stored(jsonb_tables) == '{"a": 1}'


async def test_dict_only_field_treats_str_as_serialized_json(jsonb_tables: AsyncConnection) -> None:
    """Unchanged behaviour: a JSON document passed as str to a dict-only field is stored as that document."""
    await make_table(jsonb_tables)
    repo = BaseRepository(jsonb_tables, "docs", Strict)
    await repo.create(Strict(id=1, payload={"a": 1}))
    updated = await repo.update(1, {"payload": '{"b": 2}'})
    assert updated.payload == {"b": 2}
    assert await stored(jsonb_tables) == '{"b": 2}'
