# JSONB Support Documentation

The `psycopg-toolkit` provides comprehensive support for PostgreSQL's JSONB data type, enabling seamless integration of JSON data with your Pydantic models. This document covers all aspects of JSONB support including automatic field detection, data processing, error handling, and performance optimization.

## Overview

JSONB (Binary JSON) is PostgreSQL's binary JSON data type that offers:
- Efficient storage and fast query performance
- Rich indexing capabilities (GIN indexes)
- Powerful operators for complex queries
- Automatic validation and type checking

The toolkit's JSONB support includes:
- **Automatic JSON field detection** from Pydantic type hints
- **Seamless serialization/deserialization** between Python objects and JSONB
- **psycopg JSON adapter integration** for optimal performance
- **Comprehensive error handling** with JSON-specific exceptions
- **Flexible configuration options** for different use cases

## Quick Start

```python
from typing import Dict, List, Any
from pydantic import BaseModel
from psycopg_toolkit import Database, BaseRepository

# Define model with JSON fields
class UserProfile(BaseModel):
    id: int
    name: str
    metadata: Dict[str, Any]      # Automatically detected as JSON field
    preferences: Dict[str, str]   # Automatically detected as JSON field
    tags: List[str]               # Automatically detected as JSON field

# Create repository - JSON fields detected automatically
class UserRepository(BaseRepository[UserProfile, int]):
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="user_profiles",
            model_class=UserProfile,
            primary_key="id"
            # auto_detect_json=True by default
        )

# Usage
async with db.connection() as conn:
    repo = UserRepository(conn)
    
    user = UserProfile(
        id=1,
        name="John Doe",
        metadata={"created_at": "2024-01-01", "source": "web"},
        preferences={"theme": "dark", "language": "en"},
        tags=["premium", "early_adopter"]
    )
    
    # JSON fields automatically serialized to JSONB
    created_user = await repo.create(user)
    
    # JSON fields automatically deserialized from JSONB
    retrieved_user = await repo.get_by_id(1)
```

## JSON Field Detection

### Automatic Detection

The toolkit automatically detects JSON fields from Pydantic type hints:

```python
from typing import Dict, List, Optional, Any, Union

class ProductModel(BaseModel):
    # These fields are automatically detected as JSON:
    specifications: Dict[str, Any]           # Dictionary -> JSON
    categories: List[str]                    # List -> JSON
    metadata: Dict[str, Union[str, int]]     # Complex Dict -> JSON
    optional_data: Optional[Dict[str, Any]]  # Optional Dict -> JSON
    
    # These fields are NOT detected as JSON:
    name: str                                # String -> TEXT
    price: float                             # Float -> NUMERIC
    description: Optional[str]               # Optional String -> TEXT
    tags_json: str                           # String -> TEXT (even if contains JSON)
```

**Supported JSON Types:**
- `Dict[K, V]` - Any dictionary type
- `List[T]` - Any list type  
- `Optional[Dict[K, V]]` - Optional dictionaries
- `Optional[List[T]]` - Optional lists
- `Union` types containing dictionaries or lists

### Manual Configuration

For precise control over JSON field handling:

```python
class ProductRepository(BaseRepository[Product, int]):
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="products",
            model_class=Product,
            primary_key="id",
            # Explicitly specify JSON fields
            json_fields={"specifications", "categories", "metadata"},
            # Disable automatic detection
            auto_detect_json=False
        )
```

## JSON Processing Approaches

### Approach 1: psycopg JSON Adapters (Recommended)

Use psycopg's native JSON adapters for optimal performance:

```python
# Database configuration
settings = DatabaseSettings(
    host="localhost",
    port=5432,
    dbname="mydb",
    user="user",
    password="password",
    enable_json_adapters=True  # Enable psycopg JSON adapters
)

# Repository configuration
class UserRepository(BaseRepository[UserProfile, int]):
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="user_profiles",
            model_class=UserProfile,
            primary_key="id",
            # Disable custom JSON processing - let psycopg handle it
            auto_detect_json=False
        )
```

