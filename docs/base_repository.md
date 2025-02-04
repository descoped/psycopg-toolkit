# BaseRepository Documentation

The `BaseRepository` implements the repository pattern, providing a type-safe, generic interface for database operations. It abstracts away SQL complexity while ensuring secure database interactions through `PsycopgHelper`.

## Understanding the Design

The repository uses generics to ensure type safety:

```python
from uuid import UUID
from pydantic import BaseModel
from psycopg_toolkit import BaseRepository

# Define your data model with Pydantic
class User(BaseModel):
    id: UUID
    username: str
    email: str

# Create a typed repository
class UserRepository(BaseRepository[User]):
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="users",
            model_class=User,  # Type information for validation
            primary_key="id"   # Primary key for lookups
        )
```

The generic type parameter `[User]` ensures that:
- Only User objects can be created through this repository
- All queries return properly typed User objects
- Type checking catches mismatched models at compile time

## CRUD Operations Explained

### Create: Understanding Data Flow

```python
# Single record creation
async def create_user():
    # Create Pydantic model instance - validates data
    user_data = User(
        id=uuid4(),
        username="john_doe",
        email="john@example.com"
    )
    
    # Repository handles:
    # 1. Converts Pydantic model to dict
    # 2. Constructs safe SQL via PsycopgHelper
    # 3. Executes query with parameters
    # 4. Converts result back to Pydantic model
    user = await repository.create(user_data)
```

Under the hood:
```python
# The repository converts your model to a secure query:
insert_query = PsycopgHelper.build_insert_query(self.table_name, data)
# Generates: INSERT INTO users (id, username, email) VALUES ($1, $2, $3)
# RETURNING ensures we get back the created record
await cur.execute(insert_query + SQL(" RETURNING *"), list(data.values()))
```

For bulk operations:
```python
async def create_many_users():
    # Create multiple users efficiently
    users = [
        User(id=uuid4(), username=f"user_{i}", email=f"user_{i}@example.com")
        for i in range(3)
    ]
    
    # Repository handles:
    # 1. Batches records for efficient insertion
    # 2. Maintains transaction safety
    # 3. Returns all created records
    created_users = await repository.create_bulk(users, batch_size=100)
```

### Read: Safe Query Construction

```python
# Get by ID - Type-safe UUID lookup
async def get_user(user_id: UUID):
    # Repository handles:
    # 1. Constructs safe parameterized query
    # 2. Executes with proper parameter binding
    # 3. Raises RecordNotFoundError if not found
    # 4. Converts result to Pydantic model
    user = await repository.get_by_id(user_id)

# Get all records - Efficient bulk loading
async def list_users():
    # Repository handles:
    # 1. Constructs optimized SELECT query
    # 2. Converts all results to Pydantic models
    users = await repository.get_all()
```

The underlying query construction:
```python
# Safe query building with PsycopgHelper
select_query = PsycopgHelper.build_select_query(
    self.table_name,
    where_clause={self.primary_key: record_id}
)
# Generates: SELECT * FROM users WHERE id = $1
# Parameters are always bound separately for security
await cur.execute(select_query, [record_id])
```

### Update: Safe Data Modifications

```python
async def update_user(user_id: UUID):
    # Specify only fields that need updating
    updates = {
        "username": "new_username",
        "email": "new@example.com"
    }
    
    # Repository handles:
    # 1. Validates record exists
    # 2. Constructs safe UPDATE query
    # 3. Returns updated Pydantic model
    updated_user = await repository.update(user_id, updates)
```

Security and validation:
```python
# The repository ensures safe updates
update_query = PsycopgHelper.build_update_query(
    self.table_name,
    data,
    where_clause={self.primary_key: record_id}
)
# Generates: UPDATE users SET username = $1, email = $2 WHERE id = $3
# Returns full record: RETURNING *
await cur.execute(update_query + SQL(" RETURNING *"), 
                 list(data.values()) + [record_id])
```

### Delete: Safe Record Removal

```python
async def remove_user(user_id: UUID):
    # Repository handles:
    # 1. Verifies record exists
    # 2. Constructs safe DELETE query
    # 3. Raises error if record not found
    await repository.delete(user_id)
```

Delete operation internals:
```python
# Safe delete construction
delete_query = PsycopgHelper.build_delete_query(
    self.table_name,
    where_clause={self.primary_key: record_id}
)
# Generates: DELETE FROM users WHERE id = $1
await cur.execute(delete_query, [record_id])
```

## Error Handling and Safety

The repository provides specific exceptions for different scenarios:

```python
try:
    user = await repository.get_by_id(user_id)
except RecordNotFoundError:
    # Record doesn't exist - handle missing data
    logger.warning(f"User {user_id} not found")
except OperationError as e:
    # Database operation failed - handle error
    logger.error(f"Database error: {e}")
    # Contains original exception in .original_error
```

## Practical Usage Patterns

### Transaction Management

```python
# Using with transaction manager ensures:
# 1. All operations succeed or all rollback
# 2. Connection is properly managed
# 3. Errors trigger automatic rollback
async with tm.transaction() as conn:
    repo = UserRepository(conn)
    
    # Create and update in same transaction
    user = await repo.create(User(
        id=uuid4(),
        username="john",
        email="john@example.com"
    ))
    
    # This only commits if both operations succeed
    await repo.update(user.id, {"username": "john_doe"})
```

### Connection Management

```python
# Using with database connection:
# 1. Automatically manages connection lifecycle
# 2. Returns connection to pool when done
# 3. Handles errors properly
async with db.connection() as conn:
    repo = UserRepository(conn)
    users = await repo.get_all()
```

## Advanced Usage

### Custom Queries

While the base repository provides common operations, you can extend it for custom needs:

```python
class UserRepository(BaseRepository[User]):
    async def find_by_email(self, email: str) -> Optional[User]:
        query = PsycopgHelper.build_select_query(
            self.table_name,
            where_clause={"email": email}
        )
        
        async with self.db_connection.cursor() as cur:
            await cur.execute(query, [email])
            result = await cur.fetchone()
            return User(**result) if result else None
```

### Batch Operations

For efficient bulk operations:

```python
async def create_users_batch(users: List[User]):
    # Efficient bulk insert with customizable batch size
    # Larger batch sizes can improve performance but use more memory
    created = await repository.create_bulk(users, batch_size=100)
    
    # All records created in single transaction
    # Returns list of created User objects
    return created
```
