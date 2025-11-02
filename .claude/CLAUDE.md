# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **psycopg-toolkit**, a robust PostgreSQL database toolkit for Python applications. It provides enterprise-grade connection pooling, transaction management, and a type-safe repository pattern with Pydantic validation.

**Requirements**: Python 3.11+ | PostgreSQL 12+ | Pydantic v2

### Key Features
- Async/await support using psycopg3
- Connection pooling with automatic retry
- Type-safe repository pattern with generics
- Transaction management with savepoints
- **Comprehensive JSONB support with automatic serialization/deserialization**
- **Native pgvector support with automatic vector field detection**
- Pydantic v2 model integration
- Comprehensive error handling
- Full control over JSON processing modes

## Development Commands

### Core Development
- **Install dependencies**: `uv sync --all-groups`
- **Run tests**: `uv run pytest` (excludes performance tests by default)
- **Run specific test category**:
  - All tests including performance: `uv run pytest -m ""`
  - Only performance tests: `uv run pytest -m performance`
  - Only integration tests: `uv run pytest tests/integration/`
  - Unit tests only: `uv run pytest tests/unit/`
- **Build package**: `uv build`
- **Lint code**: `uv run ruff check`
- **Format code**: `uv run ruff format`
- **Fix linting issues**: `uv run ruff check --fix`
- **Test coverage**: `uv run pytest --cov=src/psycopg_toolkit --cov-report=html`

### Testing
- Tests use pytest with asyncio support
- Integration tests use testcontainers with pgvector/pgvector:pg17
- Test categories are marked with pytest markers:
  - `@pytest.mark.asyncio` - Async tests (auto-detected)
  - `@pytest.mark.performance` - Performance benchmarks (excluded by default)
- Test organization:
  - Unit tests: `tests/unit/` (mocked, no database)
  - Integration tests: `tests/integration/` (real PostgreSQL via testcontainers)
  - Performance tests: `tests/performance/` (benchmarks)
  - Test utilities: `tests/repositories/`, `tests/conftest.py`

## Architecture

### Core Components
1. **Database** (`src/psycopg_toolkit/core/database.py`)
   - Main database manager with connection pooling
   - Handles connection retry logic with exponential backoff
   - Manages pool lifecycle and health checks
   - Provides connection context managers
   - **Configurable JSON adapter support** via `enable_json_adapters`

2. **TransactionManager** (`src/psycopg_toolkit/core/transaction.py`)
   - Manages database transactions with savepoint support
   - Provides schema and data lifecycle management
   - Supports nested transactions via savepoints
   - Abstract base classes for SchemaManager and DataManager
   - **JSON adapter configuration in transaction contexts**

3. **BaseRepository** (`src/psycopg_toolkit/repositories/base.py`)
   - Generic repository pattern implementation
   - Type-safe CRUD operations with Pydantic models
   - Supports generic primary key types (UUID, int, str)
   - Bulk operations with batching
   - **Automatic JSONB field detection from type hints**
   - **Automatic pgvector field detection from `list[float]` type hints**
   - **Three JSON processing modes**:
     - Auto-detection with custom processing
     - psycopg native adapters
     - Completely disabled
   - **Array field preservation** via `array_fields` parameter
   - **Automatic date conversion** via `date_fields` parameter
   - **Vector field support** via `vector_fields` parameter

4. **PsycopgHelper** (`src/psycopg_toolkit/utils/psychopg_helper.py`)
   - SQL query builder with injection protection
   - Supports INSERT, SELECT, UPDATE, DELETE operations
   - Batch query generation
   - Uses psycopg's SQL composition for safety

### pgvector Support Components
1. **TypeInspector** (`src/psycopg_toolkit/utils/type_inspector.py`)
   - Automatic detection of `list[float]` fields for pgvector
   - Supports Optional[list[float]] and list[float] | None
   - Excludes vector fields from JSON processing

2. **BaseRepository** (`src/psycopg_toolkit/repositories/base.py`)
   - Lazy async registration of pgvector adapter
   - Per-connection adapter registration
   - Graceful degradation if pgvector not installed
   - `vector_fields` and `auto_detect_vector` parameters

### JSONB Support Components
1. **JSONHandler** (`src/psycopg_toolkit/utils/json_handler.py`)
   - Centralized JSON serialization/deserialization
   - CustomJSONEncoder for UUID, datetime, Decimal, set, frozenset
   - Error handling with descriptive messages
   - Supports Pydantic model serialization via `model_dump()`

2. **TypeInspector** (`src/psycopg_toolkit/utils/type_inspector.py`)
   - Automatic detection of JSON fields from Pydantic models
   - Supports Dict, List, Optional, Union types
   - Handles modern Python type syntax (X | Y)
   - Recursive type inspection for nested structures