**Benefits:**
- ✅ Optimal performance - no double processing
- ✅ PostgreSQL handles JSON validation
- ✅ Automatic type conversion
- ✅ Recommended for production

### Approach 2: Custom JSON Processing

Use the toolkit's custom JSON processing for advanced control:

```python
# Database configuration
settings = DatabaseSettings(
    enable_json_adapters=False  # Disable psycopg adapters
)

# Repository configuration
class UserRepository(BaseRepository[UserProfile, int]):
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="user_profiles", 
            model_class=UserProfile,
            primary_key="id",
            # Enable custom JSON processing
            auto_detect_json=True,
            strict_json_processing=True  # Raise exceptions on errors
        )
```

**Benefits:**
- ✅ Fine-grained error handling
- ✅ Custom serialization logic
- ✅ Detailed error reporting
- ⚠️ Slightly lower performance

## Error Handling

### JSON-Specific Exceptions

```python
from psycopg_toolkit import (
    JSONProcessingError,
    JSONSerializationError, 
    JSONDeserializationError
)

try:
    # This will fail with non-serializable data
    user = await repo.create(UserProfile(
        id=1,
        name="John",
        metadata={"bad_data": SomeNonSerializableObject()}
    ))
except JSONSerializationError as e:
    print(f"Serialization failed: {e}")
    print(f"Field: {e.field_name}")
    print(f"Original error: {e.original_error}")

try:
    # This will fail with malformed JSON in database
    user = await repo.get_by_id(1)
except JSONDeserializationError as e:
    print(f"Deserialization failed: {e}")
    print(f"Field: {e.field_name}")
    print(f"Invalid data: {e.invalid_data}")
```

### Strict vs Lenient Processing

```python
# Strict processing - raises exceptions on JSON errors
class StrictRepository(BaseRepository[UserProfile, int]):
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="users",
            model_class=UserProfile,
            primary_key="id",
            strict_json_processing=True  # Raises JSONProcessingError
        )

# Lenient processing - logs errors and continues
class LenientRepository(BaseRepository[UserProfile, int]):
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="users", 
            model_class=UserProfile,
            primary_key="id",
            strict_json_processing=False  # Logs errors, continues
        )
```

## Database Schema Design

### Table Creation

Create tables with JSONB columns and appropriate indexes:

```sql
-- User profiles table
CREATE TABLE user_profiles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    
    -- JSONB columns
    metadata JSONB NOT NULL DEFAULT '{}',
    preferences JSONB NOT NULL DEFAULT '{}',
    tags JSONB NOT NULL DEFAULT '[]',
    profile_data JSONB
);

-- Performance indexes
CREATE INDEX idx_user_metadata ON user_profiles USING GIN (metadata);
CREATE INDEX idx_user_preferences ON user_profiles USING GIN (preferences);
CREATE INDEX idx_user_tags ON user_profiles USING GIN (tags);

-- Functional indexes for specific queries
CREATE INDEX idx_user_theme ON user_profiles 
USING BTREE ((preferences->>'theme'));

CREATE INDEX idx_user_created_at ON user_profiles 
USING BTREE ((metadata->>'created_at'));
```

### Index Strategy

**GIN Indexes** (Recommended for JSONB):
```sql
-- General JSONB queries
CREATE INDEX idx_metadata_gin ON table_name USING GIN (jsonb_column);

-- Specific path queries  
CREATE INDEX idx_metadata_path ON table_name USING GIN ((jsonb_column -> 'path'));
```

**BTREE Indexes** (For specific values):
```sql
-- Frequently queried specific values
CREATE INDEX idx_status ON table_name USING BTREE ((jsonb_column->>'status'));
```

## JSONB Querying

### Basic Operators

