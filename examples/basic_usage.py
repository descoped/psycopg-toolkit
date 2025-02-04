"""Basic usage example of PsycoDB."""
import asyncio

from psycopg_toolkit import Database, DatabaseSettings


async def main():
    # Initialize database settings
    settings = DatabaseSettings(
        host="localhost",
        port=5432,
        dbname="example",
        user="user",
        password="password"
    )

    # Create database instance
    db = Database(settings)

    try:
        # Initialize the database pool
        await db.init_db()

        # Use a connection from the pool
        async with db.connection() as conn:
            # Execute a simple query
            async with conn.cursor() as cur:
                await cur.execute("SELECT version();")
                version = await cur.fetchone()
                print(f"PostgreSQL version: {version[0]}")

    finally:
        # Clean up resources
        await db.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
