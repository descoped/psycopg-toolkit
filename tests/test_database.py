from unittest.mock import AsyncMock, Mock, patch

import pytest
from psycopg.errors import OperationalError
from psycopg_pool import AsyncConnectionPool
from tenacity import RetryError

from psycopg_toolkit import Database, DatabaseSettings, DatabasePoolError


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
    with patch('psycopg_toolkit.core.database.psycopg.connect') as mock_connect:
        mock_conn = Mock()
        mock_connect.return_value = mock_conn
        assert database.ping_postgres() is True
        mock_connect.assert_called_once_with(
            'host=localhost port=5432 dbname=test_db user=test_user password=test_pass connect_timeout=5'
        )


@pytest.mark.asyncio
async def test_ping_postgres_failure(database):
    with patch('psycopg_toolkit.core.database.psycopg.connect', side_effect=OperationalError("Connection failed")), \
            patch('tenacity.wait.wait_exponential.__call__', return_value=0):
        with pytest.raises(RetryError):
            database.ping_postgres()


@pytest.mark.asyncio
async def test_create_pool_success(database):
    with patch('psycopg_toolkit.core.database.psycopg.connect') as mock_connect:
        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        mock_pool = AsyncMock(spec=AsyncConnectionPool)
        mock_pool.open = AsyncMock()

        with patch('psycopg_toolkit.core.database.AsyncConnectionPool', return_value=mock_pool) as mock_pool_class:
            pool = await database.create_pool()

            mock_pool_class.assert_called_once_with(
                conninfo=database._settings.connection_string,
                min_size=database._settings.min_pool_size,
                max_size=database._settings.max_pool_size,
                timeout=database._settings.pool_timeout,
                open=False
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
    with patch('psycopg_toolkit.core.database.psycopg.connect') as mock_connect:
        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        mock_pool = AsyncMock(spec=AsyncConnectionPool)
        mock_pool.open = AsyncMock()

        with patch('psycopg_toolkit.core.database.AsyncConnectionPool', return_value=mock_pool) as mock_pool_class:
            pool = await database.get_pool()

            mock_pool_class.assert_called_once_with(
                conninfo=database._settings.connection_string,
                min_size=database._settings.min_pool_size,
                max_size=database._settings.max_pool_size,
                timeout=database._settings.pool_timeout,
                open=False
            )
            mock_pool.open.assert_awaited_once()
            assert pool == mock_pool
            assert database._pool == mock_pool


@pytest.mark.asyncio
async def test_connection_manager(database, mock_pool):
    database._pool = mock_pool
    mock_pool.closed = False
    async with database.connection() as conn:
        assert conn == mock_pool.connection.return_value.__aenter__.return_value
    mock_pool.connection.assert_called_once()


@pytest.mark.asyncio
async def test_init_db(database):
    callback_mock = AsyncMock()
    await database.register_init_callback(callback_mock)

    with patch('psycopg_toolkit.core.database.psycopg.connect') as mock_connect:
        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        mock_pool = AsyncMock(spec=AsyncConnectionPool)
        mock_pool.open = AsyncMock()

        # Mock the connection context manager
        async_cm = AsyncMock()
        async_cm.__aenter__.return_value = AsyncMock()
        async_cm.__aexit__.return_value = None
        mock_pool.connection.return_value = async_cm
        mock_pool.getconn = AsyncMock(return_value=mock_conn)

        with patch('psycopg_toolkit.core.database.AsyncConnectionPool', return_value=mock_pool):
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
