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
- **JSONB support with automatic field detection and psycopg JSON adapters**
- **Native pgvector support with automatic vector field detection**
- PostgreSQL array field preservation (TEXT[], INTEGER[])
- Automatic date/timestamp conversion for Pydantic models
- SQL query builder with SQL injection protection
- Database schema and test data lifecycle management
- Automatic retry mechanism with exponential backoff
- Granular exception hierarchy for error handling
- Connection health monitoring and validation
- Database initialization callback system
- Statement timeout configuration
- Lossless `Decimal` in JSON fields by default (`decimal_as`)
- `row_to_model()` for custom queries, and pluggable per-field codecs (`field_codecs`)
- Fully typed (`py.typed`), checked with pyright and ty

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
from uuid import UUID

from psycopg import AsyncConnection
from pydantic import BaseModel
from psycopg_toolkit import BaseRepository

class User(BaseModel):
    id: UUID
    email: str

class UserRepository(BaseRepository[User, UUID]):  # model type, primary key type
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
    user = await repo.get_by_id(user_id)  # raises RecordNotFoundError if missing
```

For custom queries, fetch rows with `dict_row` and convert them with `row_to_model()`, which applies
the same JSON, vector and date handling as the built-in methods:

```python
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier

class UserRepository(BaseRepository[User, UUID]):
    async def find_by_email(self, email: str) -> User | None:
        query = SQL("SELECT * FROM {} WHERE email = %s").format(Identifier(self.table_name))
        async with self.db_connection.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, [email])
            row = await cur.fetchone()
            return self.row_to_model(row) if row else None
```

### JSONB Support

```python
from typing import Any
from pydantic import BaseModel
from psycopg_toolkit import BaseRepository

class UserProfile(BaseModel):
    id: int
    name: str
    # These fields are automatically detected as JSONB
    metadata: dict[str, Any]
    preferences: dict[str, str]
    tags: list[str]

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

A `Decimal` inside a JSON field is stored as a JSON string, so no digits are lost; pass
`decimal_as="float"` for a JSON number. See [JSONB Support](docs/jsonb_support.md).

### PostgreSQL Arrays and Date Fields

```python
from typing import Any
from uuid import UUID, uuid4
from pydantic import BaseModel
from psycopg_toolkit import BaseRepository

class User(BaseModel):
    id: UUID
    username: str
    roles: list[str]          # PostgreSQL TEXT[] array
    permissions: list[str]    # PostgreSQL TEXT[] array
    metadata: dict[str, Any]  # JSONB field
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
    JSONSerializationError,
    RecordNotFoundError,
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


## Testing with psycopg-toolkit

A connection pool belongs to the event loop that opened it: its background workers run as tasks in
that loop. pytest-asyncio gives each test its own loop by default, so a pool has to live in the same
loop as the tests that use it.

### Recommended: a `Database` per test

Start the PostgreSQL container once per session (a plain, synchronous fixture), and create the
`Database` in each test's own loop. This is how this project's own test suite works.

```python
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from testcontainers.community.postgres import PostgresContainer

from psycopg_toolkit import Database, DatabaseSettings


@pytest.fixture(scope="session")
def db_settings() -> Generator[DatabaseSettings, None, None]:
    with PostgresContainer("pgvector/pgvector:pg18") as pg:
        yield DatabaseSettings(
            host=pg.get_container_host_ip(),
            port=int(pg.get_exposed_port(5432)),
            dbname=pg.dbname,
            user=pg.username,
            password=pg.password,
            min_pool_size=1,
            max_pool_size=4,
        )


@pytest_asyncio.fixture
async def db(db_settings: DatabaseSettings) -> AsyncGenerator[Database, None]:
    database = Database(db_settings)
    await database.init_db()
    yield database
    await database.cleanup()


async def test_select(db: Database) -> None:
    async with db.connection() as conn:
        row = await (await conn.execute("SELECT 1")).fetchone()
    assert row == (1,)
```

Opening a small pool per test costs milliseconds against a local container. If anything else that
uses the pool (an ASGI test server, a worker) is a fixture too, make it depend on `db`, so pytest
stops it before the pool closes.

### Sharing one pool: share one loop

To reuse a pool across tests, run the fixture and those tests in the same session-scoped loop:

```python
@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def shared_db(db_settings: DatabaseSettings) -> AsyncGenerator[Database, None]:
    database = Database(db_settings)
    await database.init_db()
    yield database
    await database.cleanup()


@pytest.mark.asyncio(loop_scope="session")
async def test_with_shared_pool(shared_db: Database) -> None:
    async with shared_db.connection() as conn:
        await conn.execute("SELECT 1")
```

Every test that uses `shared_db` needs `loop_scope="session"` (or set
`asyncio_default_test_loop_scope = "session"` in the pytest configuration). Tests then share state,
so use transactions that roll back to keep them independent.

### Don't: open the pool with `asyncio.run()` in a fixture

```python
@pytest.fixture(scope="session")
def db(db_settings):
    database = Database(db_settings)
    asyncio.run(database.get_pool())  # the pool's loop closes when asyncio.run() returns
    yield database
    asyncio.run(database.cleanup())
```

`asyncio.run()` closes its loop on return, which stops the pool's workers. Tests running in their
own loops then wait for connections that never arrive: with pytest-asyncio 1.5 and psycopg-pool
3.3 the first test hangs.

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
- **Integration tests**: Tests that require a real PostgreSQL database (in `tests/integration/`, using testcontainers)
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
