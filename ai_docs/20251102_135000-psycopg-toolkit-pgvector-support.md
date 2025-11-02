# AI Instruction: Add Native pgvector Support to psycopg-toolkit

**Target Repository**: psycopg-toolkit
**Priority**: Medium
**Complexity**: Low-Medium (similar to existing JSON adapter pattern)
**Estimated Effort**: 2-4 hours

Test with Docker image: pgvector/pgvector:pg17 and use testcontainers. Search the web for understranding pgvector.

## Problem Statement

Currently, PostgreSQL `vector` columns (from the pgvector extension) return as strings (e.g., `"[0.1,0.2,0.3,0.4]"`) instead of Python `list[float]`. This forces users to manually parse the string representation:

```python
# Current workaround needed
def _parse_vector_data(row: dict[str, Any]) -> dict[str, Any]:
    if "vector_data" in row and isinstance(row["vector_data"], str):
        row["vector_data"] = json.loads(row["vector_data"])
    return row
```

## Desired Behavior

psycopg-toolkit should automatically detect and handle pgvector columns, similar to how it handles JSON/JSONB fields today:

1. **Auto-detect** fields with `list[float]` type hints
2. **Auto-register** pgvector adapters on connection initialization
3. **Auto-convert** between Python `list[float]` ↔ PostgreSQL `vector` type
4. **No manual parsing** required by users

## Current JSON Adapter Pattern (Reference)

psycopg-toolkit already has a similar pattern for JSON fields:

```python
# In DatabaseSettings
enable_json_adapters: bool = True  # Enables automatic JSON handling

# In TypeInspector
def detect_json_fields(model_class) -> set[str]:
    """Detects dict/list type hints for JSON columns."""
    # Returns field names that should be treated as JSON
```

## Proposed Implementation

### 1. Add pgvector Detection to TypeInspector

**File**: `psycopg_toolkit/utils/type_inspector.py`

Add method to detect vector fields:

```python
@staticmethod
def detect_vector_fields(model_class: type[BaseModel]) -> set[str]:
    """
    Detect fields that should be treated as pgvector columns.

    Detects fields with type hints:
    - list[float]
    - List[float]
    - typing.List[float]

    Returns:
        Set of field names that are vector fields
    """
    vector_fields = set()

    for field_name, field_info in model_class.model_fields.items():
        annotation = field_info.annotation

        # Handle direct list[float]
        if _is_list_of_float(annotation):
            vector_fields.add(field_name)
            continue

        # Handle Optional[list[float]], list[float] | None
        if _is_optional(annotation):
            inner_type = _unwrap_optional(annotation)
            if _is_list_of_float(inner_type):
                vector_fields.add(field_name)

    return vector_fields


def _is_list_of_float(annotation) -> bool:
    """Check if annotation is list[float]."""
    # Handle list[float]
    if hasattr(annotation, '__origin__') and annotation.__origin__ is list:
        args = getattr(annotation, '__args__', ())
        if args and args[0] is float:
            return True

    # Handle typing.List[float]
    import typing
    if hasattr(annotation, '__origin__'):
        origin = annotation.__origin__
        if origin is list or (hasattr(typing, 'List') and origin is typing.List):
            args = getattr(annotation, '__args__', ())
            if args and args[0] is float:
                return True

    return False
```

### 2. Add Vector Support to BaseRepository

**File**: `psycopg_toolkit/repositories/base.py`

Update `__init__` to detect and register pgvector:

```python
def __init__(
    self,
    db_connection: AsyncConnection,
    table_name: str,
    model_class: type[T],
    primary_key: str = "id",
    json_fields: set[str] | None = None,
    vector_fields: set[str] | None = None,  # NEW PARAMETER
    auto_detect_json: bool = True,
    auto_detect_vector: bool = True,  # NEW PARAMETER
    # ... other params
):
    """
    Initialize the base repository.

    Args:
        db_connection: Active database connection
        table_name: Name of the database table
        model_class: Pydantic model class
        primary_key: Name of primary key column (default: "id")
        json_fields: Explicit JSON fields (overrides auto-detection)
        vector_fields: Explicit vector fields (overrides auto-detection)  # NEW
        auto_detect_json: Auto-detect JSON fields (default: True)
        auto_detect_vector: Auto-detect vector fields (default: True)  # NEW
    """
    self.db_connection = db_connection
    self.table_name = table_name
    self.model_class = model_class
    self.primary_key = primary_key

    # JSON field detection (existing)
    if json_fields is not None:
        self.json_fields = json_fields
    elif auto_detect_json:
        self.json_fields = TypeInspector.detect_json_fields(model_class)
    else:
        self.json_fields = set()

    # Vector field detection (NEW)
    if vector_fields is not None:
        self.vector_fields = vector_fields
    elif auto_detect_vector:
        self.vector_fields = TypeInspector.detect_vector_fields(model_class)
    else:
        self.vector_fields = set()

    # Register pgvector if needed (NEW)
    if self.vector_fields:
        self._register_pgvector_adapter()


def _register_pgvector_adapter(self):
    """Register pgvector adapter for vector type support."""
    try:
        from pgvector.psycopg import register_vector
        register_vector(self.db_connection)
        logger.debug(f"Registered pgvector adapter for {self.table_name}")
    except ImportError:
        logger.warning(
            f"pgvector not installed but vector fields detected in {self.table_name}. "
            "Install with: pip install pgvector"
        )
```

