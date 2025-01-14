# PsycopgHelper Documentation

The `PsycopgHelper` class provides utility methods for safe SQL query construction using psycopg3. It prevents SQL injection attacks by properly handling table names, column names, and query parameters.

## Overview

```python
from psyco_db.utils import PsycopgHelper
from psycopg.sql import SQL
```

The helper provides methods for:
- Safe column and table name handling
- Parameter placeholder generation
- Secure query building for CRUD operations

## Query Building Methods

### SELECT Queries

```python
# Basic select
query = PsycopgHelper.build_select_query(
    table_name="users",
    columns=["id", "username", "email"],
    where_clause={"active": True}
)

# Usage
await cur.execute(query, list(where_clause.values()))
```

Generated SQL will be:
```sql
SELECT "id", "username", "email" FROM "users" WHERE "active" = $1
```

### INSERT Queries

```python
# Single insert
data = {
    "username": "john_doe",
    "email": "john@example.com"
}
query = PsycopgHelper.build_insert_query(
    table_name="users",
    data=data
)

# Usage
await cur.execute(query, list(data.values()))

# Batch insert
query = PsycopgHelper.build_insert_query(
    table_name="users",
    data=data,
    batch_size=3
)

# Usage with multiple records
values = []
for record in records:
    values.extend(record.values())
await cur.execute(query, values)
```

Generated SQL for batch insert:
```sql
INSERT INTO "users" ("username", "email") 
VALUES ($1, $2), ($3, $4), ($5, $6)
```

### UPDATE Queries

```python
# Update with where clause
data = {"status": "active"}
where_clause = {"id": user_id}

query = PsycopgHelper.build_update_query(
    table_name="users",
    data=data,
    where_clause=where_clause
)

# Usage
values = list(data.values()) + list(where_clause.values())
await cur.execute(query, values)
```

Generated SQL:
```sql
UPDATE "users" SET "status" = $1 WHERE "id" = $2
```

### DELETE Queries

```python
where_clause = {"id": user_id}
query = PsycopgHelper.build_delete_query(
    table_name="users",
    where_clause=where_clause
)

# Usage
await cur.execute(query, list(where_clause.values()))
```

Generated SQL:
```sql
DELETE FROM "users" WHERE "id" = $1
```

## Utility Methods

### Column Handling

```python
# Get SQL-safe column identifiers
data = {"username": "john", "email": "john@example.com"}
columns = PsycopgHelper.get_columns(data)
# Returns: [Identifier('username'), Identifier('email')]

# Get column names as strings
column_names = PsycopgHelper.get_columns_as_list(data)
# Returns: ['username', 'email']
```

### Placeholder Generation

```python
# Generate SQL placeholders
placeholders = PsycopgHelper.get_placeholders(3)
# Returns: [Placeholder(), Placeholder(), Placeholder()]

# Use in custom queries
query = SQL("INSERT INTO table_name VALUES ({})").format(
    SQL(', ').join(placeholders)
)
```

## Best Practices

### Parameter Handling

1. Always use parameter binding:
```python
# Good
query = PsycopgHelper.build_select_query(
    "users",
    where_clause={"id": user_id}
)
await cur.execute(query, [user_id])

# Bad - Don't do this!
await cur.execute(
    f"SELECT * FROM users WHERE id = {user_id}"
)
```

2. Use proper value lists for execution:
```python
# For UPDATE queries
values = list(data.values()) + list(where_clause.values())
await cur.execute(query, values)

# For batch INSERT queries
batch_values = []
for record in records:
    batch_values.extend(record.values())
await cur.execute(query, batch_values)
```

### Query Construction

1. Let the helper handle identifiers:
```python
# Good - Safe table and column handling
query = PsycopgHelper.build_select_query("users", ["username"])

# Bad - Don't construct identifiers manually
query = SQL("SELECT username FROM users")
```

2. Use appropriate batch sizes:
```python
# Adjust batch size based on column count and data size
query = PsycopgHelper.build_insert_query(
    "users",
    data,
    batch_size=100
)
```

## Security Considerations

### SQL Injection Prevention

The helper automatically protects against SQL injection in multiple ways:

1. Table Names:
```python
# Safe - Table name is properly quoted
query = PsycopgHelper.build_select_query("users")
# Generates: SELECT * FROM "users"
```

2. Column Names:
```python
# Safe - Column names are properly quoted
query = PsycopgHelper.build_select_query(
    "users",
    columns=["user_id", "name"]
)
# Generates: SELECT "user_id", "name" FROM "users"
```

3. Values:
```python
# Safe - Values use parameterized queries
query = PsycopgHelper.build_select_query(
    "users",
    where_clause={"status": status}
)
# Generates: SELECT * FROM "users" WHERE "status" = $1
```

### Common Attack Vectors

The helper protects against:
- Table name injection
- Column name injection
- Value injection
- Batch parameter injection

## Advanced Usage

### Custom Query Building

```python
# Complex SELECT with multiple conditions
query = PsycopgHelper.build_select_query(
    "users",
    columns=["id", "username"],
    where_clause={
        "active": True,
        "role": "admin"
    }
)

# Multiple table operations
data = {"status": "archived"}
where_clause = {"created_at": cutoff_date}
query = PsycopgHelper.build_update_query(
    "documents",
    data,
    where_clause
)
```

### Batch Processing

```python
# Efficient batch insert
records = [
    {"name": "User 1", "email": "user1@example.com"},
    {"name": "User 2", "email": "user2@example.com"},
    # ... more records
]

query = PsycopgHelper.build_insert_query(
    "users",
    records[0],  # Use first record for structure
    batch_size=len(records)
)

# Flatten values for execution
values = [val for record in records for val in record.values()]
await cur.execute(query, values)
```

## Integration Examples

### With Repository Pattern

```python
class UserRepository:
    def __init__(self, connection):
        self.connection = connection
        
    async def find_by_criteria(self, criteria: dict):
        query = PsycopgHelper.build_select_query(
            "users",
            where_clause=criteria
        )
        async with self.connection.cursor() as cur:
            await cur.execute(query, list(criteria.values()))
            return await cur.fetchall()
```

### With Transaction Manager

```python
async with tm.transaction() as conn:
    query = PsycopgHelper.build_insert_query(
        "users",
        user_data
    )
    async with conn.cursor() as cur:
        await cur.execute(query, list(user_data.values()))
```
