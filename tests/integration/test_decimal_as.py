"""decimal_as="str" keeps Decimal precision through a real JSONB round trip (review finding M4)."""

from decimal import Decimal
from typing import Any

from psycopg import AsyncConnection
from pydantic import BaseModel

from psycopg_toolkit import BaseRepository

PRECISE = Decimal("123.456789012345678901")


class Priced(BaseModel):
    id: int
    meta: dict[str, Any]


async def make_table(conn: AsyncConnection) -> None:
    await conn.execute("CREATE TEMP TABLE priced (id int PRIMARY KEY, meta jsonb NOT NULL) ON COMMIT DROP")


async def test_default_float_loses_digits(jsonb_tables: AsyncConnection) -> None:
    await make_table(jsonb_tables)
    repo = BaseRepository(jsonb_tables, "priced", Priced)
    await repo.create(Priced(id=1, meta={"p": PRECISE}))
    got = await repo.get_by_id(1)
    assert got.meta["p"] == float(PRECISE)
    assert Decimal(str(got.meta["p"])) != PRECISE


async def test_str_mode_keeps_every_digit(jsonb_tables: AsyncConnection) -> None:
    await make_table(jsonb_tables)
    repo = BaseRepository(jsonb_tables, "priced", Priced, decimal_as="str")
    created = await repo.create(Priced(id=1, meta={"p": PRECISE, "q": Decimal("1.10")}))
    got = await repo.get_by_id(1)
    assert created.meta == got.meta == {"p": "123.456789012345678901", "q": "1.10"}
    assert Decimal(got.meta["p"]) == PRECISE

    updated = await repo.update(1, {"meta": {"p": Decimal("0.000000000000000000001")}})
    assert updated.meta == {"p": "1E-21"}
    rows = await repo.create_bulk([Priced(id=2, meta={"p": PRECISE})])
    assert rows[0].meta == {"p": "123.456789012345678901"}
