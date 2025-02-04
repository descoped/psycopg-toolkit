import logging
from asyncio import Lock
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Callable, List, Optional, Awaitable

import psycopg
from psycopg_pool import AsyncConnectionPool
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import DatabaseSettings
from .transaction import TransactionManager
from ..exceptions import DatabaseConnectionError, DatabaseNotAvailable, DatabasePoolError

logger = logging.getLogger(__name__)


class Database:
    """
    Database management class that handles connection pooling and database operations.
    """

    def __init__(self, settings: DatabaseSettings):
        self._pool: Optional[AsyncConnectionPool] = None
        self._settings = settings
        self._init_callbacks: List[Callable[[AsyncConnectionPool], Awaitable[None]]] = []
        self._transaction_manager: Optional[TransactionManager] = None
        self._pool_lock = Lock()  # Add thread lock
        self._callbacks_lock = Lock()  # Separate lock for callbacks
        self._transaction_manager_lock = Lock()

    async def get_transaction_manager(self) -> TransactionManager:
        """
        Get the transaction manager instance.

        Returns:
            TransactionManager: Instance for managing database transactions
        """
        async with self._transaction_manager_lock:
            if self._transaction_manager is None:
                self._transaction_manager = TransactionManager(self)
            return self._transaction_manager

    async def register_init_callback(self, callback: Callable[[AsyncConnectionPool], Awaitable[None]]) -> None:
        """
        Register a callback to be executed after pool initialization.

        Args:
            callback: Async function that takes a pool instance and performs initialization
        """
        async with self._callbacks_lock:
            self._init_callbacks.append(callback)

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def ping_postgres(self) -> bool:
        """
        Ping the PostgreSQL database to check if it's up and reachable.

        Raises:
            DatabaseConnectionError: If connection fails
        """
        try:
            logger.info(f"Pinging PostgreSQL at host: {self._settings.host}, "
                        f"dbname: {self._settings.dbname}, "
                        f"user: {self._settings.user}")

            conn = psycopg.connect(self._settings.connection_string)
            conn.close()
            logger.info("Successfully connected to PostgreSQL.")
            return True
        except Exception as e:
            error_msg = f"Could not connect to PostgreSQL"
            logger.error(f"Error: {error_msg}. Details: {e}")
            raise DatabaseConnectionError(error_msg, original_error=e)

    async def create_pool(self) -> Optional[AsyncConnectionPool]:
        """
        Create a database connection pool if PostgreSQL is reachable.

        Raises:
            DatabasePoolError: If pool creation fails
        """
        try:
            self.ping_postgres()
            logger.info("Initializing connection pool to PostgreSQL.")

            pool = AsyncConnectionPool(
                conninfo=self._settings.connection_string,
                min_size=self._settings.min_pool_size,
                max_size=self._settings.max_pool_size,
                timeout=self._settings.pool_timeout,
                open=False
            )
            await pool.open()
            self._pool = pool
            return pool
        except Exception as e:
            error_msg = "Could not create connection pool to PostgreSQL"
            logger.error(f"Error: {error_msg}. Details: {e}")
            raise DatabasePoolError(error_msg)

    async def get_pool(self) -> AsyncConnectionPool:
        """
        Get existing pool or create new one if none exists.

        Raises:
            DatabaseNotAvailable: If database is not available
        """

        if self._pool is not None:
            return self._pool

        async with self._pool_lock:
            if self._pool is not None:
                return self._pool

            try:
                self._pool = await self.create_pool()
            except Exception as e:
                raise DatabaseNotAvailable("Database is not available") from e
            return self._pool

    @asynccontextmanager
    async def connection(self) -> AsyncGenerator[AsyncConnectionPool, None]:
        """
        Get a database connection from the pool.
        """
        pool = await self.get_pool()
        async with pool.connection() as conn:
            yield conn

    async def init_db(self) -> None:
        """
        Initialize the database pool and execute registered callbacks.
        """
        try:
            pool = await self.get_pool()
            async with pool.connection():
                logger.info("Database pool initialized successfully.")

                # Execute registered initialization callbacks
                for callback in self._init_callbacks:
                    await callback(pool)

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def cleanup(self) -> None:
        """
        Cleanup database resources on shutdown.
        """
        async with self._pool_lock:
            if self._pool is not None:
                logger.info("Closing database connection pool...")
                try:
                    await self._pool.close()
                    logger.info("Database connection pool closed successfully.")
                except Exception as e:
                    logger.error(f"Error closing database pool: {e}")
                    raise DatabasePoolError("Failed to close database pool") from e
                finally:
                    self._pool = None

    def is_pool_active(self) -> bool:
        return self._pool is not None and not self._pool.closed

    async def check_pool_health(self) -> bool:
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
