# Database Management

The `Database` class is the core component of psyco-db that manages PostgreSQL database connections and provides connection pooling functionality. It handles connection lifecycle, pool management, health checks, and provides a robust interface for database operations.

## Quick Start

```python
from psyco_db import Database, DatabaseSettings

# Configure settings
settings = DatabaseSettings(
    host="localhost",
    port=5432,
    dbname="mydb",
    user="myuser",
    password="mypassword"
)

# Create and initialize database
db = Database(settings)
await db.init_db()

# Use the database
async with db.connection() as conn:
    # Your database operations here
    pass

# Cleanup
await db.cleanup()
```

## Configuration

### Database Settings

The `DatabaseSettings` class provides configuration options for database connections:

```python
settings = DatabaseSettings(
    # Required settings
    host="localhost",        # Database host
    port=5432,              # Database port
    dbname="mydb",          # Database name
    user="myuser",          # Database user
    password="mypassword",  # Database password
    
    # Optional settings (with defaults)
    min_pool_size=5,        # Minimum connections in pool
    max_pool_size=20,       # Maximum connections in pool
    pool_timeout=30,        # Connection acquisition timeout (seconds)
    connection_timeout=5.0,  # Initial connection timeout (seconds)
    statement_timeout=None   # SQL statement timeout (seconds)
)
```

## Connection Management

### Basic Connection Usage

The `connection()` context manager provides safe handling of database connections:

```python
async with db.connection() as conn:
    async with conn.cursor() as cur:
        await cur.execute("SELECT * FROM mytable")
        results = await cur.fetchall()
```

### Connection Pool Features

The database maintains a connection pool with:
- Automatic connection acquisition and release
- Connection timeouts
- Pool size management
- Connection validation
- Automatic retry with exponential backoff

### Pool Lifecycle

```python
# Initialize the pool
await db.init_db()

# Check if pool is active
if db.is_pool_active():
    print("Pool is ready")

# Cleanup pool when done
await db.cleanup()
```

## Health Monitoring

### Database Health Checks

```python
# Simple ping check
try:
    is_available = db.ping_postgres()
    print(f"Database is available: {is_available}")
except DatabaseConnectionError as e:
    print(f"Database is not available: {e}")

# Comprehensive pool health check
is_healthy = await db.check_pool_health()
if not is_healthy:
    print("Pool requires attention")
```

## Initialization Callbacks

You can register callbacks that will be executed after pool initialization:

```python
async def init_schema(pool):
    """Create initial database schema."""
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """)

# Register the callback
await db.register_init_callback(init_schema)
```

## Error Handling

The Database class provides specific exceptions for different scenarios:

```python
try:
    async with db.connection() as conn:
        # Database operations
        pass
except DatabaseConnectionError as e:
    print(f"Connection error: {e}")
except DatabasePoolError as e:
    print(f"Pool error: {e}")
except DatabaseNotAvailable as e:
    print(f"Database not available: {e}")
```

### Exception Types

- `DatabaseConnectionError`: Raised for connection failures
- `DatabasePoolError`: Raised for pool-related issues
- `DatabaseNotAvailable`: Raised when database is not accessible

## Best Practices

### Resource Management

1. Always use async context managers:
```python
async with db.connection() as conn:
    # Your code here
```

2. Properly initialize and cleanup:
```python
try:
    await db.init_db()
    # Your application code
finally:
    await db.cleanup()
```

### Pool Configuration

1. Set appropriate pool sizes:
```python
settings = DatabaseSettings(
    # ... other settings ...
    min_pool_size=5,    # Adjust based on minimum load
    max_pool_size=20,   # Adjust based on maximum load
    pool_timeout=30     # Adjust based on operation timing
)
```

2. Monitor pool health regularly:
```python
if not await db.check_pool_health():
    # Implement recovery logic
    pass
```

### Error Recovery

1. Implement retry logic for transient failures:
```python
from tenacity import retry, stop_after_attempt

@retry(stop=stop_after_attempt(3))
async def perform_db_operation():
    async with db.connection() as conn:
        # Your operation here
        pass
```

2. Handle cleanup properly:
```python
try:
    await db.init_db()
    # Database operations
except Exception:
    # Handle errors
finally:
    await db.cleanup()  # Always cleanup
```

## Advanced Usage

### Custom Pool Configuration

```python
settings = DatabaseSettings(
    # ... basic settings ...
    min_pool_size=10,
    max_pool_size=50,
    pool_timeout=60,
    connection_timeout=10.0,
    statement_timeout=30.0
)
```

### Multiple Database Support

```python
# Create multiple database instances
db1 = Database(settings_primary)
db2 = Database(settings_replica)

# Initialize both
await db1.init_db()
await db2.init_db()

try:
    # Use appropriate database based on operation
    async with db1.connection() as conn:
        # Write operations
        pass
    
    async with db2.connection() as conn:
        # Read operations
        pass
finally:
    # Cleanup both
    await db1.cleanup()
    await db2.cleanup()
```

## Integration with Other Components

### With Transaction Manager

```python
# Get transaction manager
tm = await db.get_transaction_manager()

# Use in transactions
async with tm.transaction() as conn:
    # Your transactional code here
    pass
```

### With Repositories

```python
async with db.connection() as conn:
    repository = UserRepository(conn)
    users = await repository.get_all()
```
