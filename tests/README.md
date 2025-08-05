# psycopg-toolkit Test Suite

## Overview

This directory contains the comprehensive test suite for psycopg-toolkit, organized by test type and functionality.

## Test Structure

```
tests/
├── unit/                      # Unit tests with mocked dependencies
│   ├── test_base_repository.py
│   ├── test_base_repository_data_processing.py
│   ├── test_custom_json_encoder.py
│   ├── test_database.py
│   ├── test_field_detection.py
│   ├── test_json_exceptions.py
│   ├── test_json_handler.py
│   ├── test_transaction.py
│   └── test_type_inspector.py
│
├── performance/              # Performance benchmarks
│   └── test_jsonb_performance.py
│
├── repositories/             # Test repository implementations
│   └── jsonb_repositories.py
│
├── sql/                      # SQL scripts for test setup
│   └── init_test_schema.sql
│
├── test_database_container.py     # Database container tests
├── test_jsonb_basic.py           # Basic JSONB functionality tests
├── test_jsonb_edge_cases.py      # JSONB edge case tests
├── test_jsonb_queries.py         # JSONB query tests
├── test_jsonb_transactions.py    # JSONB transaction tests
│
├── conftest.py              # Pytest configuration and fixtures
├── schema_and_data.py       # Test schema and data management
└── test_data.py            # Test data generation utilities
```

## Test Categories

### Unit Tests (`unit/`)

Unit tests run without a database connection, using mocks to isolate component behavior.

- `test_base_repository.py`: Base repository CRUD operations with mocks
- `test_base_repository_data_processing.py`: JSON field preprocessing/postprocessing
- `test_custom_json_encoder.py`: Custom JSON encoder for special types
- `test_database.py`: Database class functionality with mocks
- `test_field_detection.py`: Automatic JSON field detection from models
- `test_json_exceptions.py`: JSON-related exception classes
- `test_json_handler.py`: JSON serialization/deserialization utilities
- `test_transaction.py`: Transaction manager with mocks
- `test_type_inspector.py`: Type inspection for Pydantic models

### Integration Tests (root level)

Integration tests use a real PostgreSQL database (via testcontainers) to verify actual behavior.

- `test_database_container.py`: Database container setup and basic operations
- `test_jsonb_basic.py`: Basic JSONB CRUD operations with real database
- `test_jsonb_edge_cases.py`: Edge cases, malformed data, size limits, error handling
- `test_jsonb_queries.py`: PostgreSQL JSONB operators and advanced query patterns
- `test_jsonb_transactions.py`: Transactional behavior, rollbacks, and savepoints with JSONB

### Performance Tests (`performance/`)

Performance tests measure operation timing and resource usage:

- `test_jsonb_performance.py`: Comprehensive performance benchmarks for JSONB operations
  - Single record vs bulk operations
  - Simple vs complex nested JSON structures
  - Memory usage profiling
  - Query performance with GIN indexes

### Supporting Files

- `conftest.py`: Pytest configuration and shared fixtures
  - Database container setup
  - Common test models
  - Async test support configuration
- `schema_and_data.py`: Test database schema and data management
  - Schema creation/teardown
  - Test data generation
  - Transaction management for tests
- `test_data.py`: Test data generation utilities
  - Factory functions for test models
  - Random data generators
- `repositories/jsonb_repositories.py`: Test repository implementations
  - Example repositories for JSONB testing
  - Complex query patterns
- `sql/init_test_schema.sql`: SQL schema for integration tests

## Running Tests

### Run All Tests
```bash
uv run pytest
```

### Run Specific Test Categories
```bash
# Unit tests only
uv run pytest tests/unit/

# Integration tests only (excludes unit and performance)
uv run pytest tests/ -k "not unit and not performance"

# Performance benchmarks
uv run pytest tests/performance/ -v

# JSONB-specific tests
uv run pytest tests/ -k "jsonb"
```

### Run with Coverage
```bash
uv run pytest --cov=src/psycopg_toolkit --cov-report=html
```

### Run Specific Test Files
```bash
# JSON handler tests
uv run pytest tests/unit/test_json_handler.py -v

# JSONB basic operations
uv run pytest tests/test_jsonb_basic.py -v
```

## Test Markers

Tests are marked with pytest markers for easy filtering:

- `@pytest.mark.asyncio`: Async tests (automatically detected by pytest-asyncio)
- `@pytest.mark.performance`: Performance benchmarks (excluded by default)
- Unit tests are in the `unit/` directory (no marker needed)
- Integration tests are at the root level (no marker needed)

## Adding New Tests

### 1. Determine Test Type

- **Unit test**: Component behavior in isolation → `unit/`
- **Integration test**: Database interaction → root level
- **Performance test**: Benchmarking → `performance/`

### 2. Choose or Create Appropriate File

- For unit tests, add to appropriate file in `unit/`
- For integration tests, create/use files at root level
- Use `test_` prefix for all test files

### 3. Follow Testing Patterns

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

The CI/CD pipeline excludes performance tests by default. Performance benchmarks are run separately via the benchmark workflow.

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