```python
# Direct SQL queries using JSONB operators
async with db.connection() as conn:
    async with conn.cursor() as cur:
        
        # -> operator: Get JSON object field
        await cur.execute("""
            SELECT name, metadata->'browser' as browser_info
            FROM user_profiles
            WHERE metadata->'browser' IS NOT NULL
        """)
        
        # ->> operator: Get JSON object field as text
        await cur.execute("""
            SELECT name, preferences->>'theme' as theme
            FROM user_profiles 
            WHERE preferences->>'theme' = 'dark'
        """)
        
        # ? operator: Does JSON contain key?
        await cur.execute("""
            SELECT name FROM user_profiles
            WHERE tags ? 'premium'
        """)
        
        # @> operator: Does JSON contain sub-JSON?
        await cur.execute("""
            SELECT name FROM user_profiles
            WHERE metadata @> '{"source": "mobile"}'
        """)
        
        # || operator: Concatenate JSON
        await cur.execute("""
            UPDATE user_profiles 
            SET preferences = preferences || '{"new_feature": true}'
            WHERE id = %s
        """, [user_id])
```

### Advanced Queries

```python
# Array operations
await cur.execute("""
    SELECT name, tags
    FROM user_profiles
    WHERE jsonb_array_length(tags) > 2
""")

# Nested object queries
await cur.execute("""
    SELECT name, metadata->'browser'->>'version' as browser_version
    FROM user_profiles
    WHERE (metadata->'browser'->>'name') = 'Chrome'
      AND (metadata->'browser'->>'version')::numeric >= 120
""")

# JSON path queries (PostgreSQL 12+)
await cur.execute("""
    SELECT name, jsonb_path_query(metadata, '$.browser.name') as browser
    FROM user_profiles
    WHERE jsonb_path_exists(metadata, '$.browser.name')
""")

# Aggregation with JSON
await cur.execute("""
    SELECT 
        preferences->>'theme' as theme,
        COUNT(*) as users_count,
        jsonb_agg(name) as user_names
    FROM user_profiles
    WHERE preferences ? 'theme'
    GROUP BY preferences->>'theme'
""")
```

### JSONB Updates

```python
# Update specific fields
await cur.execute("""
    UPDATE user_profiles 
    SET metadata = jsonb_set(
        metadata,
        '{last_login}',
        %s::jsonb
    )
    WHERE id = %s
""", [f'"{datetime.now().isoformat()}"', user_id])

# Update nested objects
await cur.execute("""
    UPDATE user_profiles
    SET metadata = jsonb_set(
        metadata,
        '{browser,last_used}', 
        %s::jsonb
    )
    WHERE id = %s
""", [f'"{datetime.now().isoformat()}"', user_id])

# Add to arrays
await cur.execute("""
    UPDATE user_profiles
    SET tags = tags || %s::jsonb
    WHERE id = %s
""", ['["new_tag"]', user_id])

# Remove from objects
await cur.execute("""
    UPDATE user_profiles
    SET metadata = metadata - 'temporary_key'
    WHERE id = %s
""", [user_id])
```

## Performance Optimization

### Best Practices

1. **Use GIN Indexes**:
```sql
-- Index entire JSONB column
CREATE INDEX idx_metadata ON users USING GIN (metadata);

-- Index specific paths
CREATE INDEX idx_user_type ON users USING GIN ((metadata -> 'user_type'));
```

2. **Minimize JSON Processing**:
```python
# Prefer psycopg JSON adapters for better performance
settings = DatabaseSettings(enable_json_adapters=True)

# Use specific field queries instead of loading entire objects
await cur.execute("""
    SELECT id, metadata->>'status' as status
    FROM users
    WHERE metadata->>'status' = 'active'
""")
```

3. **Batch Operations**:
```python
# Use bulk operations for multiple records
users = [UserProfile(...) for _ in range(100)]
created_users = await repo.create_bulk(users, batch_size=50)
```

### Performance Monitoring

```python
import time
import logging

# Monitor JSON processing performance
class MonitoredRepository(BaseRepository[UserProfile, int]):
    async def create(self, item):
        start_time = time.time()
        try:
            result = await super().create(item)
            processing_time = time.time() - start_time
            logging.info(f"JSON create took {processing_time:.3f}s")
            return result
        except Exception as e:
            processing_time = time.time() - start_time
            logging.error(f"JSON create failed in {processing_time:.3f}s: {e}")
            raise
```

## Migration Strategies

### Adding JSONB to Existing Tables

