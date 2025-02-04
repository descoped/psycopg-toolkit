import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from psycopg import AsyncConnection

logger = logging.getLogger(__name__)


class TransactionManager:
    """
    Manages database transactions with automatic rollback on exception.
    """

    def __init__(self, database: 'Database'):  # type: ignore
        self._database = database

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[AsyncConnection, None]:
        """
        Context manager for handling database transactions with automatic
        rollback on exception.

        Returns:
            AsyncGenerator[AsyncConnection, None]: Database connection with active transaction

        Raises:
            DatabaseNotAvailable: If database is not available
            DatabaseConnectionError: If connection fails
            DatabasePoolError: If pool operations fail
        """
        try:
            pool = await self._database.get_pool()
            async with pool.connection() as conn:
                async with conn.transaction():
                    yield conn
                    # Transaction is automatically committed if no exception occurs
        except Exception as e:
            # Transaction is automatically rolled back on exception
            logger.error(f"Transaction failed: {e}")
            raise
