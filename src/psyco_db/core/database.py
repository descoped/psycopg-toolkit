import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import psycopg
from fastapi import HTTPException
from psycopg_pool import AsyncConnectionPool
from tenacity import retry, stop_after_attempt, wait_exponential

from metadocs.core.config import get_settings
from metadocs.services.db_import_document_types_service import DbImportDocumentTypesService

logger = logging.getLogger(__name__)
settings = get_settings()


class Database:
    """
    Database management class that handles connection pooling and database operations.
    """
    def __init__(self):
        self._pool: Optional[AsyncConnectionPool] = None

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    def ping_postgres(self) -> bool:
        """
        Ping the PostgreSQL database to check if it's up and reachable.
        """
        try:
            logger.info(f"Pinging PostgreSQL at host: {settings.POSTGRES_HOST}, "
                        f"dbname: {settings.POSTGRES_DB}, "
                        f"user: {settings.POSTGRES_USER}")

            conn = psycopg.connect(
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT,
                dbname=settings.POSTGRES_DB,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD
            )
            conn.close()
            logger.info("Successfully connected to PostgreSQL.")
            return True
        except Exception as e:
            logger.error(f"Error: Could not connect to PostgreSQL. Details: {e}")
            return False

    async def create_pool(self) -> Optional[AsyncConnectionPool]:
        """
        Create a database connection pool if PostgreSQL is reachable.
        """
        if not self.ping_postgres():
            return None

        try:
            logger.info("Initializing connection pool to PostgreSQL.")
            pool = AsyncConnectionPool(
                conninfo=(
                    f"host={settings.POSTGRES_HOST} "
                    f"port={settings.POSTGRES_PORT} "
                    f"dbname={settings.POSTGRES_DB} "
                    f"user={settings.POSTGRES_USER} "
                    f"password={settings.POSTGRES_PASSWORD}"
                ),
                min_size=5,
                max_size=20,
                timeout=30,
                open=False  # Important: Don't open in constructor
            )
            # Explicitly open the pool
            await pool.open()
            self._pool = pool
            return pool
        except Exception as e:
            logger.error(f"Error: Could not create connection pool to PostgreSQL. Details: {e}")
            return None

    async def get_pool(self) -> AsyncConnectionPool:
        """
        Get existing pool or create new one if none exists.
        """
        if self._pool is None:
            self._pool = await self.create_pool()
            if self._pool is None:
                raise HTTPException(
                    status_code=503,
                    detail="Database is not available."
                )
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
        Initialize the database pool on application startup.
        """
        try:
            pool = await self.get_pool()
            async with pool.connection() as conn:
                logger.info("Database pool initialized successfully.")
                # populate db here
                db_import = DbImportDocumentTypesService()
                await db_import.initialize_db(pool)
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def cleanup(self) -> None:
        """
        Cleanup database resources on shutdown.
        """
        if self._pool is not None:
            logger.info("Closing database connection pool...")
            try:
                await self._pool.close()
                logger.info("Database connection pool closed successfully.")
            except Exception as e:
                logger.error(f"Error closing database pool: {e}")
            finally:
                self._pool = None


# Create singleton instance
db = Database()