```sql
-- Add JSONB column to existing table
ALTER TABLE users ADD COLUMN metadata JSONB DEFAULT '{}';

-- Migrate existing data to JSONB
UPDATE users SET metadata = jsonb_build_object(
    'created_at', created_at::text,
    'updated_at', updated_at::text,
    'legacy_field', legacy_field
);

-- Add index after data migration
CREATE INDEX CONCURRENTLY idx_users_metadata ON users USING GIN (metadata);

-- Remove old columns after verification
ALTER TABLE users DROP COLUMN created_at, DROP COLUMN updated_at, DROP COLUMN legacy_field;
```

### Gradual Migration

```python
class MigrationRepository(BaseRepository[UserProfile, int]):
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="users",
            model_class=UserProfile,
            primary_key="id",
            # Start with custom processing for migration
            auto_detect_json=True,
            strict_json_processing=False  # Allow failures during migration
        )
    
    async def migrate_legacy_data(self, batch_size: int = 100):
        """Migrate legacy data to JSONB format"""
        offset = 0
        while True:
            # Get batch of records
            async with self.db_connection.cursor() as cur:
                await cur.execute("""
                    SELECT id, legacy_data 
                    FROM users 
                    WHERE metadata IS NULL
                    LIMIT %s OFFSET %s
                """, [batch_size, offset])
                
                batch = await cur.fetchall()
                if not batch:
                    break
                
                # Convert and update each record
                for user_id, legacy_data in batch:
                    try:
                        metadata = self._convert_legacy_data(legacy_data)
                        await cur.execute("""
                            UPDATE users 
                            SET metadata = %s::jsonb
                            WHERE id = %s
                        """, [json.dumps(metadata), user_id])
                    except Exception as e:
                        logging.error(f"Migration failed for user {user_id}: {e}")
                
                offset += batch_size
```

## Testing JSONB Functionality

### Unit Tests

```python
import pytest
from psycopg_toolkit import JSONHandler, JSONSerializationError

class TestJSONHandler:
    def test_serialize_complex_data(self):
        data = {
            "user_id": uuid.uuid4(),
            "created_at": datetime.now(),
            "preferences": {"theme": "dark"},
            "tags": ["premium", "beta"]
        }
        
        json_str = JSONHandler.serialize(data)
        assert isinstance(json_str, str)
        
        # Should be deserializable
        deserialized = JSONHandler.deserialize(json_str)
        assert deserialized["preferences"]["theme"] == "dark"
    
    def test_serialize_error_handling(self):
        class NonSerializable:
            pass
        
        with pytest.raises(ValueError, match="Cannot serialize to JSON"):
            JSONHandler.serialize({"bad": NonSerializable()})
```

### Integration Tests

```python
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture
async def db_with_jsonb():
    with PostgresContainer("postgres:17") as container:
        settings = DatabaseSettings(
            host=container.get_container_host_ip(),
            port=container.get_exposed_port(5432),
            dbname=container.dbname,
            user=container.username,
            password=container.password,
            enable_json_adapters=True
        )
        
        db = Database(settings)
        await db.init_db()
        
        # Create test schema
        async with db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE test_users (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255),
                        metadata JSONB,
                        preferences JSONB
                    )
                """)
        
        yield db
        await db.cleanup()

@pytest.mark.asyncio
async def test_jsonb_roundtrip(db_with_jsonb):
    async with db_with_jsonb.connection() as conn:
        repo = UserRepository(conn)
        
        # Test data with complex JSON
        user = UserProfile(
            id=1,
            name="Test User",
            metadata={
                "browser": {"name": "Chrome", "version": "120"},
                "location": {"country": "US", "timezone": "EST"}
            },
            preferences={"theme": "dark", "notifications": True}
        )
        
        # Create and retrieve
        created = await repo.create(user)
        retrieved = await repo.get_by_id(created.id)
        
        # Verify JSON data integrity
        assert retrieved.metadata["browser"]["name"] == "Chrome"
        assert retrieved.preferences["theme"] == "dark"
```

## Common Patterns

### Configuration Management

