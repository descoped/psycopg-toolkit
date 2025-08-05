from contextlib import AbstractAsyncContextManager, suppress
from unittest.mock import AsyncMock, patch

import pytest
from psycopg.errors import OperationalError
from psycopg_pool import AsyncConnectionPool

from psycopg_toolkit import Database, DatabaseConnectionError, DatabaseSettings, TransactionManager


class MockTransaction(AbstractAsyncContextManager):
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class MockConnection(AsyncMock):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._transaction = MockTransaction()

    def transaction(self):
        return self._transaction


@pytest.fixture
def db_settings():
    return DatabaseSettings(
        host="localhost",
        port=5432,
        dbname="test_db",
        user="test_user",
        password="test_pass",
        min_pool_size=1,
        max_pool_size=5,
        pool_timeout=5,
    )


@pytest.fixture
async def mock_pool():
    pool = AsyncMock(spec=AsyncConnectionPool)
    conn = MockConnection()

    cm = AsyncMock()
    cm.__aenter__.return_value = conn
    cm.__aexit__.return_value = None
    pool.connection.return_value = cm
    pool.close = AsyncMock()

    return pool


@pytest.fixture
async def database(db_settings, mock_pool):
    with patch.object(Database, "ping_postgres", return_value=True):
        db = Database(db_settings)
        db._pool = mock_pool
        db._pool.closed = False
        yield db
        with suppress(Exception):
            await db.cleanup()


@pytest.fixture
async def setup_mock_pool(database, mock_pool):
    database._pool = mock_pool
    database._pool.closed = False
    return database


@pytest.mark.asyncio
async def test_transaction_manager_exists(database):
    transaction_manager = await database.get_transaction_manager()
    assert transaction_manager is not None
    assert isinstance(transaction_manager, TransactionManager)

    second_instance = await database.get_transaction_manager()
    assert transaction_manager is second_instance


@pytest.mark.asyncio
@patch("psycopg_toolkit.core.database.json")
async def test_successful_transaction(mock_json, setup_mock_pool):
    database = setup_mock_pool
    tm = await database.get_transaction_manager()
    async with tm.transaction() as conn:
        assert isinstance(conn, MockConnection)
        assert hasattr(conn, "_transaction")


@pytest.mark.asyncio
@patch("psycopg_toolkit.core.database.json")
async def test_transaction_rollback_on_error(mock_json, setup_mock_pool):
    database = setup_mock_pool
    tm = await database.get_transaction_manager()

    async def run_test():
        async with tm.transaction() as conn:
            assert isinstance(conn, MockConnection)
            assert hasattr(conn, "_transaction")
            raise ValueError("Test error")

    with pytest.raises(DatabaseConnectionError) as excinfo:
        await run_test()

    assert excinfo.value.__context__ is not None
    original_exception = excinfo.value.__context__
    assert isinstance(original_exception, ValueError)
    assert "Test error" in str(original_exception)


@pytest.mark.asyncio
@patch("psycopg_toolkit.core.database.json")
async def test_transaction_connection_error(mock_json, setup_mock_pool):
    database = setup_mock_pool
    conn_cm = AsyncMock()
    conn_cm.__aenter__.side_effect = OperationalError("Connection failed")
    database._pool.connection.return_value = conn_cm

    tm = await database.get_transaction_manager()
    with pytest.raises(DatabaseConnectionError):
        async with tm.transaction():
            pytest.fail("Should not reach this point")


@pytest.mark.asyncio
@patch("psycopg_toolkit.core.database.json")
async def test_nested_transaction(mock_json, setup_mock_pool):
    database = setup_mock_pool
    tm = await database.get_transaction_manager()

    async with tm.transaction() as outer_conn:
        assert isinstance(outer_conn, MockConnection)
        assert hasattr(outer_conn, "_transaction")

        async with tm.transaction() as inner_conn:
            assert inner_conn is outer_conn
            assert hasattr(inner_conn, "_transaction")


@pytest.mark.asyncio
async def test_cleanup_closes_pool(setup_mock_pool):
    database = setup_mock_pool
    original_pool = database._pool
    await database.cleanup()
    original_pool.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_pool_size_limits(db_settings):
    with (
        patch.object(Database, "ping_postgres", return_value=True),
        patch("psycopg_toolkit.core.database.AsyncConnectionPool", autospec=True) as pool_mock,
    ):
        database = Database(db_settings)
        await database.get_pool()

        pool_mock.assert_called_once()
        call_kwargs = pool_mock.call_args.kwargs
        assert call_kwargs["min_size"] == db_settings.min_pool_size
        assert call_kwargs["max_size"] == db_settings.max_pool_size
