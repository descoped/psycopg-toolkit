# Integration Test Refactoring Plan

## Problem
Each integration test class creates its own PostgreSQL container, causing:
- **Slow test execution**: ~5 seconds per test class just for container startup
- **Resource waste**: Multiple containers running simultaneously
- **Duplicated setup code**: Each test recreates the same schema

## Current State
```python
# Each test does this:
@pytest.fixture
async def test_db():
    with PostgresContainer("postgres:17") as container:  # NEW CONTAINER!
        # ... setup code ...
```

## Solution: Use Shared Fixtures from conftest.py

### Available Fixtures in conftest.py
1. **postgres_container** (session scope) - Single container for all tests
2. **test_settings** (session scope) - Database connection settings
3. **db_connection** (function scope) - Connection per test
4. **transaction** (function scope) - Transaction per test (auto-rollback)
5. **jsonb_database** - Database instance with JSON adapters enabled

### Refactoring Strategy

#### 1. Create Shared Schema Setup
Add to conftest.py:
```python
@pytest.fixture(scope="session")
async def jsonb_schema(postgres_container, test_settings):
    """Create JSONB test schema once per session."""
    db = Database(settings=test_settings)
    await db.init_db()
    
    async with db.connection() as conn:
        async with conn.cursor() as cur:
            # Create all JSONB test tables
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id UUID PRIMARY KEY,
                    username VARCHAR(100) NOT NULL,
                    email VARCHAR(255) NOT NULL,
                    metadata JSONB NOT NULL,
                    preferences JSONB NOT NULL,
                    tags JSONB NOT NULL,
                    profile_data JSONB,
                    created_at TIMESTAMP NOT NULL,
                    is_active BOOLEAN NOT NULL,
                    age INTEGER
                );
                
                CREATE TABLE IF NOT EXISTS products (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    price NUMERIC(10,2) NOT NULL,
                    specifications JSONB NOT NULL,
                    categories JSONB NOT NULL,
                    inventory JSONB NOT NULL,
                    reviews JSONB NOT NULL,
                    sku VARCHAR(100) NOT NULL,
                    in_stock BOOLEAN NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS configurations (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    settings JSONB NOT NULL,
                    feature_flags JSONB NOT NULL,
                    allowed_values JSONB NOT NULL,
                    metadata JSONB,
                    empty_dict JSONB NOT NULL,
                    empty_list JSONB NOT NULL
                );
            """)
    
    yield
    
    # Cleanup after all tests
    await db.cleanup()
```

#### 2. Use Transaction Isolation
Each test should use a transaction that gets rolled back:
```python
@pytest.mark.asyncio
async def test_something(db_connection, jsonb_schema):
    async with db_connection.transaction():
        # Test runs in transaction
        # Automatically rolled back after test
```

#### 3. Refactor Test Classes

**Before:**
```python
class TestUserProfileCRUD:
    @pytest.fixture
    async def test_db(self):
        with PostgresContainer("postgres:17") as container:
            # ... 50 lines of setup ...
```

**After:**
```python
class TestUserProfileCRUD:
    @pytest.mark.asyncio
    async def test_create_user(self, db_connection, jsonb_schema):
        async with db_connection.transaction():
            repo = UserRepository(db_connection)
            # ... test code ...
```

## Expected Benefits

1. **Speed**: Tests run 5-10x faster (no container startup per class)
2. **Resource usage**: Single PostgreSQL container instead of 4-5
3. **Maintainability**: Schema defined once in conftest.py
4. **Isolation**: Transaction rollback ensures test independence

## Migration Steps

1. Add `jsonb_schema` fixture to conftest.py
2. Refactor each test file:
   - Remove local `test_db` fixture
   - Use `db_connection` + `jsonb_schema` fixtures
   - Wrap tests in transactions for isolation
3. Run tests to verify they still pass
4. Measure performance improvement

## Example Refactored Test
```python
class TestJSONBRepository:
    @pytest.mark.asyncio
    async def test_create_with_jsonb(self, db_connection, jsonb_schema):
        async with db_connection.transaction():
            repo = UserRepository(db_connection)
            
            user = UserProfile(
                username="test",
                email="test@example.com",
                metadata={"key": "value"},
                preferences={"theme": "dark"},
                tags=["python", "testing"]
            )
            
            created = await repo.create(user)
            assert created.id is not None
            assert created.metadata == {"key": "value"}
            # Transaction automatically rolled back
```

## Performance Impact
- Current: ~25 seconds for 5 test classes (5s per container)
- After refactoring: ~5 seconds total (1 container for all)
- **80% reduction in test setup time**