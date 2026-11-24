import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from psycopg.errors import OperationalError
from psycopg_pool import AsyncConnectionPool

from psycopg_toolkit import Database, DatabaseConnectionError, DatabasePoolError, DatabaseSettings


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
    async_cm = AsyncMock()
    async_cm.__aenter__.return_value = AsyncMock()
    async_cm.__aexit__.return_value = None
    pool.connection.return_value = async_cm
    return pool


@pytest.fixture
async def database(db_settings):
    db = Database(db_settings)
    yield db
    await db.cleanup()


def test_calc():
    a = 5
    print(f"Value of a is {a**5=}")


@pytest.mark.asyncio
async def test_database_init(database, db_settings):
    assert database._settings == db_settings
    assert database._pool is None
    assert database._init_callbacks == []


@pytest.mark.asyncio
async def test_register_callback(database):
    async def callback(pool):
        pass

    await database.register_init_callback(callback)
    assert len(database._init_callbacks) == 1


@pytest.mark.asyncio
async def test_ping_postgres_success(database):
    with patch("psycopg_toolkit.core.database.AsyncConnection.connect") as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn
        assert await database.ping_postgres() is True
        mock_connect.assert_called_once_with(
            "host=localhost port=5432 dbname=test_db user=test_user password=test_pass connect_timeout=5"
        )


@pytest.mark.asyncio
async def test_ping_postgres_failure(database):
    """M3: after the retries, the documented DatabaseConnectionError, not tenacity's RetryError."""
    error = OperationalError("Connection failed")
    with (
        patch("psycopg_toolkit.core.database.AsyncConnection.connect", side_effect=error) as connect,
        patch("tenacity.wait.wait_exponential.__call__", return_value=0),
        pytest.raises(DatabaseConnectionError) as excinfo,
    ):
        await database.ping_postgres()
    assert type(excinfo.value) is DatabaseConnectionError
    assert excinfo.value.original_error is error
    assert excinfo.value.__cause__ is error
    assert connect.call_count == 5


@pytest.mark.asyncio
@pytest.mark.parametrize("retries", [1, 3])
async def test_ping_postgres_retries_from_settings(retries):
    db = Database(DatabaseSettings(host="h", port=5432, dbname="d", user="u", password="p", connect_retries=retries))
    with (
        patch("psycopg_toolkit.core.database.AsyncConnection.connect", side_effect=OperationalError("x")) as connect,
        patch("tenacity.wait.wait_exponential.__call__", return_value=0),
        pytest.raises(DatabaseConnectionError),
    ):
        await db.ping_postgres()
    assert connect.call_count == retries


def test_connect_retries_must_be_positive():
    with pytest.raises(ValueError, match="connect_retries"):
        Database(DatabaseSettings(host="h", port=5432, dbname="d", user="u", password="p", connect_retries=0))


@pytest.mark.asyncio
async def test_create_pool_unreachable_raises_connection_error(database):
    with (
        patch("psycopg_toolkit.core.database.AsyncConnection.connect", side_effect=OperationalError("down")),
        patch("tenacity.wait.wait_exponential.__call__", return_value=0),
        pytest.raises(DatabaseConnectionError),
    ):
        await database.create_pool()


@pytest.mark.asyncio
async def test_create_pool_open_failure_is_one_pool_error(database):
    """M3: 'Failed to open pool' is raised as-is, no longer wrapped in a second DatabasePoolError."""
    cause = RuntimeError("open failed")
    pool = AsyncMock()
    pool.open = AsyncMock(side_effect=cause)
    with (
        patch.object(Database, "ping_postgres", new=AsyncMock(return_value=True)),
        patch("psycopg_toolkit.core.database.AsyncConnectionPool", return_value=pool),
        pytest.raises(DatabasePoolError) as excinfo,
    ):
        await database.create_pool()
    assert str(excinfo.value) == "Failed to open pool"
    assert excinfo.value.__cause__ is cause
    pool.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_pool_success(database):
    with patch("psycopg_toolkit.core.database.AsyncConnection.connect") as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn

        mock_pool = AsyncMock(spec=AsyncConnectionPool)
        mock_pool.open = AsyncMock()

        with patch("psycopg_toolkit.core.database.AsyncConnectionPool", return_value=mock_pool) as mock_pool_class:
            pool = await database.create_pool()

            mock_pool_class.assert_called_once_with(
                conninfo=database._settings.connection_string,
                min_size=database._settings.min_pool_size,
                max_size=database._settings.max_pool_size,
                timeout=database._settings.pool_timeout,
                configure=database._configure_new_connection,
                open=False,
            )
            mock_pool.open.assert_awaited_once()
            assert pool == mock_pool
            assert database._pool == mock_pool


