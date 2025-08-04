# JSONB Test Migration Guide for Developers

This guide helps developers understand and adapt to the new consolidated JSONB test structure.

## Overview of Changes

The JSONB test suite has been consolidated to reduce redundancy and improve maintainability:
- **38% reduction** in test code (from ~6,500 to ~4,000 lines)
- **Better organization** with clear separation of concerns
- **Faster execution** with 30-40% reduction in test time
- **Shared utilities** to avoid code duplication

## File Mapping Reference

### Unit Tests

| Old Location | New Location | Notes |
|--------------|--------------|-------|
| `tests/unit/test_custom_json_encoder.py` | `tests/unit/jsonb/test_serialization.py` | Merged with handler tests |
| `tests/unit/test_json_handler.py` | `tests/unit/jsonb/test_serialization.py` | Combined serialization tests |
| `tests/unit/test_type_inspector.py` | `tests/unit/jsonb/test_field_detection.py` | Renamed and consolidated |
| `tests/unit/test_base_repository_json_detection.py` | `tests/unit/jsonb/test_field_detection.py` | Merged detection tests |
| `tests/unit/test_json_exceptions.py` | `tests/unit/jsonb/test_exceptions.py` | Consolidated error handling |
| `tests/unit/test_base_repository_json_exception_handling.py` | `tests/unit/jsonb/test_exceptions.py` | Merged exception tests |
| `tests/unit/test_base_repository_crud_json.py` | `tests/unit/repository/test_base_repository_jsonb.py` | Focused CRUD tests |
| `tests/unit/test_base_repository_data_processing.py` | **Removed** | Merged into other files |

### Integration Tests

| Old Location | New Location | Notes |
|--------------|--------------|-------|
| `tests/integration/test_jsonb_repository.py` | `tests/integration/jsonb/test_crud_operations.py` | Primary CRUD integration |
| `tests/integration/test_jsonb_psycopg_adapters.py` | `tests/integration/jsonb/test_native_features.py` | PostgreSQL-specific features |
| `tests/integration/test_jsonb_custom_processing.py` | `tests/integration/jsonb/test_adapter_modes.py` | Custom vs native adapters |
| `tests/integration/test_jsonb_transactions.py` | `tests/integration/jsonb/test_transactions.py` | Transaction behavior |

### Other Tests

| Old Location | New Location | Notes |
|--------------|--------------|-------|
| `tests/edge_cases/test_malformed_json.py` | `tests/edge_cases/test_jsonb_edge_cases.py` | All edge cases consolidated |
| `tests/performance/test_jsonb_performance.py` | `tests/performance/test_jsonb_benchmarks.py` | Renamed for clarity |

## Key Changes for Test Development

### 1. Use Shared Utilities

The new `tests/jsonb_test_utils.py` provides common functionality:

```python
from tests.jsonb_test_utils import (
    # Data generators
    generate_simple_json_data,
    generate_complex_json_data,
    generate_edge_case_json_data,
    generate_bulk_test_data,
    
    # Assertions
    assert_json_equal,
    assert_json_structure,
    assert_serialization_roundtrip,
    
    # Mocks
    create_mock_json_repository,
    create_mock_db_connection,
    
    # Error helpers
    create_circular_reference,
    create_non_serializable_object,
    create_invalid_json_strings
)
```

### 2. Use Shared Fixtures

New fixtures in `conftest.py`:

```python
@pytest.fixture
def mock_db_connection():
    """Mock database connection for unit tests."""
    
@pytest.fixture
def sample_json_data():
    """Basic JSON test data."""
    
@pytest.fixture
def complex_json_data():
    """Complex JSON with special types."""
    
@pytest.fixture
def jsonb_settings():
    """Database settings with JSON adapters."""
    
@pytest.fixture
def jsonb_database():
    """Database instance for JSONB tests."""
```

### 3. Import Path Updates

Update your imports to use the new structure:

```python
# Old imports
from tests.unit.test_json_handler import JSONHandler
from tests.unit.test_type_inspector import TypeInspector

# New imports
from psycopg_toolkit.utils.json_handler import JSONHandler
from psycopg_toolkit.utils.type_inspector import TypeInspector
```

