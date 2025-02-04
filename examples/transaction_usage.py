"""Transaction usage example of PsycoDB."""

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

    # Setup database
    db = Database(settings)
    await db.init_db()

    try:
        async with db.transaction_manager.transaction() as conn:
            async with conn.cursor() as cur:
                await cur.execute("INSERT INTO users (name) VALUES (%s)", ["John"])
                await cur.execute("UPDATE users SET status = 'active' WHERE name = %s", ["John"])
                # If any operation fails, the entire transaction is rolled back
    except Exception as e:
        print(f"Transaction failed: {e}")
    finally:
        await db.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
