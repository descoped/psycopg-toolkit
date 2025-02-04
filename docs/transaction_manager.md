# Transaction Management

The `TransactionManager` provides a robust interface for managing database transactions in psyco-db. It handles transaction lifecycle, automatic rollback on errors, and proper resource cleanup.

## Quick Start

```python
from psycopg_toolkit import Database, DatabaseSettings

# Initialize database
db = Database(settings)
await db.init_db()

# Get transaction manager
tm = await db.get_transaction_manager()

# Use in transaction
async with tm.transaction() as conn:
    async with conn.cursor() as cur:
        await cur.execute("INSERT INTO users (id, name) VALUES (%s, %s)", 
                         (user_id, name))
```

## Core Features

### Automatic Rollback

The transaction manager automatically rolls back transactions when exceptions occur:

```python
async with tm.transaction() as conn:
    async with conn.cursor() as cur:
        await cur.execute("INSERT INTO users (id, name) VALUES (%s, %s)", 
                         (user_id, name))
        # If any error occurs here, the transaction is automatically rolled back
        await cur.execute("UPDATE user_count SET count = count + 1")
```

### Resource Management

The transaction manager ensures proper cleanup of database resources:
- Automatically closes cursors
- Properly handles connection return to pool
- Manages transaction boundaries

## Usage Patterns

### Basic Transaction

```python
async with tm.transaction() as conn:
    async with conn.cursor() as cur:
        await cur.execute("INSERT INTO users (id, name) VALUES (%s, %s)", 
                         (user_id, name))
```

### Error Handling

```python
try:
    async with tm.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute("INSERT INTO users (id, name) VALUES (%s, %s)", 
                            (user_id, name))
except DatabaseConnectionError:
    # Handle connection issues
    logger.error("Database connection failed")
except Exception as e:
    # Handle other errors
    logger.error(f"Transaction failed: {e}")
```

### Multiple Operations

```python
async with tm.transaction() as conn:
    async with conn.cursor() as cur:
        # Multiple operations in same transaction
        await cur.execute("INSERT INTO users (id, name) VALUES (%s, %s)", 
                         (user_id, name))
        await cur.execute("INSERT INTO profiles (user_id, data) VALUES (%s, %s)", 
                         (user_id, profile_data))
        await cur.execute("UPDATE user_count SET count = count + 1")
```

## Best Practices

### Transaction Scope

1. Keep transactions as short as possible:
```python
# Good: Short, focused transaction
async with tm.transaction() as conn:
    await create_user(conn, user_data)

# Bad: Long-running transaction
async with tm.transaction() as conn:
    await process_many_users(conn)  # Could take a long time
    await send_notifications()      # Network I/O inside transaction
```

2. Avoid mixing transaction and non-transaction operations:
```python
# Good: Clear transaction boundaries
async with tm.transaction() as conn:
    user_id = await create_user(conn, user_data)

# Separate non-transactional operations
await send_welcome_email(user_id)
```

### Error Handling

1. Let exceptions propagate for automatic rollback:
```python
async with tm.transaction() as conn:
    # Don't catch exceptions unless you have a specific reason
    await perform_operations(conn)
```

2. Handle specific exceptions appropriately:
```python
try:
    async with tm.transaction() as conn:
        await perform_operations(conn)
except DatabaseConnectionError:
    # Handle connection issues
    await notify_admin("Database connection failed")
except UniqueViolationError:
    # Handle specific database constraints
    await handle_duplicate_entry()
except Exception:
    # Handle unexpected errors
    await log_error("Transaction failed")
```

## Advanced Usage

### Nested Transactions

The transaction manager supports nested transactions through savepoints:

```python
async with tm.transaction() as conn1:
    # Outer transaction
    await perform_operation_1(conn1)
    
    async with tm.transaction() as conn2:
        # Inner transaction (uses savepoint)
        await perform_operation_2(conn2)
```

### Integration with Repositories

```python
async with tm.transaction() as conn:
    # Create repositories with transaction connection
    user_repo = UserRepository(conn)
    profile_repo = ProfileRepository(conn)
    
    # Perform multiple operations
    user = await user_repo.create(user_data)
    await profile_repo.create(user.id, profile_data)
```

### Bulk Operations

```python
async with tm.transaction() as conn:
    async with conn.cursor() as cur:
        # Execute multiple operations efficiently
        await cur.executemany(
            "INSERT INTO users (id, name) VALUES (%s, %s)",
            [(user.id, user.name) for user in users]
        )
```

## Common Pitfalls

### Long-Running Transactions

Avoid keeping transactions open for long periods:

```python
# Bad: Transaction held open during processing
async with tm.transaction() as conn:
    data = await fetch_large_dataset(conn)
    processed_data = await process_data(data)  # Long operation
    await save_results(conn, processed_data)

# Good: Minimize transaction duration
data = await fetch_large_dataset(db)
processed_data = await process_data(data)
async with tm.transaction() as conn:
    await save_results(conn, processed_data)
```

### Resource Leaks

Always use async context managers:

```python
# Bad: Manual cursor management
async with tm.transaction() as conn:
    cur = await conn.cursor()
    try:
        await cur.execute(query)
    finally:
        await cur.close()

# Good: Automatic cursor management
async with tm.transaction() as conn:
    async with conn.cursor() as cur:
        await cur.execute(query)
```

### Exception Handling

Don't suppress exceptions that should trigger rollback:

```python
# Bad: Suppressing exceptions
async with tm.transaction() as conn:
    try:
        await perform_operation(conn)
    except Exception:
        pass  # Don't do this!

# Good: Let exceptions propagate
async with tm.transaction() as conn:
    await perform_operation(conn)
```

## Performance Considerations

### Transaction Size

Keep transactions focused and minimal:

```python
# Bad: Too many operations in one transaction
async with tm.transaction() as conn:
    for user in many_users:
        await process_user(conn, user)

# Good: Batch operations appropriately
batch_size = 100
for i in range(0, len(many_users), batch_size):
    batch = many_users[i:i+batch_size]
    async with tm.transaction() as conn:
        await process_user_batch(conn, batch)
```

### Connection Management

The transaction manager efficiently handles connection pooling:
- Connections are acquired only when needed
- Connections are properly returned to the pool
- Pool settings are respected
