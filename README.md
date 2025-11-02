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


## Testing with Async Libraries

### Understanding the pytest and Async Boundary

When testing async libraries like `async-task-worker` or database libraries (e.g., `psycopg-toolkit`), you'll encounter a fundamental challenge: pytest's session-scoped fixtures are synchronous, while modern libraries are increasingly async. This section explains the problem and provides the recommended patterns for handling this boundary.

#### The Core Problem

pytest's fixture system was designed before async became prevalent in Python:
- **Session fixtures are synchronous**: They run once per test session and must be sync functions
- **Modern libraries are async**: Database pools, task workers, and connections require `await`
- **Resource efficiency matters**: You want to reuse expensive resources (containers, pools) across tests

This creates an awkward boundary where you need async resources in sync fixture setup.

#### The Standard Solution: `asyncio.run()`

The accepted pattern in the Python testing community is using `asyncio.run()` in session fixtures. While it may feel inelegant, this is the recommended approach documented in pytest-asyncio's own examples.

```python
import pytest
import asyncio
from async_task_worker import AsyncTaskWorker

@pytest.fixture(scope="session")
def worker():
    """Session-scoped worker for test efficiency.
    
    This uses asyncio.run() to bridge the sync/async boundary.
    This is the standard pattern for async resources in session fixtures.
    """
    # Create the worker
    worker = AsyncTaskWorker(max_workers=5)
    
    # Start it using asyncio.run() - the standard workaround
    asyncio.run(worker.start())
    
    yield worker
    
    # Cleanup
    asyncio.run(worker.stop())

# Your async tests can then use the worker normally
@pytest.mark.asyncio
async def test_task_execution(worker):
    task_id = await worker.add_task(my_task, data)
    result = await worker.get_task_future(task_id)
    assert result == expected
```

### Complete Testing Pattern

Here's a comprehensive example showing best practices for testing async-task-worker:

```python
import pytest
import pytest_asyncio
import asyncio
from datetime import datetime
from async_task_worker import AsyncTaskWorker, task, TaskStatus

# ============================================================
# Session Fixtures (Synchronous with asyncio.run())
# ============================================================

@pytest.fixture(scope="session")
def event_loop_policy():
    """Use a specific event loop policy for tests."""
    return asyncio.get_event_loop_policy()

@pytest.fixture(scope="session")
def worker():
    """Create a session-scoped worker instance.
    
    Note: We use asyncio.run() here because session fixtures
    must be synchronous. This is the standard pattern.
    """
    worker = AsyncTaskWorker(
        max_workers=3,
        task_timeout=10,
        cache_enabled=True,
        cache_ttl=60
    )
    
    # Start the worker using asyncio.run()
    asyncio.run(worker.start())
    
    yield worker
    
    # Cleanup
    asyncio.run(worker.stop())

# ============================================================
# Function-Scoped Async Fixtures (Can use async/await)
# ============================================================

@pytest_asyncio.fixture
async def clean_worker(worker):
    """Provides a clean worker state for each test."""
    # Clear any existing tasks
    tasks = worker.get_all_tasks()
    for task in tasks:
        if task.status in ("pending", "running"):
            await worker.cancel_task(task.id)
    
    # Clear cache if enabled
    if worker.cache:
        await worker.clear_cache()
    
    yield worker
    
    # Post-test cleanup if needed
    # ...

# ============================================================
# Test Task Definitions
# ============================================================

@task("test_computation")
async def test_computation(value, delay=0.1, progress_callback=None):
    """A test task that simulates computation."""
    steps = 5
    result = value
    
    for i in range(steps):
        await asyncio.sleep(delay)
        result = result * 2
        
        if progress_callback:
            progress_callback((i + 1) / steps)
    
    return result

@task("test_failing_task")
async def test_failing_task(should_fail=True):
    """A task that can be configured to fail."""
    if should_fail:
        raise ValueError("Task failed as expected")
    return "success"

# ============================================================
# Test Cases
# ============================================================

@pytest.mark.asyncio
async def test_basic_task_execution(clean_worker):
    """Test basic task execution flow."""
    # Add a task
    task_id = await clean_worker.add_task(
        test_computation,
        value=2,
        delay=0.01
    )
    
    # Wait for completion
    result = await clean_worker.get_task_future(task_id)
    
    # Verify result (2 * 2^5 = 64)
    assert result == 64
    
    # Check task info
    info = clean_worker.get_task_info(task_id)
    assert info.status == TaskStatus.COMPLETED
    assert info.progress == 1.0

@pytest.mark.asyncio
async def test_task_cancellation(clean_worker):
    """Test task cancellation."""
    # Start a long-running task
    task_id = await clean_worker.add_task(
        test_computation,
        value=1,
        delay=1.0  # Long delay
    )
    
    # Cancel it
    cancelled = await clean_worker.cancel_task(task_id)
    assert cancelled
    
    # Verify status
    info = clean_worker.get_task_info(task_id)
    assert info.status == TaskStatus.CANCELLED

@pytest.mark.asyncio
async def test_cache_functionality(clean_worker):
    """Test caching of task results."""
    # First execution
    task_id1 = await clean_worker.add_task(
        test_computation,
        value=3,
        delay=0.01,
        use_cache=True
    )
    result1 = await clean_worker.get_task_future(task_id1)
    
    # Second execution with same args (should hit cache)
    start_time = datetime.now()
    task_id2 = await clean_worker.add_task(
        test_computation,
        value=3,
        delay=0.01,  # This delay won't happen due to cache
        use_cache=True
    )
    result2 = await clean_worker.get_task_future(task_id2)
    elapsed = (datetime.now() - start_time).total_seconds()
    
    # Results should match
    assert result1 == result2
    
    # Second execution should be much faster (cache hit)
    assert elapsed < 0.05  # Much less than the task delay

@pytest.mark.asyncio
async def test_concurrent_tasks(clean_worker):
    """Test concurrent task execution."""
    # Add multiple tasks
    task_ids = []
    for i in range(5):
        task_id = await clean_worker.add_task(
            test_computation,
            value=i,
            delay=0.01
        )
        task_ids.append(task_id)
    
    # Wait for all to complete
    futures = clean_worker.get_task_futures(task_ids)
    results = await asyncio.gather(*futures)
    
    # Verify all completed
    assert len(results) == 5
    for i, result in enumerate(results):
        assert result == i * (2 ** 5)

# ============================================================
# Testing Utilities
# ============================================================

class TaskMonitor:
    """Utility class for monitoring task execution in tests."""
    
    def __init__(self, worker: AsyncTaskWorker):
        self.worker = worker
        self.events = []
    
    async def monitor_task(self, task_id: str, timeout: float = 5.0):
        """Monitor a task until completion or timeout."""
        start_time = asyncio.get_event_loop().time()
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            info = self.worker.get_task_info(task_id)
            self.events.append({
                "time": asyncio.get_event_loop().time() - start_time,
                "status": info.status,
                "progress": info.progress
            })
            
            if info.status not in ("pending", "running"):
                return info
            
            await asyncio.sleep(0.1)
        
        raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")

@pytest.mark.asyncio
async def test_with_monitor(clean_worker):
    """Example of using the TaskMonitor utility."""
    monitor = TaskMonitor(clean_worker)
    
    task_id = await clean_worker.add_task(
        test_computation,
        value=5,
        delay=0.1
    )
    
    # Monitor the task
    final_info = await monitor.monitor_task(task_id)
    
    # Check the monitoring captured progress
    assert len(monitor.events) > 0
    assert final_info.status == TaskStatus.COMPLETED
    
    # Verify progress increased over time
    progresses = [e["progress"] for e in monitor.events]
    assert progresses[-1] == 1.0
```

