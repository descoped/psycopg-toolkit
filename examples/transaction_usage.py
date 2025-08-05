"""Transaction usage example of psycopg-toolkit."""

import asyncio

from testcontainers.postgres import PostgresContainer

from psycopg_toolkit import Database, DatabaseSettings


async def single_transaction():
    # Initialize postgres container
    with PostgresContainer("postgres:17") as container:
        settings = DatabaseSettings(
            host=container.get_container_host_ip(),
            port=container.get_exposed_port(5432),
            dbname=container.dbname,
            user=container.username,
            password=container.password,
        )

        # Setup database
        db = Database(settings)
        await db.init_db()

        try:
            tm = await db.get_transaction_manager()
            async with tm.transaction() as conn, conn.cursor() as cur:
                # Create table transaction
                await cur.execute("""
                        CREATE TABLE users (
                            id SERIAL PRIMARY KEY,
                            name VARCHAR(100),
                            status VARCHAR(50) DEFAULT 'inactive'
                        )
                    """)
                await cur.execute("INSERT INTO users (name) VALUES (%s)", ["John"])
                await cur.execute("UPDATE users SET status = 'active' WHERE name = %s", ["John"])
                await cur.execute("SELECT * FROM users")
                rows = await cur.fetchall()
                print("Users:", rows)
            # If any operation fails, the entire transaction is rolled back
        except Exception as e:
            print(f"Transaction failed: {e}")
        finally:
            await db.cleanup()


async def multiple_transactions():
    # Initialize postgres container
    with PostgresContainer("postgres:17") as container:
        settings = DatabaseSettings(
            host=container.get_container_host_ip(),
            port=container.get_exposed_port(5432),
            dbname=container.dbname,
            user=container.username,
            password=container.password,
        )

        # Setup database
        db = Database(settings)
        await db.init_db()

        try:
            tm = await db.get_transaction_manager()
            async with tm.transaction() as conn, conn.cursor() as cur:
                # Create table transaction
                await cur.execute("""
                        CREATE TABLE users (
                            id SERIAL PRIMARY KEY,
                            name VARCHAR(100),
                            status VARCHAR(50) DEFAULT 'inactive'
                        )
                    """)

            async with tm.transaction() as conn, conn.cursor() as cur:
                # Insert user transaction
                await cur.execute("INSERT INTO users (name) VALUES (%s)", ["John"])

            async with tm.transaction() as conn, conn.cursor() as cur:
                # Update user status transaction
                await cur.execute("UPDATE users SET status = 'active' WHERE name = %s", ["John"])

            async with tm.transaction() as conn, conn.cursor() as cur:
                # Fetch and print all rows transaction
                await cur.execute("SELECT * FROM users")
                rows = await cur.fetchall()
                print("Users:", rows)
            # If any operation fails, the entire transaction is rolled back
        except Exception as e:
            print(f"Transaction failed: {e}")
        finally:
            await db.cleanup()


async def main():
    await single_transaction()
    await multiple_transactions()


if __name__ == "__main__":
    asyncio.run(main())