### 3. Add Optional Dependency

**File**: `pyproject.toml`

```toml
[project.optional-dependencies]
vector = ["pgvector>=0.3.0"]

# Or add to existing extras
[project.optional-dependencies]
all = [
    "pgvector>=0.3.0",
    # ... other dependencies
]
```

### 4. Update DatabaseSettings (Optional Enhancement)

**File**: `psycopg_toolkit/core/database.py`

Add global pgvector support flag:

```python
class DatabaseSettings(BaseModel):
    # ... existing fields ...

    enable_json_adapters: bool = True
    enable_vector_adapters: bool = True  # NEW
```

Then register globally on connection creation if enabled.

## Testing Requirements

### Test Case 1: Auto-Detection

```python
from pydantic import BaseModel

class EmbeddingVector(BaseModel):
    vector_id: UUID
    vector_data: list[float]  # Should be auto-detected
    dimension: int

repository = EmbeddingVectorRepository(connection)
assert "vector_data" in repository.vector_fields
```

### Test Case 2: CRUD Operations

```python
# Create with list[float]
embedding = EmbeddingVector(
    vector_id=uuid4(),
    vector_data=[0.1, 0.2, 0.3],
    dimension=3
)
created = await repository.create(embedding)

# Verify returned as list[float], not string
assert isinstance(created.vector_data, list)
assert all(isinstance(x, float) for x in created.vector_data)
assert created.vector_data == [0.1, 0.2, 0.3]
```

### Test Case 3: Optional Vector Fields

```python
class Document(BaseModel):
    id: UUID
    content: str
    embedding: list[float] | None = None  # Optional vector

# Should still detect and handle properly
repository = DocumentRepository(connection)
assert "embedding" in repository.vector_fields
```

### Test Case 4: Manual Override

```python
# Allow users to explicitly specify vector fields
repository = MyRepository(
    connection=conn,
    table_name="my_table",
    model_class=MyModel,
    vector_fields={"custom_vector_field"},
    auto_detect_vector=False
)
```

## Usage Examples

### Before (Manual Parsing Required)

```python
class EmbeddingVectorRepository(BaseRepository[EmbeddingVector, UUID]):
    def __init__(self, connection: AsyncConnection):
        super().__init__(
            db_connection=connection,
            table_name="embedding_vectors",
            model_class=EmbeddingVector,
            primary_key="vector_id",
            json_fields={"metadata"},  # Exclude vector_data from JSON
        )

    async def create(self, embedding: EmbeddingVector) -> EmbeddingVector:
        # Manual parsing workaround
        row = await self._execute_query(...)
        if isinstance(row["vector_data"], str):
            row["vector_data"] = json.loads(row["vector_data"])
        return EmbeddingVector(**row)
```

### After (Automatic Handling)

```python
class EmbeddingVectorRepository(BaseRepository[EmbeddingVector, UUID]):
    def __init__(self, connection: AsyncConnection):
        super().__init__(
            db_connection=connection,
            table_name="embedding_vectors",
            model_class=EmbeddingVector,
            primary_key="vector_id",
            # No manual vector handling needed!
        )

    # All methods work automatically - no parsing needed
```

## Edge Cases to Handle

1. **Missing pgvector package**: Log warning but don't crash
2. **Mixed types**: `list[int]` should NOT be treated as vector
3. **Nested lists**: `list[list[float]]` should NOT be treated as vector
4. **Database without pgvector extension**: Graceful degradation
5. **Connection pooling**: Register adapters per-connection, not globally

## Implementation Notes

1. **Follow existing JSON pattern**: The implementation should mirror the existing JSON adapter logic for consistency
2. **Lazy registration**: Only register pgvector when vector fields are detected
3. **Per-connection registration**: Register adapters on each connection from the pool
4. **Backward compatibility**: Default `auto_detect_vector=True` but allow users to opt-out
5. **Clear error messages**: If pgvector not installed but needed, provide helpful error with installation instructions

## References

- **pgvector documentation**: https://github.com/pgvector/pgvector-python
- **psycopg3 adapter docs**: https://www.psycopg.org/psycopg3/docs/basic/adapt.html
- **Existing JSON adapter**: See `psycopg_toolkit/utils/type_inspector.py` for pattern

## Success Criteria

- ✅ `list[float]` fields auto-detected in Pydantic models
- ✅ pgvector adapter auto-registered when vector fields detected
- ✅ CRUD operations work without manual string parsing
- ✅ Optional dependency installed only when needed
- ✅ Backward compatible - existing code continues working
- ✅ Clear error messages when pgvector not installed
- ✅ Tests passing for auto-detection and CRUD operations

## Discovery Context

This requirement was discovered while implementing the embeddings feature in Factflow, where:
- PostgreSQL column: `vector_data vector NOT NULL`
- Python type: `vector_data: list[float]`
- Issue: Returns as string `"[0.1,0.2,0.3]"` instead of `[0.1, 0.2, 0.3]`
- Workaround: Manual `json.loads()` parsing in 10+ methods

The pattern is very similar to how psycopg-toolkit already handles JSON/JSONB columns, making this a natural extension of the existing adapter system.