### Testing with Database Libraries (e.g., psycopg-toolkit)

The same pattern applies when testing with async database libraries:

```python
import pytest
import asyncio
from psycopg_toolkit import Database

@pytest.fixture(scope="session")
def db():
    """Session-scoped database connection.
    
    Uses asyncio.run() to handle async operations in sync fixture.
    This is the standard pattern for pytest with async resources.
    """
    db = Database("postgresql://user:pass@localhost/test")
    
    # Create the pool synchronously using asyncio.run()
    asyncio.run(db.get_pool())
    
    yield db
    
    # Cleanup
    asyncio.run(db.cleanup())

@pytest.fixture(scope="function")
async def db_connection(db):
    """Function-scoped connection from the session pool."""
    async with db.connection() as conn:
        yield conn
        # Automatic cleanup via context manager
```

### Key Takeaways

1. **The `asyncio.run()` pattern is correct**: Don't feel bad about using it in session fixtures - it's the standard solution
2. **Session vs Function Scope**: Use session fixtures for expensive resources (pools, workers) and function fixtures for cleanup
3. **The awkwardness is pytest's limitation, not your design**: Your async library doesn't need sync wrappers
4. **Document the pattern**: Help users understand why `asyncio.run()` appears in test fixtures

### Additional Testing Resources

- **pytest-asyncio**: The standard pytest plugin for async testing
- **pytest-timeout**: Useful for preventing hanging async tests
- **asyncio-test**: Utilities for testing asyncio code
- **Testing async generators**: Use `async for` in tests or `aioitertools` for utilities

### Common Pitfalls and Solutions

#### Pitfall 1: Event Loop Conflicts
```python
# Wrong - Creates new event loop
def test_something():
    loop = asyncio.new_event_loop()
    loop.run_until_complete(my_async_func())

# Right - Use pytest-asyncio
@pytest.mark.asyncio
async def test_something():
    await my_async_func()
```

#### Pitfall 2: Forgetting Cleanup
```python
# Wrong - No cleanup
@pytest.fixture
def worker():
    w = AsyncTaskWorker()
    asyncio.run(w.start())
    return w

# Right - Proper cleanup
@pytest.fixture
def worker():
    w = AsyncTaskWorker()
    asyncio.run(w.start())
    yield w
    asyncio.run(w.stop())
```

#### Pitfall 3: Mixing Sync and Async Incorrectly
```python
# Wrong - Can't await in sync function
def test_task(worker):
    result = await worker.add_task(...)  # SyntaxError

# Right - Mark as async test
@pytest.mark.asyncio
async def test_task(worker):
    result = await worker.add_task(...)
```

By following these patterns, you can effectively test async-task-worker and similar async libraries while maintaining clean, efficient test suites.


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
