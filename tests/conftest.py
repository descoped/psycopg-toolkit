from typing import Generator, AsyncGenerator, Optional
from uuid import uuid4

import pytest
from psycopg import AsyncConnection, AsyncTransaction
from psycopg_pool import AsyncConnectionPool
from testcontainers.postgres import PostgresContainer

from psycopg_toolkit import DatabaseSettings, Database, TransactionManager
from schema_and_data import UserSchemaManager, TestUserData

_db: Optional[Database] = None


@pytest.fixture(scope="session")
def postgres_container() -> Generator[PostgresContainer, None, None]:
    with PostgresContainer("postgres:17") as container:
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
            raise e

    yield _db

    if _db is not None:
        await _db.cleanup()
        _db = None


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