@pytest.mark.asyncio
async def test_get_pool_existing(database, mock_pool):
    database._pool = mock_pool
    mock_pool.closed = False
    pool = await database.get_pool()
    assert pool == mock_pool


@pytest.mark.asyncio
async def test_get_pool_new(database):
    with patch("psycopg_toolkit.core.database.AsyncConnection.connect") as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn

        mock_pool = AsyncMock(spec=AsyncConnectionPool)
        mock_pool.open = AsyncMock()

        with patch("psycopg_toolkit.core.database.AsyncConnectionPool", return_value=mock_pool) as mock_pool_class:
            pool = await database.get_pool()

            mock_pool_class.assert_called_once_with(
                conninfo=database._settings.connection_string,
                min_size=database._settings.min_pool_size,
                max_size=database._settings.max_pool_size,
                timeout=database._settings.pool_timeout,
                configure=database._configure_new_connection,
                open=False,
            )
            mock_pool.open.assert_awaited_once()
            assert pool == mock_pool
            assert database._pool == mock_pool


@pytest.mark.asyncio
@patch("psycopg_toolkit.core.database.json")
async def test_connection_manager(mock_json, database, mock_pool):
    database._pool = mock_pool
    mock_pool.closed = False
    async with database.connection() as conn:
        assert conn == mock_pool.connection.return_value.__aenter__.return_value
    mock_pool.connection.assert_called_once()


@pytest.mark.asyncio
async def test_init_db(database):
    callback_mock = AsyncMock()
    await database.register_init_callback(callback_mock)

    with patch("psycopg_toolkit.core.database.AsyncConnection.connect") as mock_connect:
        mock_conn = AsyncMock()
        mock_connect.return_value = mock_conn

        mock_pool = AsyncMock(spec=AsyncConnectionPool)
        mock_pool.open = AsyncMock()

        # Mock the connection context manager
        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = AsyncMock()
        async_cm.__aexit__.return_value = None
        mock_pool.connection.return_value = async_cm
        mock_pool.getconn = AsyncMock(return_value=mock_conn)

        with patch("psycopg_toolkit.core.database.AsyncConnectionPool", return_value=mock_pool):
            await database.init_db()
            callback_mock.assert_awaited_once_with(mock_pool)


@pytest.mark.asyncio
async def test_cleanup(database, mock_pool):
    database._pool = mock_pool
    mock_pool.close = AsyncMock()

    await database.cleanup()
    mock_pool.close.assert_awaited_once()
    assert database._pool is None


@pytest.mark.asyncio
async def test_cleanup_error(database, mock_pool):
    database._pool = mock_pool
    mock_pool.close = AsyncMock(side_effect=Exception("Cleanup failed"))

    with pytest.raises(DatabasePoolError):
        await database.cleanup()
    assert database._pool is None


@pytest.mark.asyncio
async def test_create_pool_cancelled_during_open_closes_pool(database):
    """A cancelled create_pool() must not leave the half-opened pool running."""
    opening = asyncio.Event()

    async def slow_open():
        opening.set()
        await asyncio.sleep(10)

    pool = AsyncMock()
    pool.open = slow_open
    with (
        patch.object(Database, "ping_postgres", new=AsyncMock(return_value=True)),
        patch("psycopg_toolkit.core.database.AsyncConnectionPool", return_value=pool),
    ):
        task = asyncio.create_task(database.create_pool())
        await opening.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    pool.close.assert_awaited_once()
    assert database._pool is None


@pytest.mark.asyncio
async def test_get_pool_cancelled_during_open_allows_a_retry(database):
    """After a cancelled first get_pool(), the lock is free and a new pool is created."""
    first = AsyncMock()

    async def never_open():
        await asyncio.sleep(10)

    first.open = never_open
    second = AsyncMock()
    second.closed = False
    with (
        patch.object(Database, "ping_postgres", new=AsyncMock(return_value=True)),
        patch("psycopg_toolkit.core.database.AsyncConnectionPool", side_effect=[first, second]),
    ):
        task = asyncio.create_task(database.get_pool())
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert await asyncio.wait_for(database.get_pool(), timeout=1) is second
    first.close.assert_awaited_once()
