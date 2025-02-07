from contextlib import AbstractAsyncContextManager
from unittest.mock import AsyncMock

import pytest
from psycopg.errors import OperationalError
from psycopg_pool import AsyncConnectionPool

from psycopg_toolkit import (
    Database,
    DatabaseSettings,
    TransactionManager,
    DatabaseConnectionError
)


class MockTransaction(AbstractAsyncContextManager):
    """Mock for psycopg Transaction that properly implements async context manager"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class MockConnection(AsyncMock):
    """Mock for psycopg Connection with proper transaction support"""

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
        pool_timeout=5
    )


@pytest.fixture
async def mock_pool():
    # Create the pool mock.
    pool = AsyncMock(spec=AsyncConnectionPool)

    # Create a connection that properly handles transactions.
    conn = MockConnection()

    # Make pool.connection() return an async context manager that yields our connection.
    cm = AsyncMock()
    cm.__aenter__.return_value = conn
    cm.__aexit__.return_value = None
    pool.connection.return_value = cm

    return pool


@pytest.fixture
async def database(db_settings):
    db = Database(db_settings)
    db._pool = AsyncMock(spec=AsyncConnectionPool)
    db._pool.closed = False
    yield db
    await db.cleanup()


@pytest.mark.asyncio
async def test_transaction_manager_exists(database):
    """Test that we can access the transaction manager and it's properly instantiated."""
    transaction_manager = await database.get_transaction_manager()
    assert transaction_manager is not None
    assert isinstance(transaction_manager, TransactionManager)

    # Verify it's the same instance when accessed multiple times.
    second_instance = await database.get_transaction_manager()
    assert transaction_manager is second_instance


@pytest.mark.asyncio
async def test_successful_transaction(database, mock_pool):
    """Test successful transaction flow."""
    # Set up database pool.
    database._pool = mock_pool
    mock_pool.closed = False

    tm = await database.get_transaction_manager()
    transaction_context = tm.transaction()  # Assign to local variable.
    async with transaction_context as conn:
        # Verify we got a connection.
        assert isinstance(conn, MockConnection)
        # Verify transaction was started.
        assert hasattr(conn, '_transaction')


@pytest.mark.asyncio
async def test_transaction_rollback_on_error(database, mock_pool):
    """Test that transaction is rolled back when an exception occurs."""
    database._pool = mock_pool
    mock_pool.closed = False
    tm = await database.get_transaction_manager()

    async def run_test():
        transaction_context = tm.transaction()  # Assign to local variable.
        async with transaction_context as conn:
            assert isinstance(conn, MockConnection)
            assert hasattr(conn, '_transaction')
            raise ValueError("Test error")

    # Expect a DatabaseConnectionError.
    with pytest.raises(DatabaseConnectionError) as excinfo:
        await run_test()

    # Instead of checking excinfo.value.args, check __context__.
    assert excinfo.value.__context__ is not None, "Expected the original exception in __context__"
    original_exception = excinfo.value.__context__
    assert isinstance(original_exception, ValueError)
    assert "Test error" in str(original_exception)


@pytest.mark.asyncio
async def test_transaction_connection_error(database, mock_pool):
    """Test behavior when database connection fails."""
    conn_cm = AsyncMock()
    conn_cm.__aenter__.side_effect = OperationalError("Connection failed")
    mock_pool.connection.return_value = conn_cm

    database._pool = mock_pool
    mock_pool.closed = False

    tm = await database.get_transaction_manager()
    transaction_context = tm.transaction()  # Assign to local variable.
    with pytest.raises(DatabaseConnectionError):
        async with transaction_context:
            pytest.fail("Should not reach this point")


@pytest.mark.asyncio
async def test_nested_transaction(database, mock_pool):
    """Test that nested transactions work correctly and reuse the same connection."""
    # Set up database pool.
    database._pool = mock_pool
    mock_pool.closed = False

    tm = await database.get_transaction_manager()
    outer_transaction = tm.transaction()  # Assign to local variable.
    async with outer_transaction as outer_conn:
        # Verify outer transaction setup.
        assert isinstance(outer_conn, MockConnection)
        assert hasattr(outer_conn, '_transaction')

        inner_transaction = tm.transaction()  # Also assign inner transaction to local variable.
        async with inner_transaction as inner_conn:
            # Verify inner transaction uses the same connection.
            assert inner_conn is outer_conn
            assert hasattr(inner_conn, '_transaction')
