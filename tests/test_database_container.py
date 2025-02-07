import pytest
from psycopg import AsyncConnection, AsyncTransaction
from psycopg_pool import AsyncConnectionPool
from testcontainers.postgres import PostgresContainer

from psycopg_toolkit import DatabaseSettings, TransactionManager


@pytest.mark.asyncio
def test_container(postgres_container: PostgresContainer):
    print(f"\nPostgres URL: {postgres_container.get_connection_url()}")


@pytest.mark.asyncio
def test_database_settings(test_settings: DatabaseSettings):
    print(f"\fDatabase settings: {test_settings}")


@pytest.mark.asyncio
async def test_db_pool(db_pool: AsyncConnectionPool):
    async with db_pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
            print("SELECT 1: success")


@pytest.mark.asyncio
async def test_database(db_connection: AsyncConnection):
    async with db_connection.cursor() as cur:
        await cur.execute("SELECT 1")
        print("\nSELECT 1: success")


@pytest.mark.asyncio
async def test_transaction(transaction: AsyncTransaction):
    async with transaction.connection.cursor() as cur:
        await cur.execute("SELECT 1")
        print("\nSELECT 1: success")


@pytest.mark.asyncio
async def test_with_transaction(transaction_manager: TransactionManager):
    async with transaction_manager.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
            print("\nSELECT 1: success")
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
            print("\nSELECT 1: 2nd success")


@pytest.mark.asyncio
async def test_users(transaction_manager: TransactionManager, setup_test_db):
    test_user = setup_test_db

    async with transaction_manager.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT id, email FROM users WHERE id = %s", (test_user['id'],))
            result = await cur.fetchone()
            assert result is not None
            assert str(result[0]) == str(test_user['id'])
            assert result[1] == test_user['email']
