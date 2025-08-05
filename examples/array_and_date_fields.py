"""
Example demonstrating array_fields and date_fields parameters.

This example shows how to:
1. Use array_fields to preserve PostgreSQL arrays instead of JSONB
2. Use date_fields for automatic date/string conversion
3. Mix JSONB, arrays, and date fields in one model

Note: You may see "Failed to deserialize JSON field" warnings when running this example.
These are expected when using auto_detect_json=True with psycopg's JSON adapters enabled,
as the data is already deserialized by psycopg. The warnings can be safely ignored.
"""

import asyncio
import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field
from testcontainers.postgres import PostgresContainer

from psycopg_toolkit import BaseRepository, Database, DatabaseSettings


# Example 1: OAuth Client with PostgreSQL arrays
class OAuthClient(BaseModel):
    """OAuth client model with array fields."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    client_id: str
    client_name: str

    # These will be PostgreSQL arrays, not JSONB
    redirect_uris: list[str]
    grant_types: list[str]
    scopes: list[str]

    # This will be JSONB
    metadata: dict[str, Any]

    # Date fields (note: these should be TIMESTAMP in real apps)
    created_at: str  # ISO datetime string
    updated_at: str | None = None


class OAuthClientRepository(BaseRepository[OAuthClient, uuid.UUID]):
    """Repository demonstrating array_fields usage."""

    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="oauth_clients",
            model_class=OAuthClient,
            primary_key="id",
            auto_detect_json=True,  # Will detect all list/dict fields
            # Specify which fields should remain as PostgreSQL arrays
            array_fields={"redirect_uris", "grant_types", "scopes"},
            # Specify date fields for automatic conversion
            date_fields={"created_at", "updated_at"},
        )


# Example 2: User with mixed field types
class User(BaseModel):
    """User model with various field types."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    username: str
    email: str

    # Date fields (as strings in model)
    birthdate: str | None = None  # DATE column
    created_at: str  # TIMESTAMP column
    updated_at: str  # TIMESTAMP column
    last_login: str | None = None  # TIMESTAMP column (nullable)

    # PostgreSQL array
    roles: list[str]

    # JSONB fields
    profile: dict[str, Any]
    settings: dict[str, str]


class UserRepository(BaseRepository[User, uuid.UUID]):
    """Repository with all field type configurations."""

    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="users",
            model_class=User,
            primary_key="id",
            auto_detect_json=True,
            array_fields={"roles"},  # Keep roles as PostgreSQL array
            date_fields={"birthdate", "created_at", "updated_at", "last_login"},  # Convert ALL date/timestamp fields
        )


async def setup_database(container_db_url: str):
    """Create database tables."""
    # Parse the connection URL
    # Format: postgresql+psycopg2://user:password@host:port/dbname
    from urllib.parse import urlparse

    parsed = urlparse(container_db_url.replace("postgresql+psycopg2", "postgresql"))

    settings = DatabaseSettings(
        host=parsed.hostname,
        port=parsed.port,
        dbname=parsed.path.lstrip("/"),
        user=parsed.username,
        password=parsed.password,
    )
    db = Database(settings=settings)
    await db.init_db()

    async with db.connection() as conn:
        # Create OAuth clients table with arrays
        await conn.execute("""
            CREATE TABLE oauth_clients (
                id UUID PRIMARY KEY,
                client_id VARCHAR(255) UNIQUE NOT NULL,
                client_name VARCHAR(255) NOT NULL,
                redirect_uris TEXT[],
                grant_types TEXT[],
                scopes TEXT[],
                metadata JSONB NOT NULL,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP
            )
        """)

        # Create users table with mixed types
        await conn.execute("""
            CREATE TABLE users (
                id UUID PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                birthdate DATE,
                created_at TIMESTAMP NOT NULL,
                updated_at TIMESTAMP NOT NULL,
                last_login TIMESTAMP,
                roles TEXT[] NOT NULL,
                profile JSONB NOT NULL,
                settings JSONB NOT NULL
            )
        """)

        await conn.commit()

    return db


