"""Basic usage example of psycopg-toolkit."""

import asyncio

from testcontainers.community.postgres import PostgresContainer

from psycopg_toolkit import Database, DatabaseSettings


async def main():
    # Initialize postgres container
    with PostgresContainer("postgres:18") as container:
        settings = DatabaseSettings(
            host=container.get_container_host_ip(),
            port=container.get_exposed_port(5432),
            dbname=container.dbname,
            user=container.username,
            password=container.password,
        )

        # Create database instance
        db = Database(settings)

        try:
            # Initialize the database pool
            await db.init_db()

            # Use a connection from the pool
            async with db.connection() as conn, conn.cursor() as cur:
                # Execute a simple query
                await cur.execute("SELECT version();")
                version = await cur.fetchone()
                assert version is not None
                print(f"PostgreSQL version:\n{version[0]}")

        finally:
            # Clean up resources
            await db.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
