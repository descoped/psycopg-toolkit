# Psycopg Toolkit

A robust PostgreSQL database toolkit providing enterprise-grade connection pooling and database management capabilities for Python applications.

## Features

- Async-first design with connection pooling via `psycopg-pool`
- Smart connection management with automatic retries and exponential backoff
- Configurable pool settings with runtime optimization
- Type-safe with full typing support
- Comprehensive error handling and custom exceptions
- Database health monitoring
- Initialization callback system for startup operations

## Installation

```bash
pip install psycopg-toolkit
```

## Quick Start

Here's a simple example of connecting to PostgreSQL:

```python
from psycopg_toolkit import Database, DatabaseSettings

# Configure database
settings = DatabaseSettings(
    host="localhost",
    port=5432,
    dbname="your_database",
    user="your_user",
    password="your_password"
)

async def main():
    # Initialize database with connection pool
    db = Database(settings)
    await db.init_db()
    
    # Execute queries
    async with db.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT * FROM users")
            users = await cur.fetchall()
    
    # Clean up connections
    await db.cleanup()
```

## Architecture

The toolkit manages database connections through a layered architecture:

1. Connection Pool Layer - Handles connection lifecycle and pooling
2. Transaction Layer - Manages database transactions and retries
3. Error Management Layer - Provides custom exceptions and error handling
4. Health Check Layer - Monitors database availability

## Key Components

### Database Settings

Configure your database connection:

```python
settings = DatabaseSettings(
    host="localhost",
    port=5432,
    dbname="your_database",
    user="your_user",
    password="your_password",
    min_pool_size=5,    # Optional
    max_pool_size=20,   # Optional
    pool_timeout=30     # Optional
)
```

### Connection Management

The `Database` class provides connection handling:

```python
# Connection context manager
async with db.connection() as conn:
    # Your database operations here
    pass  # Connection automatically returned to pool

# Manual connection acquisition
conn = await db.acquire()
try:
    # Your operations
    pass
finally:
    await db.release(conn)
```

### Initialization Callbacks

Register startup operations:

```python
async def init_tables(pool):
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL
                )
            """)

db.register_init_callback(init_tables)
```

### Error Handling

Comprehensive exception hierarchy:

```python
try:
    async with db.connection() as conn:
        # Database operations
        pass
except DatabaseConnectionError as e:
    # Handle connection failures
except DatabasePoolError as e:
    # Handle pool exhaustion
except DatabaseNotAvailable as e:
    # Handle database unavailability
except PsycoDBException as e:
    # Handle general database errors
```

## Advanced Usage

### Health Monitoring

```python
# Check database availability
is_healthy = await db.ping_postgres()

# Get pool statistics
stats = await db.get_pool_stats()
print(f"Active connections: {stats.active_connections}")
```

### Connection Pool Management

```python
# Configure pool behavior
db = Database(
    settings,
    retry_attempts=3,
    backoff_factor=2.0,
    max_retry_delay=30.0
)
```

## Best Practices

1. Always use async context managers for connection handling
2. Configure appropriate pool sizes for your workload
3. Implement proper error handling using provided exceptions
4. Use health checks in production environments
5. Clean up resources during application shutdown

## Documentation

Detailed documentation for each component is available in the `docs/` directory:

- [Database Management](docs/database.md)
- [Transaction Management](docs/transaction_manager.md)
- [Base Repository](docs/base_repository.md)
- [PsycopgHelper](docs/psycopg_helper.md)

These guides provide in-depth explanations, examples, and best practices for each feature.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
