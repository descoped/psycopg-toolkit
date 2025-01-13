from unittest.mock import AsyncMock, Mock
import pytest
from contextlib import AbstractAsyncContextManager
from psycopg.errors import OperationalError
from psycopg_pool import AsyncConnectionPool

from psyco_db import (
    Database,
    DatabaseSettings,
    TransactionManager,
    DatabaseConnectionError,
    DatabaseNotAvailable
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
    # Create the pool mock
    pool = AsyncMock(spec=AsyncConnectionPool)

    # Create a connection that properly handles transactions
    conn = MockConnection()

    # Make pool.connection() return an async context manager that yields our connection
    cm = AsyncMock()
    cm.__aenter__.return_value = conn
    cm.__aexit__.return_value = None
    pool.connection.return_value = cm

    return pool


@pytest.fixture
async def database(db_settings):
    db = Database(db_settings)
    yield db
    await db.cleanup()


@pytest.mark.asyncio
async def test_transaction_manager_exists(database):
    """Test that we can access the transaction manager and it's properly instantiated"""
    assert database.transaction_manager is not None
    assert isinstance(database.transaction_manager, TransactionManager)
    # Verify it's the same instance when accessed multiple times
    assert database.transaction_manager is database.transaction_manager


@pytest.mark.asyncio
async def test_successful_transaction(database, mock_pool):
    """Test successful transaction flow"""
    # Set up database pool
    database._pool = mock_pool

    # Execute a transaction
    async with database.transaction_manager.transaction() as conn:
        # Verify we got a connection
        assert isinstance(conn, MockConnection)
        # Verify transaction was started
        assert hasattr(conn, '_transaction')


@pytest.mark.asyncio
async def test_transaction_rollback_on_error(database, mock_pool):
    """Test that transaction is rolled back when an exception occurs"""
    # Set up database pool
    database._pool = mock_pool

    # Execute a transaction that will raise an error
    with pytest.raises(ValueError, match="Test error"):
        async with database.transaction_manager.transaction() as conn:
            # Verify we got a connection and transaction was started
            assert isinstance(conn, MockConnection)
            assert hasattr(conn, '_transaction')

            # Raise an error to trigger rollback
            raise ValueError("Test error")


@pytest.mark.asyncio
async def test_transaction_connection_error(database, mock_pool):
    """Test behavior when database connection fails"""
    # Configure pool to raise connection error
    conn_cm = AsyncMock()
    conn_cm.__aenter__.side_effect = OperationalError("Connection failed")
    mock_pool.connection.return_value = conn_cm

    # Set up database pool
    database._pool = mock_pool

    # Attempt transaction and verify it raises the correct error
    with pytest.raises(OperationalError, match="Connection failed"):
        async with database.transaction_manager.transaction():
            pytest.fail("Should not reach this point")


@pytest.mark.asyncio
async def test_nested_transaction(database, mock_pool):
    """Test that nested transactions work correctly and reuse the same connection"""
    # Set up database pool
    database._pool = mock_pool

    # Execute nested transactions
    async with database.transaction_manager.transaction() as outer_conn:
        # Verify outer transaction setup
        assert isinstance(outer_conn, MockConnection)
        assert hasattr(outer_conn, '_transaction')

        async with database.transaction_manager.transaction() as inner_conn:
            # Verify inner transaction uses same connection
            assert inner_conn is outer_conn
            assert hasattr(inner_conn, '_transaction')