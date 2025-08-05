from psycopg import AsyncConnection

from psycopg_toolkit.core.transaction import DataManager, SchemaManager


class UserSchemaManager(SchemaManager[None]):
    async def create_schema(self, conn: AsyncConnection) -> None:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """)

    async def drop_schema(self, conn: AsyncConnection) -> None:
        await conn.execute("DROP TABLE IF EXISTS users;")


class TestUserData(DataManager[dict]):
    def __init__(self, test_users: list[dict]):
        self.test_users = test_users

    async def setup_data(self, conn: AsyncConnection) -> dict:
        async with conn.cursor() as cur:
            for user in self.test_users:
                await cur.execute("INSERT INTO users (id, email) VALUES (%s, %s)", (user["id"], user["email"]))
        return {"users": self.test_users}

    async def cleanup_data(self, conn: AsyncConnection) -> None:
        await conn.execute("DELETE FROM users;")