3. **JSON-specific Exceptions** (`src/psycopg_toolkit/exceptions.py`)
   - `JSONProcessingError` - Base JSON exception
   - `JSONSerializationError` - Serialization failures with field info
   - `JSONDeserializationError` - Deserialization failures with JSON data

### Exception Hierarchy
```
PsycoDBException (base)
├── DatabaseConnectionError
├── DatabasePoolError
├── DatabaseNotAvailable
└── RepositoryError
    ├── RecordNotFoundError
    ├── InvalidDataError
    ├── OperationError
    └── JSONProcessingError
        ├── JSONSerializationError
        └── JSONDeserializationError
```

### Key Design Patterns
- **Async-first**: All operations are async using psycopg3
- **Connection pooling**: Uses psycopg-pool for connection management
- **Repository pattern**: Generic BaseRepository with type safety
- **Context managers**: Transaction and schema lifecycle management
- **Retry logic**: Exponential backoff for connection attempts
- **Type safety**: Full typing with generics and Pydantic v2 models
- **Flexible JSON handling**: Three modes for different use cases

## JSONB Feature Usage

### Basic Usage (Auto-detection)
```python
from pydantic import BaseModel
from typing import Dict, List, Optional
from psycopg_toolkit import BaseRepository

class UserProfile(BaseModel):
    id: int
    username: str
    preferences: Dict[str, Any]  # Automatically detected as JSONB
    tags: List[str]              # Automatically detected as JSONB
    metadata: Optional[Dict[str, Any]] = None  # Optional JSONB

class UserRepository(BaseRepository[UserProfile, int]):
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="users",
            model_class=UserProfile,
            primary_key="id"
            # auto_detect_json=True is default
        )
```

### Manual JSON Field Specification
```python
class ProductRepository(BaseRepository[Product, UUID]):
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="products",
            model_class=Product,
            primary_key="id",
            json_fields={"specifications", "pricing"},  # Explicit fields
            auto_detect_json=False
        )
```

### Using psycopg Native Adapters (Recommended for Production)
```python
# Database configuration
settings = DatabaseSettings(
    host="localhost",
    port=5432,
    dbname="mydb",
    user="user",
    password="password",
    enable_json_adapters=True  # Enable psycopg's native JSON handling
)

# Repository configuration
class UserRepository(BaseRepository[UserProfile, int]):
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="users",
            model_class=UserProfile,
            primary_key="id",
            auto_detect_json=False  # Let psycopg handle JSON
        )
```

### Completely Disable JSON Processing
```python
# For projects with custom JSON handling
settings = DatabaseSettings(
    ...,
    enable_json_adapters=False  # No psycopg adapters
)

class MyRepository(BaseRepository[MyModel, int]):
    def __init__(self, db_connection):
        super().__init__(
            ...,
            json_fields=set(),      # No JSON fields
            auto_detect_json=False  # No auto-detection
        )
```

### Using Array Fields (PostgreSQL Arrays)
```python
# Preserve PostgreSQL arrays instead of converting to JSONB
class OAuthClient(BaseModel):
    id: UUID
    redirect_uris: List[str]  # Will be TEXT[] array
    grant_types: List[str]    # Will be TEXT[] array
    metadata: Dict[str, Any]  # Will be JSONB

class ClientRepository(BaseRepository[OAuthClient, UUID]):
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="oauth_clients",
            model_class=OAuthClient,
            primary_key="id",
            array_fields={"redirect_uris", "grant_types"}  # Keep as arrays
        )
```

### Using Date Fields (Automatic Conversion)
```python
# Automatically convert PostgreSQL dates to/from strings
class User(BaseModel):
    id: UUID
    username: str
    birthdate: str           # PostgreSQL DATE -> ISO date string
    created_at: str          # PostgreSQL TIMESTAMP -> ISO datetime string
    updated_at: str          # PostgreSQL TIMESTAMPTZ -> ISO datetime string
    last_login: str | None   # Nullable timestamp field

class UserRepository(BaseRepository[User, UUID]):
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="users",
            model_class=User,
            primary_key="id",
            # Include ALL date/timestamp fields
            date_fields={"birthdate", "created_at", "updated_at", "last_login"}
        )
```

