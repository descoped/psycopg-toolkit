"""Regression tests for the Database pool lifecycle and per-connection settings."""

import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import patch

import pytest
from psycopg import AsyncConnection, OperationalError

from psycopg_toolkit import Database, DatabaseConnectionError, DatabasePoolError, DatabaseSettings


def _settings(base: DatabaseSettings, **overrides: object) -> DatabaseSettings:
    values = {
        "host": base.host,
        "port": base.port,
        "dbname": base.dbname,
        "user": base.user,
        "password": base.password,
        "min_pool_size": 1,
        "max_pool_size": 2,
    }
    values.update(overrides)
    return DatabaseSettings(**values)  # type: ignore[arg-type]


async def _show_timeout(conn: AsyncConnection) -> str:
    row = await (await conn.execute("SHOW statement_timeout")).fetchone()
    assert row is not None
    return str(row[0])


@pytest.fixture
async def timeout_db(test_settings: DatabaseSettings) -> AsyncGenerator[Database, None]:
    db = Database(_settings(test_settings, statement_timeout=5))
    yield db
    await db.cleanup()


@pytest.fixture
async def plain_db(test_settings: DatabaseSettings) -> AsyncGenerator[Database, None]:
    db = Database(_settings(test_settings))
    yield db
    await db.cleanup()


class TestPoolCreation:
    async def test_concurrent_get_pool_creates_one_pool(self, plain_db: Database) -> None:
        created = []
        original = Database.create_pool

        async def counting(self: Database):  # type: ignore[no-untyped-def]
            pool = await original(self)
            created.append(pool)
            return pool

        with patch.object(Database, "create_pool", counting):
            pools = await asyncio.gather(*(plain_db.get_pool() for _ in range(5)))

        try:
            assert len(created) == 1
            assert all(p is pools[0] for p in pools)
        finally:
            for extra in created[1:]:
                await extra.close()

    async def test_get_pool_reuses_and_recreates_after_cleanup(self, plain_db: Database) -> None:
        """Characterization: an open pool is reused; after cleanup a new one is created."""
        first = await plain_db.get_pool()
        assert await plain_db.get_pool() is first
        await plain_db.cleanup()
        second = await plain_db.get_pool()
        assert second is not first
        assert not second.closed


class TestStatementTimeoutScope:
    async def test_applies_in_database_connection(self, timeout_db: Database) -> None:
        async with timeout_db.connection() as conn:
            assert await _show_timeout(conn) == "5s"

    async def test_applies_in_database_transaction(self, timeout_db: Database) -> None:
        async with timeout_db.transaction() as conn:
            assert await _show_timeout(conn) == "5s"

    async def test_applies_in_transaction_manager(self, timeout_db: Database) -> None:
        tm = await timeout_db.get_transaction_manager()
        async with tm.transaction() as conn:
            assert await _show_timeout(conn) == "5s"

    async def test_applies_on_every_pooled_connection(self, timeout_db: Database) -> None:
        """Both pool connections get the timeout, not just the one that went through connection()."""

        async def check() -> str:
            async with timeout_db.transaction() as conn:
                value = await _show_timeout(conn)
                await asyncio.sleep(0.05)  # hold the connection so the other task gets the second one
                return value

        assert await asyncio.gather(check(), check()) == ["5s", "5s"]

    async def test_no_timeout_configured_keeps_server_default(self, plain_db: Database) -> None:
        """Characterization: without statement_timeout nothing is set and connections start idle."""
        async with plain_db.connection() as conn:
            assert conn.info.transaction_status.name == "IDLE"
            assert await _show_timeout(conn) == "0"
        async with plain_db.transaction() as conn:
            assert await _show_timeout(conn) == "0"

    async def test_connection_is_idle_with_timeout(self, timeout_db: Database) -> None:
        """With a timeout configured the connection is handed out idle, like without one."""
        async with timeout_db.connection() as conn:
            assert conn.info.transaction_status.name == "IDLE"
            await conn.set_autocommit(True)  # failed before: SET had opened a transaction
            await conn.set_autocommit(False)

    async def test_writes_in_connection_are_kept(self, timeout_db: Database) -> None:
        """Characterization: a transaction block inside connection() commits, with or without a timeout."""
        async with timeout_db.connection() as conn:
            await conn.execute("CREATE TABLE IF NOT EXISTS pool_lifecycle_t (v int)")
            await conn.execute("TRUNCATE pool_lifecycle_t")
            await conn.commit()
        async with timeout_db.connection() as conn, conn.transaction():
            await conn.execute("INSERT INTO pool_lifecycle_t VALUES (1)")
        async with timeout_db.connection() as conn:
            assert (await (await conn.execute("SELECT count(*) FROM pool_lifecycle_t")).fetchone()) == (1,)
            await conn.execute("DROP TABLE pool_lifecycle_t")
            await conn.commit()


class TestFailureContract:
    """Characterization: the exception types callers see today must not change."""

    @pytest.fixture
    def unreachable(self) -> Database:
        return Database(DatabaseSettings(host="127.0.0.1", port=1, dbname="d", user="u", password="p"))

    async def test_ping_raises_connection_error(self, unreachable: Database) -> None:
        with (
            patch("psycopg_toolkit.core.database.AsyncConnection.connect", side_effect=OperationalError("down")),
            patch("tenacity.nap.time.sleep"),
            patch("asyncio.sleep"),
            patch("tenacity.wait.wait_exponential.__call__", return_value=0),
            pytest.raises(DatabaseConnectionError),
        ):
            await unreachable.ping_postgres()

    async def test_create_and_get_pool_raise_connection_error(self, unreachable: Database) -> None:
        with (
            patch("psycopg_toolkit.core.database.AsyncConnection.connect", side_effect=OperationalError("down")),
            patch("tenacity.wait.wait_exponential.__call__", return_value=0),
        ):
            with pytest.raises(DatabaseConnectionError):
                await unreachable.create_pool()
            with pytest.raises(DatabaseConnectionError):
                await unreachable.get_pool()


async def test_check_pool_health_true_on_live_pool(plain_db: Database) -> None:
    assert await plain_db.check_pool_health() is True


async def test_check_pool_health_false_when_pool_unavailable(plain_db: Database) -> None:
    with patch.object(plain_db, "get_pool", side_effect=DatabasePoolError("Failed to create pool")):
        assert await plain_db.check_pool_health() is False


async def test_check_pool_health_false_when_query_fails(plain_db: Database) -> None:
    pool = await plain_db.get_pool()
    await pool.close()
    with patch.object(plain_db, "get_pool", return_value=pool):
        assert await plain_db.check_pool_health() is False
