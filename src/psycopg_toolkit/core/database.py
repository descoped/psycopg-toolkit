import asyncio
import json as stdlib_json
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import cast

from psycopg import AsyncConnection, sql
from psycopg.types import json
from psycopg_pool import AsyncConnectionPool
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential

from ..exceptions import DatabaseConnectionError, DatabasePoolError
from .config import DatabaseSettings
from .transaction import TransactionManager

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
        if settings.connect_retries < 1:
            raise ValueError(
                f"Invalid database settings: connect_retries must be at least 1, got {settings.connect_retries}"
            )

        self._settings = settings
        self._pool: AsyncConnectionPool | None = None
        self._init_callbacks: list[Callable[[AsyncConnectionPool], Awaitable[None]]] = []
        self._transaction_manager: TransactionManager | None = None
        # Serializes pool creation so concurrent first callers share one pool
        self._pool_lock = asyncio.Lock()

    def _configure_json_adapters(self, connection: AsyncConnection) -> None:
        """Reset the connection's JSON loads/dumps to the standard library's, if enabled.

        psycopg decodes json/jsonb to Python objects by default; this does not change that. With
        ``enable_json_adapters`` set, it pins ``json.loads``/``json.dumps`` on this connection, which
        overrides any loader registered globally with ``psycopg.types.json.set_json_loads``. With it
        unset, the connection keeps whatever loaders are in effect.

        Called on every checkout by ``connection()``, ``transaction()`` and the TransactionManager.

        Args:
            connection: The database connection to configure
        """
        if self._settings.enable_json_adapters:
            logger.debug("Configuring JSON adapters for connection")
            # Set up JSON adapters to handle JSONB columns automatically
            json.set_json_loads(loads=stdlib_json.loads, context=connection)
            json.set_json_dumps(dumps=stdlib_json.dumps, context=connection)
            logger.debug("JSON adapters configured successfully")
        else:
            logger.debug("JSON adapters disabled in settings")

    async def _configure_new_connection(self, connection: AsyncConnection) -> None:
        """Apply session settings once to every connection the pool creates.

        Runs as the pool's ``configure`` callback, so the statement timeout holds for every
        pooled connection, whether it is used through ``connection()``, ``transaction()`` or a
        ``TransactionManager``. The connection is left idle, as the pool requires.
        """
        if self._settings.statement_timeout:
            timeout_ms = int(self._settings.statement_timeout * 1000)
            await connection.execute(sql.SQL("SET statement_timeout = {}").format(sql.Literal(timeout_ms)))
            await connection.commit()

    async def ping_postgres(self) -> bool:
        """Test database connectivity, retrying with exponential backoff.

        Makes up to ``settings.connect_retries`` attempts (default 5), waiting 4 to 10 seconds
        between them.

        Returns:
            bool: True if connection successful

        Raises:
            DatabaseConnectionError: If every attempt fails. The last driver error is
                ``original_error`` and ``__cause__``.
        """
        retrying = AsyncRetrying(
            stop=stop_after_attempt(self._settings.connect_retries),
            wait=wait_exponential(multiplier=1, min=4, max=10),
            reraise=True,
        )
        async for attempt in retrying:
            with attempt:
                await self._connect_once()
        return True

    async def _connect_once(self) -> None:
        """One connection attempt; raises DatabaseConnectionError on failure."""
        try:
            logger.info("Pinging PostgreSQL at %s", self._settings.host)
            conn = await AsyncConnection.connect(
                self._settings.get_connection_string(self._settings.connection_timeout)
            )
            await conn.close()
            logger.info("Successfully connected to PostgreSQL")
        except Exception as e:
            logger.warning("Could not connect to PostgreSQL: %s", e)
            raise DatabaseConnectionError("Failed to connect to database", e) from e

    async def create_pool(self) -> AsyncConnectionPool:
        """Create and initialize connection pool.

        Returns:
            AsyncConnectionPool: Configured connection pool

        Raises:
            DatabaseConnectionError: If the database cannot be reached (connection retries exhausted).
            DatabasePoolError: If the pool cannot be created or opened. The cause is chained.
        """
        await self.ping_postgres()

        try:
            logger.info("Initializing connection pool")
            # cast: psycopg_pool cannot infer the connection type parameter from these arguments
            pool = cast(
                "AsyncConnectionPool[AsyncConnection]",
                AsyncConnectionPool(
                    conninfo=self._settings.connection_string,
                    min_size=self._settings.min_pool_size,
                    max_size=self._settings.max_pool_size,
                    timeout=self._settings.pool_timeout,
                    configure=self._configure_new_connection,
                    open=False,
                ),
            )
        except Exception as e:
            logger.error("Could not create connection pool: %s", e)
            raise DatabasePoolError("Failed to create pool") from e

        try:
            await pool.open()
        except Exception as e:
            logger.error("Could not open connection pool: %s", e)
            await pool.close()
            raise DatabasePoolError("Failed to open pool") from e

        self._pool = pool
        return pool

    async def get_pool(self) -> AsyncConnectionPool:
        """Get existing pool or create new one.

        Returns:
            AsyncConnectionPool: Active connection pool

        Safe to call concurrently: only one pool is ever created.

        Raises:
            DatabaseConnectionError: If the database cannot be reached
            DatabasePoolError: If pool creation fails
        """
        if self._pool is None or self._pool.closed:
            async with self._pool_lock:
                if self._pool is None or self._pool.closed:
                    self._pool = await self.create_pool()
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
            AsyncConnection: Database connection, idle (no transaction open)

        Raises:
            DatabaseConnectionError: If the database cannot be reached
            DatabasePoolError: If the pool cannot be created
            psycopg_pool.PoolTimeout: If no connection becomes available within pool_timeout
        """
        async with self._checkout() as conn:
            yield conn

    @asynccontextmanager
    async def _checkout(self) -> AsyncGenerator[AsyncConnection, None]:
        """Borrow a pooled connection with JSON adapters configured.

        The statement timeout is applied once per connection by the pool's configure callback.
        """
        pool = await self.get_pool()
        async with pool.connection() as conn:
            self._configure_json_adapters(conn)
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
                return result is not None and bool(result[0] == 1)
        except Exception as e:
            logger.error(f"Pool health check failed: {e}")
            return False

    def is_pool_active(self) -> bool:
        """Check if pool exists and is not closed.

        Returns:
            bool: True if pool is active
        """
        return self._pool is not None and not self._pool.closed

    async def get_transaction_manager(self) -> TransactionManager:
        """Get existing transaction manager or create new one.

        Returns:
            TransactionManager: Active transaction manager
        """
        if not self._transaction_manager:
            pool = await self.get_pool()
            self._transaction_manager = TransactionManager(pool, self._configure_json_adapters)
        return self._transaction_manager

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncConnection, None]:
        """Get connection with transaction context and JSON adapters.

        Yields:
            AsyncConnection: Database connection in transaction
        """
        async with self._checkout() as conn, conn.transaction():
            yield conn