### Using pgvector Fields (Automatic Detection)
```python
# Automatically detect and handle vector fields
class DocumentEmbedding(BaseModel):
    id: UUID
    document_id: UUID
    embedding: list[float]              # Auto-detected as vector
    sparse_embedding: list[float] | None = None  # Optional vector
    metadata: dict[str, Any] | None = None       # JSON field

class EmbeddingRepository(BaseRepository[DocumentEmbedding, UUID]):
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="embeddings",
            model_class=DocumentEmbedding,
            primary_key="id",
            auto_detect_vector=True,  # default - detects list[float]
            auto_detect_json=True,    # default - detects dict/list
        )

# Usage - vectors work seamlessly
embedding_vector = [0.1] * 384  # 384-dimensional vector
doc = DocumentEmbedding(
    id=uuid4(),
    document_id=uuid4(),
    embedding=embedding_vector,
    metadata={"model": "all-MiniLM-L6-v2"}
)
created = await repo.create(doc)
assert isinstance(created.embedding, list)  # Returns as list[float], not string!
```

## Configuration

### Database Settings
- `DatabaseSettings` class in `src/psycopg_toolkit/core/config.py`
- Connection pooling configuration (min/max pool size, timeouts)
- Statement timeout configuration
- Connection string building with validation
- **JSON adapter configuration** (`enable_json_adapters`, default: True)

### Repository Configuration
- `auto_detect_json` (default: True) - Automatically detect JSON fields
- `json_fields` - Explicitly specify JSON field names (overrides auto-detection)
- `auto_detect_vector` (default: True) - Automatically detect vector fields
- `vector_fields` - Explicitly specify vector field names (overrides auto-detection)
- `strict_json_processing` (default: False) - Raise exceptions on JSON errors
- `array_fields` - Preserve PostgreSQL arrays (TEXT[], INTEGER[]) instead of JSONB
- `date_fields` - Automatically convert PostgreSQL date/timestamp to/from strings

## Performance Considerations

### JSONB Performance (from benchmarks)
- JSONB operations have ~2-3x overhead vs simple fields
- Bulk operations reduce per-record overhead by 50-70%
- Complex nested JSON: ~50ms for 1000 ops (0.05ms per op)
- GIN indexes are crucial for JSONB query performance
- Memory usage scales with document size

### Best Practices
1. **Use psycopg adapters** for production (best performance)
2. **Use bulk operations** for multiple records
3. **Create GIN indexes** for frequently queried JSONB columns
4. **Keep JSONB documents reasonably sized** (<10KB preferred)
5. **Monitor memory usage** with large JSONB datasets

## Testing Strategy
- Uses testcontainers for PostgreSQL integration tests
- Schema and data managers for test isolation
- Transaction rollback for test cleanup
- Async test support with pytest-asyncio
- **Test categories**:
  - Unit tests: Mock-based, no database required
  - Integration tests: Real PostgreSQL via testcontainers
  - Performance benchmarks: Measure operation timing
  - Edge case tests: Malformed data, error conditions

## CI/CD
- GitHub Actions workflows:
  - `.github/workflows/build-test.yml`: Main CI/CD (excludes performance tests)
  - `.github/workflows/benchmark.yml`: Performance testing (manual/PR trigger)
  - `.github/workflows/release.yml`: PyPI release automation
- Tests against Python 3.11, 3.12, and 3.13
- PostgreSQL 17 in CI environment
- Coverage reporting with pytest-cov
- Renovate for dependency updates
- Linting with ruff

## Project Structure
```
psycopg-toolkit/
├── src/psycopg_toolkit/
│   ├── __init__.py         # Public API exports
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py       # DatabaseSettings
│   │   ├── database.py     # Database manager
│   │   ├── factory.py      # Database factory
│   │   └── transaction.py  # Transaction management
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── base.py         # BaseRepository with JSONB & pgvector
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── json_handler.py     # JSON serialization
│   │   ├── psychopg_helper.py  # SQL query builder
│   │   └── type_inspector.py   # Type detection (JSON & vector)
│   └── exceptions.py       # Exception hierarchy
├── tests/
│   ├── unit/               # Unit tests (mocked)
│   │   ├── test_base_repository.py
│   │   ├── test_base_repository_data_processing.py
│   │   ├── test_custom_json_encoder.py
│   │   ├── test_database.py
│   │   ├── test_field_detection.py
│   │   ├── test_json_exceptions.py
│   │   ├── test_json_handler.py
│   │   ├── test_transaction.py
│   │   └── test_type_inspector.py (includes vector tests)
│   ├── integration/        # Integration tests (testcontainers)
│   │   ├── test_database_container.py
│   │   ├── test_jsonb_basic.py
│   │   ├── test_jsonb_edge_cases.py
│   │   ├── test_jsonb_queries.py
│   │   ├── test_jsonb_transactions.py
│   │   ├── test_array_fields.py
│   │   ├── test_date_fields.py
│   │   └── test_pgvector.py    # pgvector integration tests
│   ├── performance/        # Performance benchmarks
│   │   └── test_jsonb_performance.py
│   ├── repositories/       # Test utilities
│   │   └── jsonb_repositories.py
│   ├── sql/               # Test database schema
│   │   └── init_test_schema.sql (includes pgvector)
│   ├── conftest.py        # Test fixtures
│   ├── schema_and_data.py # Test data management
│   └── test_data.py       # Test data generation
├── examples/
│   ├── basic_usage.py              # Basic repository usage
│   ├── transaction_usage.py        # Transaction examples
│   ├── jsonb_usage.py             # Comprehensive JSONB examples
│   ├── jsonb_usage_simple.py      # Simple JSONB examples
│   ├── complex_json_operations.py  # Advanced JSONB patterns
│   └── array_and_date_fields.py   # Array fields and date conversion
├── docs/
│   ├── base_repository.md    # Repository documentation
│   ├── database.md          # Database manager docs
│   ├── transaction_manager.md # Transaction docs
│   ├── psycopg_helper.md    # SQL builder docs
│   └── jsonb_support.md     # Comprehensive JSONB guide
└── pyproject.toml          # Project configuration
```

