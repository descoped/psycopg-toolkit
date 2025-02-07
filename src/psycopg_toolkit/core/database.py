import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable, List, Optional, Awaitable, Any

import psycopg
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import DatabaseSettings
from ..exceptions import (
    DatabaseConnectionError,
    DatabaseNotAvailable,
    DatabasePoolError
)

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
        self._pool: Optional[AsyncConnectionPool] = None
        self._init_callbacks: List[Callable[[AsyncConnectionPool], Awaitable[None]]] = []
        self._transaction_manager = None

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def ping_postgres(self) -> bool:
        """Test database connectivity with exponential backoff retry.

        Returns:
            bool: True if connection successful

        Raises:
            DatabaseConnectionError: If connection fails after retries
        """
        try:
            logger.info(f"Pinging PostgreSQL at {self._settings.host}")
            conn = psycopg.connect(self._settings.get_connection_string(self._settings.connection_timeout))
            conn.close()
            logger.info("Successfully connected to PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"Could not connect to PostgreSQL: {e}")
            raise DatabaseConnectionError("Failed to connect to database", e)

    async def create_pool(self) -> AsyncConnectionPool:
        """Create and initialize connection pool.

        Returns:
            AsyncConnectionPool: Configured connection pool

        Raises:
            DatabaseConnectionError: If database ping fails
            DatabasePoolError: If pool creation or initialization fails
        """
        try:
            if not self.ping_postgres():
                raise DatabaseConnectionError("Failed to ping database")

            logger.info("Initializing connection pool")
            pool = AsyncConnectionPool(
                conninfo=self._settings.connection_string,
                min_size=self._settings.min_pool_size,
                max_size=self._settings.max_pool_size,
                timeout=self._settings.pool_timeout,
                open=False
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

    async def register_init_callback(
            self,
            callback: Callable[[AsyncConnectionPool], Awaitable[None]]
    ) -> None:
        """Register callback to run during database initialization.

        Args:
            callback: Async function taking pool as argument
        """
        self._init_callbacks.append(callback)

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[AsyncConnection, None]:
        """Get database connection with configured statement timeout.

        Yields:
            AsyncConnection: Database connection

        Raises:
            DatabaseConnectionError: If connection acquisition fails
        """
        pool = await self.get_pool()
        async with pool.connection() as conn:
            if self._settings.statement_timeout:
                await conn.execute(
                    f"SET statement_timeout = {int(self._settings.statement_timeout * 1000)}"
                )
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
            async with pool.connection() as conn:
                async with conn.cursor() as cur:
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

    async def get_transaction_manager(self) -> Any:
        """Get existing transaction manager or create new one.

        Returns:
            TransactionManager: Active transaction manager
        """
        if not self._transaction_manager:
            from .transaction import TransactionManager
            pool = await self.get_pool()
            self._transaction_manager = TransactionManager(pool)
        return self._transaction_manager

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncConnection, None]:
        """Get connection with transaction context.

        Yields:
            AsyncConnection: Database connection in transaction
        """
        pool = await self.get_pool()
        async with pool.connection() as conn:
            async with conn.transaction():
                yield conn
