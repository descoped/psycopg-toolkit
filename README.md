# Psycopg Toolkit

[![Build Status](https://github.com/descoped/psycopg-toolkit/actions/workflows/build-test.yml/badge.svg)](https://github.com/descoped/psycopg-toolkit/actions/workflows/build-test-native.yml)
[![Coverage](https://codecov.io/gh/descoped/psycopg-toolkit/branch/master/graph/badge.svg)](https://codecov.io/gh/descoped/psycopg-toolkit)
[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Release](https://img.shields.io/github/v/release/descoped/psycopg-toolkit)](https://github.com/descoped/psycopg-toolkit/releases)

A robust PostgreSQL database toolkit providing enterprise-grade connection pooling and database management capabilities for Python applications.

## Features

- Async-first design with connection pooling via `psycopg-pool`
- Comprehensive transaction management with savepoint support
- Type-safe repository pattern with Pydantic model validation
- JSONB support with automatic field detection and psycopg JSON adapters
- PostgreSQL array field preservation (TEXT[], INTEGER[])
- Automatic date/timestamp conversion for Pydantic models
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

### JSONB Support

```python
from typing import Dict, List, Any
from pydantic import BaseModel
from psycopg_toolkit import BaseRepository

class UserProfile(BaseModel):
    id: int
    name: str
    # These fields are automatically detected as JSONB
    metadata: Dict[str, Any]
    preferences: Dict[str, str]
    tags: List[str]

class UserRepository(BaseRepository[UserProfile, int]):
    def __init__(self, conn):
        super().__init__(
            db_connection=conn,
            table_name="user_profiles",
            model_class=UserProfile,
            primary_key="id"
            # auto_detect_json=True by default
        )

# Usage - JSON fields handled automatically
user = UserProfile(
    id=1,
    name="John Doe",
    metadata={"created_at": "2024-01-01", "source": "web"},
    preferences={"theme": "dark", "language": "en"},
    tags=["premium", "beta_tester"]
)

# JSONB fields automatically serialized/deserialized
created_user = await repo.create(user)
retrieved_user = await repo.get_by_id(1)
```

### PostgreSQL Arrays and Date Fields

```python
from typing import List
from datetime import date
from pydantic import BaseModel
from psycopg_toolkit import BaseRepository

class User(BaseModel):
    id: UUID
    username: str
    roles: List[str]          # PostgreSQL TEXT[] array
    permissions: List[str]    # PostgreSQL TEXT[] array
    metadata: Dict[str, Any]  # JSONB field
    birthdate: str            # ISO date string (from DATE)
    created_at: str           # ISO datetime string (from TIMESTAMP)
    updated_at: str           # ISO datetime string (from TIMESTAMPTZ)
    last_login: str | None    # Optional timestamp field

class UserRepository(BaseRepository[User, UUID]):
    def __init__(self, conn):
        super().__init__(
            db_connection=conn,
            table_name="users",
            model_class=User,
            primary_key="id",
            # Preserve PostgreSQL arrays instead of JSONB
            array_fields={"roles", "permissions"},
            # Auto-convert ALL date/timestamp fields to/from strings
            date_fields={"birthdate", "created_at", "updated_at", "last_login"}
        )

# PostgreSQL arrays are preserved, dates are auto-converted
user = User(
    id=uuid4(),
    username="john",
    roles=["admin", "user"],      # Stored as TEXT[]
    permissions=["read", "write"], # Stored as TEXT[]
    metadata={"dept": "IT"},       # Stored as JSONB
    birthdate="1990-01-01",           # Converts to/from PostgreSQL DATE
    created_at="2024-01-01T12:00:00", # Converts to/from TIMESTAMP
    updated_at="2024-01-01T12:00:00", # Converts to/from TIMESTAMPTZ
    last_login=None                   # Nullable timestamp field
)
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

- [Database Management](docs/database.md)
- [Transaction Management](docs/transaction_manager.md)
- [Base Repository](docs/base_repository.md)
- [JSONB Support](docs/jsonb_support.md)
- [PsycopgHelper](docs/psycopg_helper.md)

## Running Tests

```bash
# Install dependencies
uv sync --all-groups

# Run all tests except performance tests (default)
uv run pytest

# Run only performance tests
uv run pytest -m performance

# Run all tests including performance
uv run pytest -m ""

# Run specific test categories
uv run pytest tests/unit/  # Only unit tests
uv run pytest -m performance  # Only performance tests

# Run with coverage
uv run pytest --cov=src/psycopg_toolkit --cov-report=html
```

### Test Categories

The test suite is organized into three categories:

- **Unit tests**: Fast, isolated tests that don't require a database (in `tests/unit/`)
- **Integration tests**: Tests that require a real PostgreSQL database (in `tests/` root)
- **Performance tests**: Benchmarks and performance measurements (marked with `@pytest.mark.performance`)

Performance tests are excluded by default to keep the regular test runs fast. Use the `-m performance` flag to run them explicitly.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Ensure all tests pass
5. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
