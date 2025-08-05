from collections.abc import AsyncGenerator, Generator
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from psycopg import AsyncConnection, AsyncTransaction
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel, ConfigDict
from schema_and_data import TestUserData, UserSchemaManager
from testcontainers.postgres import PostgresContainer

from psycopg_toolkit import Database, DatabaseSettings, TransactionManager

_db: Database | None = None


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    with PostgresContainer("postgres:17") as container:
        # Initialize schema after container starts
        import time

        import psycopg

        # Wait for container to be ready
        time.sleep(2)

        # Create tables using sync connection
        from pathlib import Path

        conn_str = f"postgresql://{container.username}:{container.password}@{container.get_container_host_ip()}:{container.get_exposed_port(5432)}/{container.dbname}"
        with psycopg.connect(conn_str) as conn, conn.cursor() as cur:
            sql_path = Path(__file__).parent / "sql" / "init_test_schema.sql"
            with sql_path.open() as f:
                cur.execute(f.read())
            conn.commit()

        yield container


@pytest.fixture(scope="session")
def test_settings(postgres_container: PostgresContainer) -> DatabaseSettings:
    return DatabaseSettings(
        host=postgres_container.get_container_host_ip(),
        port=postgres_container.get_exposed_port(5432),
        dbname=postgres_container.dbname,
        user=postgres_container.username,
        password=postgres_container.password,
    )


@pytest.fixture(scope="function")
async def _database_instance(test_settings: DatabaseSettings) -> AsyncGenerator[Database, None]:
    """Create a Database instance that persists for the entire test session."""
    global _db
    if _db is None:
        _db = Database(settings=test_settings)
        try:
            await _db.create_pool()
            await _db.init_db()
        except Exception as e:
            await _db.cleanup()
            _db = None
            raise e

    yield _db


@pytest.fixture(scope="function")
async def db_pool(_database_instance: Database) -> AsyncGenerator[AsyncConnectionPool, None]:
    """Get the connection pool from the database instance."""
    yield await _database_instance.get_pool()


@pytest.fixture(scope="function")
async def db_connection(_database_instance: Database) -> AsyncGenerator[AsyncConnection, None]:
    """Get a connection for each test function."""
    pool = await _database_instance.get_pool()
    async with pool.connection() as conn:
        yield conn


@pytest.fixture(scope="function")
async def transaction(db_connection: AsyncConnection) -> AsyncGenerator[AsyncTransaction, None]:
    """Get a transaction for each test function."""
    async with db_connection.transaction() as tx:
        yield tx


@pytest.fixture(scope="function")
async def transaction_manager(_database_instance: Database) -> AsyncGenerator[TransactionManager, None]:
    yield await _database_instance.get_transaction_manager()


@pytest.fixture
def user_schema_manager():
    return UserSchemaManager()


@pytest.fixture
def test_user():
    return {"id": uuid4(), "email": "test@example.com"}


@pytest.fixture
def test_data_manager(test_user):
    return TestUserData([test_user])


@pytest.fixture
async def setup_test_db(transaction_manager, user_schema_manager, test_data_manager):
    async with transaction_manager.transaction() as conn:
        await user_schema_manager.create_schema(conn)
        await test_data_manager.setup_data(conn)
    return test_data_manager.test_users[0]


# JSONB-specific fixtures


@pytest.fixture
def mock_db_connection():
    """Create a mock database connection for unit tests."""
    conn = AsyncMock()
    cursor = AsyncMock()

    # Set up cursor as async context manager
    cursor.__aenter__ = AsyncMock(return_value=cursor)
    cursor.__aexit__ = AsyncMock(return_value=None)

    # Set up connection to return cursor
    conn.cursor = AsyncMock(return_value=cursor)

    # Add transaction support
    conn.transaction = AsyncMock()
    conn.transaction.__aenter__ = AsyncMock(return_value=conn)
    conn.transaction.__aexit__ = AsyncMock(return_value=None)

    return conn, cursor


@pytest.fixture
def sample_json_data():
    """Sample JSON data for testing."""
    return {
        "string": "test value",
        "number": 123,
        "boolean": True,
        "null": None,
        "array": [1, 2, 3],
        "object": {"nested": "value"},
    }


@pytest.fixture
def complex_json_data():
    """Complex JSON data with special types."""
    return {"uuid": uuid4(), "datetime": datetime.now(), "nested": {"deep": {"structure": [1, 2, {"key": "value"}]}}}


