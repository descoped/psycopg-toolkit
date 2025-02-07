# Psycopg Toolkit

A robust PostgreSQL database toolkit providing enterprise-grade connection pooling and database management capabilities for Python applications.

## Features

- Async-first design with connection pooling via `psycopg-pool`
- Comprehensive transaction management with savepoint support
- Type-safe repository pattern with Pydantic model validation
- SQL query builder with SQL injection protection
- Database schema and test data lifecycle management
- Automatic retry mechanism with exponential backoff
- Granular exception hierarchy for error handling
- Connection health monitoring and validation
- Database initialization callback system
- Statement timeout configuration
- Fully typed with modern Python type hints

## Installation

```bash
pip install psycopg-toolkit
```

## Quick Start

```python
from psycopg_toolkit import Database, DatabaseSettings
from uuid import uuid4

# Configure database
settings = DatabaseSettings(
    host="localhost",
    port=5432,
    dbname="your_database",
    user="your_user",
    password="your_password"
)

async def main():
    # Initialize database
    db = Database(settings)
    await db.init_db()
    
    # Get transaction manager
    tm = await db.get_transaction_manager()
    
    # Execute in transaction
    async with tm.transaction() as conn:
        async with conn.cursor() as cur:
            user_id = uuid4()
            await cur.execute(
                "INSERT INTO users (id, email) VALUES (%s, %s)",
                (user_id, "user@example.com")
            )
    
    # Clean up
    await db.cleanup()
```

## Core Components

### Database Management

```python
# Health check
is_healthy = await db.check_pool_health()

# Connection management
async with db.connection() as conn:
    async with conn.cursor() as cur:
        await cur.execute("SELECT version()")
```

### Transaction Management

```python
# Basic transaction
async with tm.transaction() as conn:
    # Operations automatically rolled back on error
    pass

# With savepoint
async with tm.transaction(savepoint="user_creation") as conn:
    # Nested transaction using savepoint
    pass
```

### Repository Pattern

```python
from pydantic import BaseModel
from psycopg_toolkit import BaseRepository

class User(BaseModel):
    id: UUID
    email: str

class UserRepository(BaseRepository[User]):
    def __init__(self, conn: AsyncConnection):
        super().__init__(
            db_connection=conn,
            table_name="users",
            model_class=User,
            primary_key="id"
        )

# Usage
async with tm.transaction() as conn:
    repo = UserRepository(conn)
    user = await repo.get_by_id(user_id)
```

### Schema Management

```python
from psycopg_toolkit.core.transaction import SchemaManager

class UserSchemaManager(SchemaManager[None]):
    async def create_schema(self, conn: AsyncConnection) -> None:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY,
                email TEXT UNIQUE NOT NULL
            )
        """)

    async def drop_schema(self, conn: AsyncConnection) -> None:
        await conn.execute("DROP TABLE IF EXISTS users")

# Usage
async with tm.with_schema(UserSchemaManager()) as _:
    # Schema available here
    pass  # Automatically dropped after
```

## Error Handling

```python
from psycopg_toolkit import (
    DatabaseConnectionError,
    DatabasePoolError,
    DatabaseNotAvailable,
    RecordNotFoundError
)

try:
    async with tm.transaction() as conn:
        repo = UserRepository(conn)
        user = await repo.get_by_id(user_id)
except DatabaseConnectionError as e:
    print(f"Connection error: {e.original_error}")
except RecordNotFoundError:
    print(f"User {user_id} not found")
```

## Documentation

- [Database Management](https://github.com/descoped/psycopg-toolkit/blob/master/docs/database.md)
- [Transaction Management](https://github.com/descoped/psycopg-toolkit/blob/master/docs/transaction_manager.md)
- [Base Repository](https://github.com/descoped/psycopg-toolkit/blob/master/docs/base_repository.md)
- [PsycopgHelper](https://github.com/descoped/psycopg-toolkit/blob/master/docs/psycopg_helper.md)

## Running Tests

```bash
# Install test dependencies
poetry install --with test

# Run tests
poetry run pytest
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
