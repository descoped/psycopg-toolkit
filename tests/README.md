# psycopg-toolkit Test Suite

## Overview

This directory contains the comprehensive test suite for psycopg-toolkit, organized by test type and functionality. The test structure has been optimized to reduce redundancy while maintaining complete coverage.

## Test Structure

```
tests/
├── unit/                      # Unit tests with mocked dependencies
│   ├── jsonb/                 # JSONB-specific unit tests
│   │   ├── test_serialization.py    # JSON serialization/deserialization
│   │   ├── test_field_detection.py  # Type inspection and field detection
│   │   └── test_exceptions.py       # Exception handling
│   └── repository/            # Repository pattern unit tests
│       └── test_base_repository_jsonb.py  # BaseRepository with JSONB
│
├── integration/               # Integration tests with real database
│   ├── jsonb/                # JSONB integration tests
│   │   ├── test_crud_operations.py   # CRUD operations with JSONB
│   │   ├── test_native_features.py   # PostgreSQL JSONB operators
│   │   ├── test_transactions.py      # Transactional behavior
│   │   └── test_adapter_modes.py     # Custom vs native adapters
│   └── test_database.py      # Core database functionality
│
├── performance/              # Performance benchmarks
│   └── test_jsonb_benchmarks.py     # JSONB performance tests
│
├── edge_cases/               # Edge case and error scenario tests
│   └── test_jsonb_edge_cases.py    # Malformed data, limits, etc.
│
├── models/                   # Shared test models
│   └── jsonb_models.py      # Pydantic models for testing
│
├── schema/                   # Test database schemas
│   ├── jsonb_test_schema.sql
│   └── manage_test_schema.py
│
└── jsonb_test_utils.py      # Shared utilities for JSONB testing
```

## Test Categories

### Unit Tests (`unit/`)

Unit tests run without a database connection, using mocks to isolate component behavior.

- **JSONB Tests** (`unit/jsonb/`):
  - `test_serialization.py`: Tests JSON encoding/decoding, type handling, round-trip conversion
  - `test_field_detection.py`: Tests automatic detection of JSON fields from Pydantic models
  - `test_exceptions.py`: Tests exception classes and error handling behavior

- **Repository Tests** (`unit/repository/`):
  - `test_base_repository_jsonb.py`: Tests repository logic with mocked database

### Integration Tests (`integration/`)

Integration tests use a real PostgreSQL database (via testcontainers) to verify actual behavior.

- **JSONB Integration** (`integration/jsonb/`):
  - `test_crud_operations.py`: Full CRUD operations with JSONB fields
  - `test_native_features.py`: PostgreSQL-specific JSONB operators (`->`, `->>`, `@>`, etc.)
  - `test_transactions.py`: Transaction boundaries, rollback, savepoints with JSONB
  - `test_adapter_modes.py`: Comparison of custom vs psycopg native JSON handling

### Performance Tests (`performance/`)

- `test_jsonb_benchmarks.py`: Comprehensive performance benchmarks comparing:
  - JSONB vs non-JSONB operations
  - Serialization/deserialization overhead
  - Bulk operation efficiency
  - Query performance with GIN indexes

### Edge Cases (`edge_cases/`)

- `test_jsonb_edge_cases.py`: Tests for:
  - Malformed JSON data
  - Circular references
  - Unicode and special characters
  - Large data structures
  - Numeric precision limits

## Running Tests

### Run All Tests
```bash
uv run pytest
```

### Run Specific Test Categories
```bash
# Unit tests only
uv run pytest tests/unit/

# JSONB tests only
uv run pytest tests/unit/jsonb/ tests/integration/jsonb/

# Integration tests only
uv run pytest tests/integration/

# Performance benchmarks
uv run pytest tests/performance/ -v

# Edge cases
uv run pytest tests/edge_cases/
```

### Run with Coverage
```bash
uv run pytest --cov=psycopg_toolkit --cov-report=html
```

### Run Specific Test Files
```bash
# JSON serialization tests
uv run pytest tests/unit/jsonb/test_serialization.py -v

# CRUD integration tests
uv run pytest tests/integration/jsonb/test_crud_operations.py -v
```

## Test Utilities

The `jsonb_test_utils.py` module provides shared utilities:

- **Data Generators**:
  - `generate_simple_json_data()`: Basic JSON test data
  - `generate_complex_json_data()`: Complex nested structures with special types
  - `generate_edge_case_json_data()`: Edge cases and boundary conditions
  - `generate_bulk_test_data()`: Bulk data for performance testing

- **Assertion Helpers**:
  - `assert_json_equal()`: Compare JSON objects ignoring specific keys
  - `assert_json_structure()`: Validate JSON structure against expected schema
  - `assert_serialization_roundtrip()`: Verify data survives serialization

- **Mock Factories**:
  - `create_mock_json_repository()`: Create mock repository for testing
  - `create_mock_db_connection()`: Create mock database connection

## Adding New Tests

### 1. Determine Test Type

- **Unit test**: Component behavior in isolation → `unit/`
- **Integration test**: Database interaction → `integration/`
- **Performance test**: Benchmarking → `performance/`
- **Edge case**: Error conditions, limits → `edge_cases/`

### 2. Choose or Create Appropriate File

- For JSONB functionality, add to existing JSONB test files
- For new components, create new test files following naming convention
- Use `test_` prefix for all test files

### 3. Use Shared Resources

- Import test models from `models/jsonb_models.py`
- Use utilities from `jsonb_test_utils.py`
- Follow existing test patterns for consistency

### 4. Write Descriptive Tests

```python
class TestYourFeature:
    """Test [component/feature name]."""
    
    def test_specific_behavior(self):
        """Test that [specific behavior description]."""
        # Arrange
        
        # Act
        
        # Assert
```

## Best Practices

1. **Use Fixtures**: Leverage pytest fixtures for common setup
2. **Parametrize Tests**: Use `@pytest.mark.parametrize` for testing multiple scenarios
3. **Mock External Dependencies**: Use mocks in unit tests to isolate behavior
4. **Test One Thing**: Each test should verify a single behavior
5. **Use Descriptive Names**: Test names should describe what they test
6. **Clean Up**: Ensure tests don't leave artifacts or affect other tests

## CI/CD Integration

Tests are automatically run in GitHub Actions on:
- Push to main branch
- Pull requests
- Python versions: 3.11, 3.12, 3.13
- PostgreSQL version: 17

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure you're running from the project root
2. **Database Connection**: Integration tests require Docker for PostgreSQL
3. **Slow Tests**: Use `-k` to run specific tests during development
4. **Test Isolation**: Each test should be independent; check for shared state

### Debug Mode

Run tests with verbose output and stop on first failure:
```bash
uv run pytest -vx
```

Show print statements during test execution:
```bash
uv run pytest -s
```

## Maintenance

- Regularly run the full test suite before commits
- Update tests when adding new features
- Remove redundant tests when refactoring
- Keep test documentation up to date