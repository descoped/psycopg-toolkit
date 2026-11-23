"""Regression tests for TransactionManager schema/data lifecycles."""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from psycopg import AsyncConnection, errors, sql

from psycopg_toolkit import Database, DatabaseConnectionError, DatabaseSettings, TransactionManager
from psycopg_toolkit.core.transaction import DataManager, SchemaManager


def _causes(exc: BaseException) -> list[type[BaseException]]:
    chain: list[type[BaseException]] = []
    current: BaseException | None = exc
    while current is not None:
        chain.append(type(current))
        current = current.__cause__ or current.__context__
    return chain


class TableSchema(SchemaManager[str]):
    def __init__(self, table: str) -> None:
        self.table = table
        self.dropped = False

    async def create_schema(self, conn: AsyncConnection) -> str:
        await conn.execute(sql.SQL("CREATE TABLE {} (id int PRIMARY KEY)").format(sql.Identifier(self.table)))
        return self.table

    async def drop_schema(self, conn: AsyncConnection) -> None:
        self.dropped = True
        await conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(self.table)))


class RowData(DataManager[list[int]]):
    def __init__(self, table: str) -> None:
        self.table = table
        self.cleaned = False

    async def setup_data(self, conn: AsyncConnection) -> list[int]:
        await conn.execute(sql.SQL("INSERT INTO {} VALUES (1), (2)").format(sql.Identifier(self.table)))
        return [1, 2]

    async def cleanup_data(self, conn: AsyncConnection) -> None:
        self.cleaned = True
        await conn.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier(self.table)))


@pytest.fixture
async def database(test_settings: DatabaseSettings) -> AsyncGenerator[Database, None]:
    db = Database(test_settings)
    yield db
    await db.cleanup()


@pytest.fixture
async def tm(database: Database) -> TransactionManager:
    return TransactionManager(await database.get_pool())


@pytest.fixture
def table() -> str:
    return f"mt_{uuid4().hex[:10]}"


@pytest.fixture
async def existing_table(tm: TransactionManager, table: str) -> AsyncGenerator[str, None]:
    async with tm.transaction() as conn:
        await conn.execute(sql.SQL("CREATE TABLE {} (id int PRIMARY KEY)").format(sql.Identifier(table)))
    yield table
    async with tm.transaction() as conn:
        await conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table)))


async def _rows(tm: TransactionManager, table: str) -> list[int] | None:
    async with tm.transaction() as conn:
        if (await (await conn.execute("SELECT to_regclass(%s)", [table])).fetchone()) == (None,):
            return None
        cur = await conn.execute(sql.SQL("SELECT id FROM {} ORDER BY id").format(sql.Identifier(table)))
        return [r[0] for r in await cur.fetchall()]


async def _drop(tm: TransactionManager, table: str) -> None:
    async with tm.transaction() as conn:
        await conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table)))


class TestManagedTransaction:
    async def test_schema_and_data_visible_in_body(self, tm: TransactionManager, table: str) -> None:
        data = RowData(table)
        try:
            async with tm.managed_transaction(TableSchema(table), data) as conn:
                cur = await conn.execute(sql.SQL("SELECT id FROM {} ORDER BY id").format(sql.Identifier(table)))
                assert [r[0] for r in await cur.fetchall()] == [1, 2]
            # Same end state the separate helpers produce: schema kept, data cleaned up
            assert data.cleaned
            assert await _rows(tm, table) == []
        finally:
            await _drop(tm, table)

    async def test_schema_only_visible_in_body(self, tm: TransactionManager, table: str) -> None:
        try:
            async with tm.managed_transaction(schema_manager=TableSchema(table)) as conn:
                await conn.execute(sql.SQL("INSERT INTO {} VALUES (7)").format(sql.Identifier(table)))
            assert await _rows(tm, table) == [7]
        finally:
            await _drop(tm, table)

    async def test_data_only_visible_in_body(self, tm: TransactionManager, existing_table: str) -> None:
        data = RowData(existing_table)
        async with tm.managed_transaction(data_manager=data) as conn:
            cur = await conn.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(existing_table)))
            assert (await cur.fetchone()) == (2,)
        assert data.cleaned
        assert await _rows(tm, existing_table) == []

    async def test_no_managers_is_a_plain_transaction(self, tm: TransactionManager, existing_table: str) -> None:
        """Characterization: without managers it behaves like transaction()."""
        async with tm.managed_transaction() as conn:
            await conn.execute(sql.SQL("INSERT INTO {} VALUES (3)").format(sql.Identifier(existing_table)))
        assert await _rows(tm, existing_table) == [3]

    async def test_error_in_body_rolls_everything_back(self, tm: TransactionManager, table: str) -> None:
        with pytest.raises(DatabaseConnectionError) as excinfo:
            async with tm.managed_transaction(TableSchema(table), RowData(table)):
                raise ValueError("boom")
        assert ValueError in _causes(excinfo.value)
        assert await _rows(tm, table) is None  # schema creation rolled back too


class TestStandaloneHelpers:
    """Characterization of with_schema / with_test_data used on their own."""

    async def test_with_schema_keeps_schema_on_success(self, tm: TransactionManager, table: str) -> None:
        try:
            async with tm.with_schema(TableSchema(table)) as created:
                assert created == table
            assert await _rows(tm, table) == []
        finally:
            await _drop(tm, table)

    async def test_with_test_data_cleans_up_after_success(self, tm: TransactionManager, existing_table: str) -> None:
        data = RowData(existing_table)
        async with tm.with_test_data(data) as ids:
            assert ids == [1, 2]
        assert data.cleaned
        assert await _rows(tm, existing_table) == []

    async def test_with_test_data_runs_cleanup_after_python_error(
        self, tm: TransactionManager, existing_table: str
    ) -> None:
        data = RowData(existing_table)
        with pytest.raises(DatabaseConnectionError) as excinfo:
            async with tm.with_test_data(data):
                raise ValueError("boom")
        assert data.cleaned
        assert ValueError in _causes(excinfo.value)

    async def test_failed_setup_keeps_the_original_database_error(self, tm: TransactionManager) -> None:
        """A failing setup statement aborts the transaction; cleanup must not replace the real error."""
        data = RowData(f"missing_{uuid4().hex[:8]}")  # table does not exist -> UndefinedTable
        with pytest.raises(DatabaseConnectionError) as excinfo:
            async with tm.with_test_data(data):
                pass
        causes = _causes(excinfo.value)
        assert errors.UndefinedTable in causes
        assert errors.InFailedSqlTransaction not in causes

    async def test_managed_failed_setup_keeps_the_original_database_error(self, tm: TransactionManager) -> None:
        data = RowData(f"missing_{uuid4().hex[:8]}")
        with pytest.raises(DatabaseConnectionError) as excinfo:
            async with tm.managed_transaction(data_manager=data):
                pass
        causes = _causes(excinfo.value)
        assert errors.UndefinedTable in causes
        assert errors.InFailedSqlTransaction not in causes
