# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **psycopg-toolkit**, a robust PostgreSQL database toolkit for Python applications. It provides enterprise-grade connection pooling, transaction management, and a type-safe repository pattern with Pydantic validation.

**Requirements**: Python 3.11+ | PostgreSQL 12+

### Key Features
- Async/await support using psycopg3
- Connection pooling with automatic retry
- Type-safe repository pattern with generics
- Transaction management with savepoints
- **JSONB support with automatic serialization/deserialization**
- Pydantic model integration
- Comprehensive error handling

## Development Commands

### Core Development
- **Install dependencies**: `uv sync --all-groups`
- **Run tests**: `uv run pytest` (excludes performance tests by default)
- **Run specific test category**: 
  - All tests including performance: `uv run pytest -m ""`
  - Only performance tests: `uv run pytest -m performance`
  - Only integration tests: `uv run pytest -m integration`
  - Unit tests only: `uv run pytest -m "not integration and not performance"`
- **Build package**: `uv build`
- **Lint code**: `uv run ruff check`
- **Format code**: `uv run ruff format`
- **Fix linting issues**: `uv run ruff check --fix`

### Testing
- Tests use pytest with asyncio support
- Integration tests use testcontainers with PostgreSQL 17
- Test categories are marked with pytest markers:
  - `@pytest.mark.asyncio` - Async tests (auto-detected)
  - `@pytest.mark.integration` - Database integration tests
  - `@pytest.mark.performance` - Performance benchmarks (excluded by default)
- Test organization:
  - Unit tests: Throughout the codebase
  - Integration tests: Tests requiring database
  - Performance tests: `tests/performance/`

## Architecture

### Core Components
1. **Database** (`src/psycopg_toolkit/core/database.py`)
   - Main database manager with connection pooling
   - Handles connection retry logic with exponential backoff
   - Manages pool lifecycle and health checks
   - Provides connection context managers
   - **Configurable JSON adapter support**

2. **TransactionManager** (`src/psycopg_toolkit/core/transaction.py`)
   - Manages database transactions with savepoint support
   - Provides schema and data lifecycle management
   - Supports nested transactions via savepoints
   - Abstract base classes for SchemaManager and DataManager
   - **JSON adapter support in transaction contexts**

3. **BaseRepository** (`src/psycopg_toolkit/repositories/base.py`)
   - Generic repository pattern implementation
   - Type-safe CRUD operations with Pydantic models
   - Supports generic primary key types (UUID, int, str)
   - Bulk operations with batching
   - **Automatic JSONB field detection and handling**
   - **Configurable JSON processing (auto-detect or manual)**

4. **PsycopgHelper** (`src/psycopg_toolkit/utils/psychopg_helper.py`)
   - SQL query builder with injection protection
   - Supports INSERT, SELECT, UPDATE, DELETE operations
   - Batch query generation
   - Uses psycopg's SQL composition for safety

### JSONB Support Components
1. **JSONHandler** (`src/psycopg_toolkit/utils/json_handler.py`)
   - Centralized JSON serialization/deserialization
   - Custom encoder for UUID, datetime, Decimal, set, frozenset
   - Error handling with descriptive messages
   - Supports Pydantic model serialization

2. **TypeInspector** (`src/psycopg_toolkit/utils/type_inspector.py`)
   - Automatic detection of JSON fields from Pydantic models
   - Supports Dict, List, Optional, Union types
   - Recursive type inspection for nested structures

3. **JSON-specific Exceptions**
   - `JSONProcessingError` - Base JSON exception
   - `JSONSerializationError` - Serialization failures
   - `JSONDeserializationError` - Deserialization failures

### Exception Hierarchy
- `PsycoDBException` - Base exception
- `DatabaseConnectionError` - Connection failures
- `DatabasePoolError` - Pool management errors
- `DatabaseNotAvailable` - Database unavailability
- `RepositoryError` - Repository operation errors
- `RecordNotFoundError` - Record not found
- `InvalidDataError` - Data validation errors
- `OperationError` - General operation failures
- `JSONProcessingError` - JSON processing errors
  - `JSONSerializationError` - JSON serialization failures
  - `JSONDeserializationError` - JSON deserialization failures

