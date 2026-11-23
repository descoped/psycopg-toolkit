"""What DatabaseSettings.enable_json_adapters does, pinned against a real server (review finding M2).

psycopg decodes json/jsonb to Python objects on its own. The setting only decides whether each
connection the toolkit hands out is reset to the standard-library loads/dumps, which overrides
any loader registered globally with psycopg.types.json.set_json_loads.
"""

import json
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any

import pytest
from psycopg.types.json import set_json_loads

from psycopg_toolkit import Database, DatabaseSettings


def settings_with(base: DatabaseSettings, enable_json_adapters: bool) -> DatabaseSettings:
    return replace(base, enable_json_adapters=enable_json_adapters)


@asynccontextmanager
async def database(settings: DatabaseSettings) -> AsyncGenerator[Database, None]:
    db = Database(settings)
    try:
        yield db
    finally:
        await db.cleanup()


@pytest.fixture
def global_loads() -> Any:
    """Register a marking jsonb loader globally for one test, then restore psycopg's default."""

    def install(loads: Callable[[str | bytes], Any]) -> None:
        set_json_loads(loads)

    yield install
    set_json_loads(json.loads)


def marking_loads(data: str | bytes) -> Any:
    return {"marked": json.loads(data)}


async def fetch_jsonb(db: Database, via: str) -> Any:
    ctx = db.connection() if via == "connection" else db.transaction()
    async with ctx as conn:
        cur = await conn.execute("""SELECT '{"a": 1}'::jsonb""")
        row = await cur.fetchone()
        assert row is not None
        return row[0]


@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("via", ["connection", "transaction"])
async def test_jsonb_is_decoded_either_way(test_settings: DatabaseSettings, enabled: bool, via: str) -> None:
    async with database(settings_with(test_settings, enabled)) as db:
        assert await fetch_jsonb(db, via) == {"a": 1}


@pytest.mark.parametrize("via", ["connection", "transaction"])
async def test_enabled_overrides_a_global_loader(test_settings: DatabaseSettings, global_loads: Any, via: str) -> None:
    global_loads(marking_loads)
    async with database(settings_with(test_settings, True)) as db:
        assert await fetch_jsonb(db, via) == {"a": 1}


@pytest.mark.parametrize("via", ["connection", "transaction"])
async def test_disabled_keeps_a_global_loader(test_settings: DatabaseSettings, global_loads: Any, via: str) -> None:
    global_loads(marking_loads)
    async with database(settings_with(test_settings, False)) as db:
        assert await fetch_jsonb(db, via) == {"marked": {"a": 1}}


async def test_transaction_manager_follows_the_setting(test_settings: DatabaseSettings, global_loads: Any) -> None:
    global_loads(marking_loads)
    for enabled, expected in [(True, {"a": 1}), (False, {"marked": {"a": 1}})]:
        async with database(settings_with(test_settings, enabled)) as db:
            tm = await db.get_transaction_manager()
            async with tm.transaction() as conn:
                cur = await conn.execute("""SELECT '{"a": 1}'::jsonb""")
                row = await cur.fetchone()
                assert row is not None
                assert row[0] == expected