@pytest.fixture(scope="session")
def jsonb_settings(test_settings: DatabaseSettings) -> DatabaseSettings:
    """Database settings with JSON adapters enabled."""
    # Create new instance with same values
    settings = DatabaseSettings(
        host=test_settings.host,
        port=test_settings.port,
        dbname=test_settings.dbname,
        user=test_settings.user,
        password=test_settings.password,
        enable_json_adapters=True,  # Enable JSON adapters
    )
    return settings


@pytest.fixture
async def jsonb_database(jsonb_settings: DatabaseSettings) -> AsyncGenerator[Database, None]:
    """Database instance with JSON adapters enabled."""
    db = Database(settings=jsonb_settings)
    try:
        await db.create_pool()
        await db.init_db()
        yield db
    finally:
        await db.cleanup()


# JSONB schema fixtures
@pytest.fixture(scope="session")
async def jsonb_schema(postgres_container, test_settings):
    """Create JSONB test schema once per session."""
    db = Database(settings=test_settings)
    await db.init_db()

    async with db.connection() as conn, conn.cursor() as cur:
        # Create all JSONB test tables
        await cur.execute("""
                          CREATE TABLE IF NOT EXISTS user_profiles
                          (
                              id
                              UUID
                              PRIMARY
                              KEY,
                              username
                              VARCHAR
                          (
                              100
                          ) NOT NULL,
                              email VARCHAR
                          (
                              255
                          ) NOT NULL,
                              metadata JSONB NOT NULL,
                              preferences JSONB NOT NULL,
                              tags JSONB NOT NULL,
                              profile_data JSONB,
                              created_at TIMESTAMP NOT NULL,
                              is_active BOOLEAN NOT NULL,
                              age INTEGER
                              );

                          CREATE TABLE IF NOT EXISTS products
                          (
                              id
                              SERIAL
                              PRIMARY
                              KEY,
                              name
                              VARCHAR
                          (
                              255
                          ) NOT NULL,
                              price NUMERIC
                          (
                              10,
                              2
                          ) NOT NULL,
                              specifications JSONB NOT NULL,
                              categories JSONB NOT NULL,
                              inventory JSONB NOT NULL,
                              reviews JSONB NOT NULL,
                              sku VARCHAR
                          (
                              100
                          ) NOT NULL,
                              in_stock BOOLEAN NOT NULL
                              );

                          CREATE TABLE IF NOT EXISTS configurations
                          (
                              id
                              SERIAL
                              PRIMARY
                              KEY,
                              name
                              VARCHAR
                          (
                              255
                          ) NOT NULL,
                              settings JSONB NOT NULL,
                              feature_flags JSONB NOT NULL,
                              allowed_values JSONB NOT NULL,
                              metadata JSONB,
                              empty_dict JSONB NOT NULL,
                              empty_list JSONB NOT NULL
                              );

                          -- Additional tables for edge case testing
                          CREATE TABLE IF NOT EXISTS test_json_types
                          (
                              id
                              SERIAL
                              PRIMARY
                              KEY,
                              json_data
                              JSON,
                              jsonb_data
                              JSONB
                          );

                          CREATE TABLE IF NOT EXISTS transactions_test
                          (
                              id
                              SERIAL
                              PRIMARY
                              KEY,
                              data
                              JSONB
                              NOT
                              NULL,
                              version
                              INTEGER
                              NOT
                              NULL
                              DEFAULT
                              1
                          );
                          """)

    yield

    # Tables will be cleaned up when container stops
    await db.cleanup()


@pytest.fixture
async def jsonb_test_db(db_connection, jsonb_schema):
    """Provides a database connection with JSONB schema in a transaction."""
    # The jsonb_schema ensures tables exist
    # Each test runs in its own transaction that gets rolled back
    async with db_connection.transaction():
        yield db_connection


# Simple JSONB test models


class SimpleJSON(BaseModel):
    """Simple model for basic JSONB testing."""

    id: int | None = None
    data: dict[str, Any]

    model_config = ConfigDict(exclude_none=True)


class ComplexJSON(BaseModel):
    """Model with multiple JSONB fields for complex testing."""

    id: int | None = None
    name: str
    metadata: dict[str, Any]
    tags: list[str] | None = None
    settings: dict[str, Any] | None = None

    model_config = ConfigDict(exclude_none=True)


# JSONB fixtures
@pytest.fixture
async def jsonb_tables(jsonb_database):
    """Provide database connection with JSONB tables already created by init script."""
    async with jsonb_database.connection() as db_connection, db_connection.transaction():
        # Use transaction for automatic cleanup
        yield db_connection