### Key Design Patterns
- **Async-first**: All operations are async using psycopg3
- **Connection pooling**: Uses psycopg-pool for connection management
- **Repository pattern**: Generic BaseRepository with type safety
- **Context managers**: Transaction and schema lifecycle management
- **Retry logic**: Exponential backoff for connection attempts
- **Type safety**: Full typing with generics and Pydantic models
- **Automatic JSON handling**: Seamless JSONB field processing

## JSONB Feature Usage

### Basic Usage
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
            primary_key="id",
            auto_detect_json=True  # Default behavior
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

### Using psycopg Native Adapters
```python
# In DatabaseSettings
settings = DatabaseSettings(
    # ... other settings ...
    enable_json_adapters=True  # Enable psycopg's native JSON handling
)
```

## Configuration

### Database Settings
- Database settings via `DatabaseSettings` class
- Supports connection pooling configuration (min/max pool size, timeouts)
- Statement timeout configuration
- Connection string building with validation
- **JSON adapter configuration** (`enable_json_adapters`)

### Repository Configuration
- `auto_detect_json` (default: True) - Automatically detect JSON fields
- `json_fields` - Explicitly specify JSON field names
- `strict_json_processing` - Raise exceptions on deserialization errors

## Performance Considerations

### JSONB Performance
- JSONB operations have ~2-3x overhead vs simple fields
- Bulk operations reduce per-record overhead by 50-70%
- GIN indexes are crucial for JSONB query performance
- Consider document size impact on memory usage

### Best Practices
1. **Use bulk operations** for multiple records
2. **Create GIN indexes** for frequently queried JSONB columns
3. **Keep JSONB documents reasonably sized** (<10KB preferred)
4. **Use manual field specification** for slight performance gain
5. **Monitor memory usage** with large JSONB datasets

## Testing Strategy
- Uses testcontainers for PostgreSQL integration tests
- Schema and data managers for test isolation
- Transaction rollback for test cleanup
- Async test support with pytest-asyncio
- **JSONB-specific test categories**:
  - Unit tests for JSON handler and type inspector
  - Integration tests for JSONB CRUD operations
  - Transaction tests with JSONB data
  - Edge case tests for malformed JSON
  - Performance benchmarks comparing JSONB vs non-JSONB

## CI/CD
- GitHub Actions workflows:
  - `build-test.yml`: Main CI/CD (excludes performance tests)
  - `benchmark.yml`: Performance testing (runs on PR or manual trigger)
  - `release.yml`: PyPI release automation
- Tests against Python 3.11, 3.12, and 3.13
- PostgreSQL 17 in CI environment
- Coverage reporting to Codecov
- Renovate for dependency updates
- Linting with ruff (replaces flake8)

## Project Structure
```
psycopg-toolkit/
├── src/psycopg_toolkit/
│   ├── core/
│   │   ├── database.py      # Database manager
│   │   ├── transaction.py   # Transaction management
│   │   └── config.py        # Configuration classes
│   ├── repositories/
│   │   └── base.py          # BaseRepository with JSONB support
│   ├── utils/
│   │   ├── json_handler.py  # JSON serialization/deserialization
│   │   ├── type_inspector.py # Automatic JSON field detection
│   │   └── psychopg_helper.py # SQL query builder
│   └── exceptions.py        # Exception hierarchy
├── tests/
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   ├── edge_cases/         # Edge case tests
│   ├── performance/        # Performance benchmarks
│   └── schema/             # Test database schema
├── examples/               # Usage examples
└── docs/                   # Documentation
```

## Recent Changes
### JSONB Implementation (v0.1.7)
- Added comprehensive JSONB support
- Automatic detection of JSON fields from Pydantic models
- Seamless serialization/deserialization of complex Python types
- Support for both custom processing and psycopg native adapters
- Full test coverage including edge cases and performance benchmarks
- Performance benchmarks excluded from default test runs

### Code Quality Updates
- Migrated from flake8 to ruff for linting
- Updated type annotations to use Python 3.10+ syntax (X | Y)
- Fixed TypeInspector to handle modern Union types
- Maintained backwards compatibility for exception names (no Error suffix)

### CI/CD Improvements
- Simplified test workflows using pytest markers
- Performance tests run in dedicated benchmark workflow
- Support for Python 3.11, 3.12, and 3.13