### 4. Test Organization Pattern

Follow the new organizational pattern:

```python
class TestFeatureCategory:
    """Test [feature] functionality."""
    
    @pytest.mark.asyncio
    async def test_specific_behavior(self):
        """Test that [specific behavior]."""
        # Arrange
        # Act
        # Assert
    
    @pytest.mark.parametrize("param,expected", [...])
    async def test_variations(self, param, expected):
        """Test [feature] with various inputs."""
```

## Common Migration Scenarios

### Scenario 1: Adding a New JSON Serialization Test

**Before:** Add to `test_custom_json_encoder.py` or `test_json_handler.py`

**After:** Add to `tests/unit/jsonb/test_serialization.py` in the appropriate class:
- `TestJSONSerialization` for encoding tests
- `TestJSONDeserialization` for decoding tests
- `TestJSONEdgeCases` for edge cases

### Scenario 2: Testing Repository CRUD with JSON

**Before:** Add to `test_base_repository_crud_json.py` (1,343 lines)

**After:** Add to `tests/unit/repository/test_base_repository_jsonb.py` (focused on CRUD logic)
- Use existing test patterns
- Leverage parametrized tests for variations
- Mock the database connection

### Scenario 3: Testing JSON Field Detection

**Before:** Add to `test_type_inspector.py` or `test_base_repository_json_detection.py`

**After:** Add to `tests/unit/jsonb/test_field_detection.py`:
- `TestTypeInspectorFieldDetection` for detection logic
- `TestBaseRepositoryJSONDetection` for repository integration

### Scenario 4: Testing Error Conditions

**Before:** Scattered across multiple files

**After:** Add to appropriate consolidated file:
- `tests/unit/jsonb/test_exceptions.py` for exception behavior
- `tests/edge_cases/test_jsonb_edge_cases.py` for malformed data

## Running Tests in New Structure

### Run All JSONB Tests
```bash
# Unit tests
uv run pytest tests/unit/jsonb/

# Integration tests
uv run pytest tests/integration/jsonb/

# All JSONB tests
uv run pytest -k jsonb
```

### Run Specific Test Categories
```bash
# Serialization only
uv run pytest tests/unit/jsonb/test_serialization.py

# CRUD operations
uv run pytest tests/unit/repository/test_base_repository_jsonb.py

# Edge cases
uv run pytest tests/edge_cases/test_jsonb_edge_cases.py
```

### Run with Coverage
```bash
# Check JSONB coverage
uv run pytest tests/unit/jsonb/ --cov=psycopg_toolkit.utils --cov-report=html
```

## Best Practices in New Structure

1. **Don't Duplicate Tests**
   - Check consolidated files first
   - Use parametrized tests for variations
   - Leverage shared utilities

2. **Follow Separation of Concerns**
   - Unit tests: Mock external dependencies
   - Integration tests: Test with real database
   - Edge cases: Test error conditions

3. **Use Descriptive Names**
   ```python
   # Good
   def test_serialize_datetime_with_timezone_preserves_offset(self):
   
   # Bad
   def test_datetime(self):
   ```

4. **Leverage Fixtures**
   ```python
   def test_something(self, mock_db_connection, sample_json_data):
       # Use provided fixtures instead of creating new ones
   ```

5. **Keep Tests Focused**
   - One behavior per test
   - Clear arrange-act-assert structure
   - Minimal setup code

## Troubleshooting

### Import Errors
If you get import errors after migration:
1. Check the file mapping table above
2. Update imports to use new paths
3. Ensure you're importing from the source, not test files

### Missing Tests
If tests seem to be missing:
1. Check if they were consolidated into parametrized tests
2. Look in the new edge cases file
3. Search for the test name in consolidated files

### Fixture Not Found
If fixtures are not found:
1. Ensure `conftest.py` is in the test root
2. Check if the fixture was renamed
3. Import from `jsonb_test_utils.py` if needed

## Questions?

If you need help with the migration:
1. Check the consolidation report in `ai_docs/`
2. Review the test README at `tests/README.md`
3. Look at examples in the consolidated test files