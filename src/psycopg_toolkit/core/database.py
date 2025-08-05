import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .transaction import TransactionManager

from psycopg import AsyncConnection
from psycopg.types import json
from psycopg_pool import AsyncConnectionPool
from tenacity import retry, stop_after_attempt, wait_exponential

from ..exceptions import DatabaseConnectionError, DatabaseNotAvailable, DatabasePoolError
from .config import DatabaseSettings

logger = logging.getLogger(__name__)


class Database:
    """PostgreSQL database manager with connection pooling and transaction support.

    Manages database connections, connection pools, and transactions using psycopg3.
    Implements connection retry logic and health checks. Supports initialization callbacks
    and statement timeout configuration.

    Attributes:
        _settings (DatabaseSettings): Connection and pool configuration
        _pool (Optional[AsyncConnectionPool]): Connection pool instance
        _init_callbacks (List[Callable]): Initialization callback functions
        _transaction_manager (Optional[TransactionManager]): Transaction manager instance
    """

    def __init__(self, settings: DatabaseSettings):
        """Initialize database manager with settings.

        Args:
            settings: Database connection and pool configuration

        Raises:
            ValueError: If required settings are missing
        """
        if not settings.host or not settings.dbname or not settings.user:
            raise ValueError("Invalid database settings: host, dbname, and user are required")

        self._settings = settings
        self._pool: AsyncConnectionPool | None = None
        self._init_callbacks: list[Callable[[AsyncConnectionPool], Awaitable[None]]] = []
        self._transaction_manager: TransactionManager | None = None

    def _configure_json_adapters(self, connection: AsyncConnection) -> None:
        """Configure psycopg JSON adapters for JSONB support.

        This method sets up automatic JSON/JSONB handling using psycopg's built-in
        JSON adapters, which provide seamless conversion between Python objects
        and PostgreSQL JSON/JSONB data types.

        Args:
            connection: The database connection to configure

        Note:
            This is called automatically when enable_json_adapters is True in settings.
            The adapters handle serialization/deserialization transparently at the
            driver level, which can be more efficient than manual processing.
        """
        if self._settings.enable_json_adapters:
            logger.debug("Configuring JSON adapters for connection")
            # Set up JSON adapters to handle JSONB columns automatically
            json.set_json_loads(loads=json.json.loads, context=connection)
            json.set_json_dumps(dumps=json.json.dumps, context=connection)
            logger.debug("JSON adapters configured successfully")
        else:
            logger.debug("JSON adapters disabled in settings")

    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=10))
    async def ping_postgres(self) -> bool:
        """Test database connectivity with exponential backoff retry.

        Returns:
            bool: True if connection successful

        Raises:
            DatabaseConnectionError: If connection fails after retries
        """
        try:
            logger.info(f"Pinging PostgreSQL at {self._settings.host}")
            conn = await AsyncConnection.connect(self._settings.get_connection_string(self._settings.connection_timeout))
            await conn.close()
            logger.info("Successfully connected to PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"Could not connect to PostgreSQL: {e}")
            raise DatabaseConnectionError("Failed to connect to database", e) from e

    async def create_pool(self) -> AsyncConnectionPool:
        """Create and initialize connection pool.

        Returns:
            AsyncConnectionPool: Configured connection pool

        Raises:
            DatabaseConnectionError: If database ping fails
            DatabasePoolError: If pool creation or initialization fails
        """
        try:
            if not await self.ping_postgres():
                raise DatabaseConnectionError("Failed to ping database")

            logger.info("Initializing connection pool")
            pool = AsyncConnectionPool(
                conninfo=self._settings.connection_string,
                min_size=self._settings.min_pool_size,
                max_size=self._settings.max_pool_size,
                timeout=self._settings.pool_timeout,
                open=False,
            )

            try:
                await pool.open()
                self._pool = pool
            except Exception as e:
                await pool.close()
                raise DatabasePoolError("Failed to open pool") from e

            return pool
        except Exception as e:
            logger.error(f"Could not create connection pool: {e}")
            raise DatabasePoolError("Failed to create pool") from e

    async def get_pool(self) -> AsyncConnectionPool:
        """Get existing pool or create new one.

        Returns:
            AsyncConnectionPool: Active connection pool

        Raises:
            DatabaseNotAvailable: If pool creation fails
        """
        if not self._pool or self._pool.closed:
            self._pool = await self.create_pool()
            if not self._pool:
                raise DatabaseNotAvailable("Database is not available")
        return self._pool

    async def register_init_callback(self, callback: Callable[[AsyncConnectionPool], Awaitable[None]]) -> None:
        """Register callback to run during database initialization.

        Args:
            callback: Async function taking pool as argument
        """
        self._init_callbacks.append(callback)

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[AsyncConnection, None]:
        """Get database connection with configured statement timeout and JSON adapters.

        Yields:
            AsyncConnection: Database connection

        Raises:
            DatabaseConnectionError: If connection acquisition fails
        """
        pool = await self.get_pool()
        async with pool.connection() as conn:
            # Configure JSON adapters if enabled
            self._configure_json_adapters(conn)

            if self._settings.statement_timeout:
                await conn.execute(f"SET statement_timeout = {int(self._settings.statement_timeout * 1000)}")
            yield conn

    async def init_db(self) -> None:
        """Initialize database and run registered callbacks.

        Raises:
            DatabaseConnectionError: If initialization or callbacks fail
        """
        try:
            pool = await self.get_pool()
            async with pool.connection() as _:
                logger.info("Database pool initialized")

                for callback in self._init_callbacks:
                    try:
                        await callback(pool)
                    except Exception as e:
                        logger.error(f"Callback failed: {e}")
                        await self.cleanup()
                        raise

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            await self.cleanup()
            raise

    async def cleanup(self) -> None:
        """Clean up database resources and close pool.

        Raises:
            DatabasePoolError: If pool closure fails
        """
        if self._pool:
            logger.info("Closing database pool")
            try:
                await self._pool.close()
                logger.info("Database pool closed")
            except Exception as e:
                logger.error(f"Error closing pool: {e}")
                raise DatabasePoolError("Failed to close pool") from e
            finally:
                self._pool = None
                self._transaction_manager = None

    async def check_pool_health(self) -> bool:
        """Check connection pool health by executing test query.

        Returns:
            bool: True if pool is healthy
        """
        try:
            pool = await self.get_pool()
            async with pool.connection() as conn, conn.cursor() as cur:
                await cur.execute("SELECT 1")
                result = await cur.fetchone()
                return result is not None and result[0] == 1
        except Exception as e:
            logger.error(f"Pool health check failed: {e}")
            return False

    def is_pool_active(self) -> bool:
        """Check if pool exists and is not closed.

        Returns:
            bool: True if pool is active
        """
        return self._pool is not None and not self._pool.closed

    async def get_transaction_manager(self) -> "TransactionManager":
        """Get existing transaction manager or create new one.

        Returns:
            TransactionManager: Active transaction manager
        """
        if not self._transaction_manager:
            from .factory import create_transaction_manager

            pool = await self.get_pool()
            self._transaction_manager = create_transaction_manager(pool, self._configure_json_adapters)
        return self._transaction_manager

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncConnection, None]:
        """Get connection with transaction context and JSON adapters.

        Yields:
            AsyncConnection: Database connection in transaction
        """
        pool = await self.get_pool()
        async with pool.connection() as conn:
            # Configure JSON adapters if enabled
            self._configure_json_adapters(conn)

            async with conn.transaction():
                yield conn
