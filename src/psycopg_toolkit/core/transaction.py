import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Generic, TypeVar

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from ..exceptions import DatabaseConnectionError, DatabaseNotAvailable, DatabasePoolError

logger = logging.getLogger(__name__)

T = TypeVar("T")  # Schema type
D = TypeVar("D")  # Data type


class SchemaManager(ABC, Generic[T]):
    """Abstract base class for database schema management.

    Generic type T represents the schema configuration type.
    """

    @abstractmethod
    async def create_schema(self, conn: AsyncConnection) -> T:
        """Create database schema.

        Args:
            conn: Database connection

        Returns:
            T: Schema configuration
        """
        pass

    @abstractmethod
    async def drop_schema(self, conn: AsyncConnection) -> None:
        """Drop database schema.

        Args:
            conn: Database connection
        """
        pass


class DataManager(ABC, Generic[D]):
    """Abstract base class for test data management.

    Generic type D represents the test data type.
    """

    @abstractmethod
    async def setup_data(self, conn: AsyncConnection) -> D:
        """Set up test data in database.

        Args:
            conn: Database connection

        Returns:
            D: Test data configuration
        """
        pass

    @abstractmethod
    async def cleanup_data(self, conn: AsyncConnection) -> None:
        """Clean up test data from database.

        Args:
            conn: Database connection
        """
        pass


@dataclass
class TransactionContext:
    """Transaction context with savepoint support.

    Attributes:
        conn: Database connection
        savepoint_name: Optional savepoint identifier
    """

    conn: AsyncConnection
    savepoint_name: str | None = None

    async def __aenter__(self):
        """Enter transaction context, creating savepoint if specified.

        Returns:
            AsyncConnection: Database connection
        """
        if self.savepoint_name:
            await self.conn.execute(f"SAVEPOINT {self.savepoint_name}")
        return self.conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit transaction context, rolling back to savepoint on error."""
        if exc_type and self.savepoint_name:
            await self.conn.execute(f"ROLLBACK TO SAVEPOINT {self.savepoint_name}")


class TransactionManager:
    """Manages database transactions with schema and data management support.

    Provides context managers for transaction handling, schema operations,
    and test data management.

    Attributes:
        pool: Connection pool for database access
        json_adapter_configurator: Optional function to configure JSON adapters
    """

    def __init__(
        self, pool: AsyncConnectionPool, json_adapter_configurator: Callable[[AsyncConnection], None] | None = None
    ):
        """Initialize with connection pool and optional JSON adapter configurator.

        Args:
            pool: AsyncConnectionPool instance
            json_adapter_configurator: Optional function to configure JSON adapters on connections
        """
        self.pool = pool
        self._json_adapter_configurator = json_adapter_configurator

    @asynccontextmanager
    async def transaction(self, savepoint: str | None = None) -> AsyncGenerator[AsyncConnection, None]:
        """Context manager for database transactions with optional savepoint.

        Args:
            savepoint: Optional savepoint name

        Yields:
            AsyncConnection: Database connection

        Raises:
            DatabaseConnectionError: On transaction or connection failure
        """
        try:
            async with self.pool.connection() as conn:
                # Configure JSON adapters if provided
                if self._json_adapter_configurator:
                    self._json_adapter_configurator(conn)

                async with conn.transaction():
                    if savepoint:
                        async with TransactionContext(conn, savepoint):
                            yield conn
                    else:
                        yield conn
        except Exception as e:
            logger.error(f"Transaction failed: {e}")
            if isinstance(e, DatabaseConnectionError | DatabaseNotAvailable | DatabasePoolError):
                raise
            raise DatabaseConnectionError("Transaction failed", e) from e

    @asynccontextmanager
    async def with_schema(self, schema_manager: SchemaManager[T]) -> AsyncGenerator[T, None]:
        """Context manager for schema operations.

        Args:
            schema_manager: Schema manager implementation

        Yields:
            T: Schema configuration

        Raises:
            DatabaseConnectionError: On schema operation failure
        """
        async with self.transaction() as conn:
            try:
                schema = await schema_manager.create_schema(conn)
                yield schema
            except Exception as e:
                logger.error(f"Schema creation failed: {e}")
                try:
                    await schema_manager.drop_schema(conn)
                except Exception as cleanup_error:
                    logger.error(f"Schema cleanup failed: {cleanup_error}")
                raise

    @asynccontextmanager
    async def with_test_data(self, data_manager: DataManager[D]) -> AsyncGenerator[D, None]:
        """Context manager for test data operations.

        Args:
            data_manager: Test data manager implementation

        Yields:
            D: Test data configuration
        """
        async with self.transaction() as conn:
            try:
                data = await data_manager.setup_data(conn)
                yield data
            finally:
                try:
                    await data_manager.cleanup_data(conn)
                except Exception as e:
                    logger.error(f"Data cleanup failed: {e}")
                    raise

    @asynccontextmanager
    async def managed_transaction(
        self, schema_manager: SchemaManager[T] | None = None, data_manager: DataManager[D] | None = None
    ) -> AsyncGenerator[AsyncConnection, None]:
        """Combined context manager for schema and data operations.

        Args:
            schema_manager: Optional schema manager implementation
            data_manager: Optional test data manager implementation

        Yields:
            AsyncConnection: Database connection
        """
        if schema_manager:
            async with self.with_schema(schema_manager):
                if data_manager:
                    async with self.with_test_data(data_manager), self.transaction() as conn:
                        yield conn
                else:
                    async with self.transaction() as conn:
                        yield conn
        else:
            if data_manager:
                async with self.with_test_data(data_manager), self.transaction() as conn:
                    yield conn
            else:
                async with self.transaction() as conn:
                    yield conn