```python
class AppConfig(BaseModel):
    id: int
    name: str
    settings: Dict[str, Any]
    features: List[str]
    
class ConfigRepository(BaseRepository[AppConfig, int]):
    async def get_feature_config(self, feature: str) -> Optional[Dict]:
        """Get configuration for specific feature"""
        async with self.db_connection.cursor() as cur:
            await cur.execute("""
                SELECT settings->%s as feature_config
                FROM app_configs
                WHERE features ? %s
                LIMIT 1
            """, [feature, feature])
            
            result = await cur.fetchone()
            return result[0] if result else None
    
    async def update_feature_setting(self, config_id: int, feature: str, key: str, value: Any):
        """Update specific feature setting"""
        async with self.db_connection.cursor() as cur:
            await cur.execute("""
                UPDATE app_configs
                SET settings = jsonb_set(
                    settings,
                    %s::text[],
                    %s::jsonb
                )
                WHERE id = %s
            """, [[feature, key], json.dumps(value), config_id])
```

### Event Logging

```python
class EventLog(BaseModel):
    id: int
    event_type: str
    timestamp: datetime
    data: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None

class EventRepository(BaseRepository[EventLog, int]):
    async def log_user_action(self, user_id: int, action: str, **kwargs):
        """Log user action with flexible data"""
        event = EventLog(
            event_type="user_action",
            timestamp=datetime.now(),
            data={
                "user_id": user_id,
                "action": action,
                **kwargs
            },
            metadata={
                "ip_address": kwargs.get("ip_address"),
                "user_agent": kwargs.get("user_agent"),
                "session_id": kwargs.get("session_id")
            }
        )
        return await self.create(event)
    
    async def get_user_actions(self, user_id: int, limit: int = 100):
        """Get recent actions for user"""
        async with self.db_connection.cursor() as cur:
            await cur.execute("""
                SELECT * FROM event_logs
                WHERE data->>'user_id' = %s
                  AND event_type = 'user_action'
                ORDER BY timestamp DESC
                LIMIT %s
            """, [str(user_id), limit])
            
            results = await cur.fetchall()
            return [EventLog(**dict(row)) for row in results]
```

## Troubleshooting

### Common Issues

1. **Double JSON Processing**:
```python
# Problem: Both psycopg adapters and custom processing enabled
settings = DatabaseSettings(enable_json_adapters=True)  # psycopg handles JSON
repo = Repository(auto_detect_json=True)  # Custom processing also enabled

# Solution: Choose one approach
settings = DatabaseSettings(enable_json_adapters=True)
repo = Repository(auto_detect_json=False)  # Let psycopg handle it
```

2. **JSON Serialization Errors**:
```python
# Problem: Non-serializable objects
user.metadata = {"timestamp": datetime.now()}  # datetime not JSON serializable

# Solution: Use CustomJSONEncoder or convert manually
user.metadata = {"timestamp": datetime.now().isoformat()}
```

3. **Performance Issues**:
```python
# Problem: Missing indexes
# Solution: Add appropriate GIN indexes
CREATE INDEX CONCURRENTLY idx_metadata ON users USING GIN (metadata);
```

### Debug Mode

```python
import logging

# Enable debug logging for JSON operations
logging.getLogger('psycopg_toolkit.utils.json_handler').setLevel(logging.DEBUG)
logging.getLogger('psycopg_toolkit.repositories.base').setLevel(logging.DEBUG)

# This will log JSON serialization/deserialization details
repo = UserRepository(conn)
user = await repo.create(user_data)  # Logs JSON processing steps
```

## Conclusion

The psycopg-toolkit's JSONB support provides a powerful and flexible foundation for working with JSON data in PostgreSQL. Key benefits include:

- **Seamless Integration**: Automatic JSON field detection and processing
- **High Performance**: Native psycopg adapter support for optimal speed  
- **Robust Error Handling**: Comprehensive exception hierarchy for JSON operations
- **Flexible Configuration**: Multiple approaches to fit different use cases
- **Production Ready**: Battle-tested patterns and performance optimizations

Choose the psycopg JSON adapter approach for production applications requiring maximum performance, or use custom JSON processing when you need fine-grained control over serialization and error handling.