## Breaking Changes (v0.1.7+)

### JSONB Auto-detection
- BaseRepository now auto-detects JSON fields by default
- Set `auto_detect_json=False` to maintain old behavior
- DatabaseSettings enables JSON adapters by default (`enable_json_adapters=True`)

### Type Syntax
- Now requires Python 3.11+ (was 3.9+)
- Uses modern union syntax: `X | Y` instead of `Union[X, Y]`
- Uses lowercase generics: `list[T]`, `dict[K, V]`

### New Exceptions
- Added JSON-specific exceptions (non-breaking additions)
- Maintained backwards compatibility for existing exceptions

See `BREAKING_CHANGES.md` for detailed migration guide.

## Recent Changes

### pgvector Support (v0.3.0 - feature/pgvector branch)
- **Native pgvector support** - Auto-detect `list[float]` fields for vector columns
- Lazy async registration of pgvector adapter using `register_vector_async()`
- `vector_fields` and `auto_detect_vector` parameters in BaseRepository
- Automatic exclusion of vector fields from JSON processing
- Graceful degradation if pgvector package not installed
- Optional dependency: `pgvector>=0.4.1` in `vector` dependency group
- **Tests**: 12 unit tests + 4 integration tests (all passing)
- Integration tests use `pgvector/pgvector:pg17` testcontainer
- Float32 precision handling (pgvector uses float32, Python uses float64)

### Test Organization (v0.3.0)
- Reorganized tests into proper subdirectories:
  - `tests/unit/` - Unit tests (mocked, no database)
  - `tests/integration/` - Integration tests (real PostgreSQL)
  - `tests/performance/` - Performance benchmarks
- Updated testcontainers to use `pgvector/pgvector:pg17`
- All 227 tests passing with zero regressions

### JSONB Implementation (v0.1.7)
- Added comprehensive JSONB support with three processing modes
- Automatic detection of JSON fields from Pydantic models
- Seamless serialization/deserialization of complex Python types
- Support for both custom processing and psycopg native adapters
- Option to completely disable JSON processing
- Full test coverage including edge cases and performance benchmarks
- Created comprehensive documentation in `docs/jsonb_support.md`

### Array and Date Field Support (v0.2.1)
- Added `array_fields` parameter to preserve PostgreSQL arrays (TEXT[], INTEGER[])
- Added `date_fields` parameter for automatic date/string conversion
  - **Important**: Include ALL date/timestamp fields (DATE, TIMESTAMP, TIMESTAMPTZ)
  - Converts both date and datetime objects to ISO strings
- Fixed auto_detect_json=False not fully disabling JSON processing
- Improved JSON field detection to exclude array fields
- Added comprehensive tests and examples for new features
- Fixed date field conversion to handle both date and datetime objects

### Code Quality Updates
- All models now use Pydantic v2 syntax
- Fixed model_config usage to use ConfigDict
- Updated all model_dump() calls (no .dict() usage)
- Migrated from flake8 to ruff for linting
- Updated type annotations to Python 3.11+ syntax

### Documentation
- Added comprehensive JSONB support guide
- Updated all documentation to reflect new features
- Created breaking changes documentation
- Added examples for all JSONB usage patterns

## Performance Benchmarks
Performance tests show (1000 operations):
- Simple fields: ~10ms baseline
- JSONB fields: ~25-50ms (2.5-5x overhead)
- Bulk operations: 50-70% faster per record
- Complex nested JSON: Scales with document complexity
- Memory: Increases with document size

## Known Limitations
1. JSONB auto-detection cannot distinguish between PostgreSQL arrays and JSONB (use `array_fields` parameter)
2. Performance overhead for JSONB operations vs simple fields
3. Large JSONB documents (>10KB) impact memory usage
4. No support for JSONB streaming