async def demo_array_fields(db: Database):
    """Demonstrate array field handling."""
    print("\n=== Array Fields Demo ===")

    async with db.connection() as conn:
        repo = OAuthClientRepository(conn)

        # Create client with arrays
        client = OAuthClient(
            client_id="my-app-123",
            client_name="My Application",
            redirect_uris=["https://myapp.com/callback", "https://myapp.com/auth/callback"],
            grant_types=["authorization_code", "refresh_token"],
            scopes=["read", "write", "admin"],
            metadata={"owner": "john@example.com", "tier": "premium", "features": ["sso", "webhooks"]},
            created_at=datetime.now().isoformat(),
        )

        # Create in database
        created = await repo.create(client)
        print(f"Created client: {created.client_id}")
        print(f"  Redirect URIs (array): {created.redirect_uris}")
        print(f"  Metadata (JSONB): {created.metadata}")

        # Verify arrays are stored correctly
        result = await conn.execute("SELECT redirect_uris, grant_types FROM oauth_clients WHERE id = %s", [created.id])
        row = await result.fetchone()
        print("\nDirect DB query - Arrays preserved:")
        print(f"  redirect_uris: {row[0]} (type: {type(row[0])})")
        print(f"  grant_types: {row[1]} (type: {type(row[1])})")

        # Update arrays
        updated = await repo.update(
            created.id, {"scopes": ["read", "write", "admin", "delete"], "updated_at": datetime.now().isoformat()}
        )
        print(f"\nUpdated scopes: {updated.scopes}")


async def demo_date_fields(db: Database):
    """Demonstrate date field handling."""
    print("\n=== Date Fields Demo ===")

    async with db.connection() as conn:
        repo = UserRepository(conn)

        # Create user with dates as strings
        user = User(
            username="johndoe",
            email="john@example.com",
            birthdate="1990-05-15",  # DATE field
            created_at=datetime.now().isoformat(),  # TIMESTAMP field
            updated_at=datetime.now().isoformat(),  # TIMESTAMP field
            last_login=datetime.now().isoformat(),  # TIMESTAMP field (nullable)
            roles=["user", "moderator"],
            profile={"bio": "Software developer", "location": "San Francisco"},
            settings={"theme": "dark", "notifications": "enabled"},
        )

        created = await repo.create(user)
        print(f"Created user: {created.username}")
        print(f"  Birthdate (string): {created.birthdate}")
        print(f"  Roles (array): {created.roles}")

        # Insert directly with PostgreSQL date
        user_id = uuid.uuid4()
        import json

        await conn.execute(
            """
            INSERT INTO users (id, username, email, birthdate, created_at, updated_at, last_login, roles, profile, settings)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb)
        """,
            [
                user_id,
                "janedoe",
                "jane@example.com",
                date(1985, 3, 20),  # PostgreSQL date object
                datetime.now(),  # PostgreSQL datetime object
                datetime.now(),  # PostgreSQL datetime object
                datetime.now(),  # PostgreSQL datetime object
                ["user", "admin"],
                json.dumps({"bio": "Data scientist"}),
                json.dumps({"theme": "light"}),
            ],
        )
        await conn.commit()

        # Retrieve - dates are automatically converted to strings
        jane = await repo.get_by_id(user_id)
        print(f"\nRetrieved user: {jane.username}")
        print(f"  Birthdate: {jane.birthdate} (type: {type(jane.birthdate)})")
        print(f"  Last login: {jane.last_login} (type: {type(jane.last_login)})")


async def main():
    """Run the examples."""
    # Use testcontainers for a temporary PostgreSQL instance
    with PostgresContainer("postgres:17") as postgres:
        container_db_url = postgres.get_connection_url()
        print(f"Container started: {container_db_url}")

        # Setup database
        db = await setup_database(container_db_url)

        try:
            # Run demos
            await demo_array_fields(db)
            await demo_date_fields(db)

        finally:
            await db.cleanup()
            print("\n✓ Examples completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
