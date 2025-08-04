# JSONB Test Simplification Plan

## Current Problems
1. **Over-engineered structure**: Nested directories, multiple schemas, duplicate models
2. **Too many tables**: 6+ different table schemas with overlapping purposes
3. **Complex fixtures**: Multiple layers of database/schema setup
4. **Duplicate tests**: Same functionality tested in multiple files
5. **Inconsistent naming**: user_profiles vs users, products vs product_catalog

## Proposed Simple Structure

### 1. Flat Directory Structure
```
tests/
├── conftest.py                    # Shared fixtures
├── test_jsonb_basic.py           # Basic CRUD with JSONB
├── test_jsonb_queries.py         # JSONB query operations  
├── test_jsonb_transactions.py    # Transaction tests
├── test_jsonb_edge_cases.py      # Edge cases & errors
└── test_jsonb_performance.py     # Performance benchmarks
```

### 2. Simple Schema (3 Tables Total)
```sql
-- Table 1: Simple JSONB operations
CREATE TABLE jsonb_simple (
    id SERIAL PRIMARY KEY,
    data JSONB NOT NULL
);

-- Table 2: Complex model with multiple JSONB fields
CREATE TABLE jsonb_complex (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    metadata JSONB NOT NULL,
    tags JSONB,
    settings JSONB
);

-- Table 3: Type comparison testing
CREATE TABLE jsonb_types (
    id SERIAL PRIMARY KEY,
    json_col JSON,      -- For JSON vs JSONB testing
    jsonb_col JSONB
);
```

### 3. Two Simple Models (Cover All Cases)
```python
# models.py or directly in conftest.py
class SimpleJSON(BaseModel):
    id: int
    data: Dict[str, Any]

class ComplexJSON(BaseModel):
    id: int
    name: str
    metadata: Dict[str, Any]
    tags: Optional[List[str]] = None
    settings: Optional[Dict[str, Any]] = None
```

### 4. One Simple Fixture
```python
@pytest.fixture
async def jsonb_tables(db_connection):
    """Create JSONB test tables."""
    async with db_connection.cursor() as cur:
        # Create all 3 tables
        await cur.execute(SIMPLE_SCHEMA)
    
    async with db_connection.transaction():
        yield db_connection
        # Auto-rollback after test
```

## Benefits
1. **Easy to understand**: New developers can grasp the entire test suite quickly
2. **No duplication**: Each test has a clear purpose
3. **Fast execution**: Shared fixtures, simple schema
4. **Easy maintenance**: Changes in one place
5. **Clear test coverage**: Obvious what each file tests

## Migration Steps
1. Create new simplified test files
2. Move essential tests from old structure
3. Remove all duplicate/redundant tests
4. Delete old complex structure
5. Update CI/CD configuration

## What We're Removing
- `/tests/integration/json_tests/` subdirectory
- `/tests/schema/` directory with SQL files
- `/tests/models/jsonb_models.py` (move to conftest)
- `/tests-old/` (already moved)
- Duplicate performance test files
- Complex nested fixtures
- 6+ different table schemas → 3 simple ones
- 10+ model classes → 2 simple ones

## End Result
- **From**: 15+ files, 6+ tables, complex nesting
- **To**: 5 test files, 3 tables, flat structure
- **Reduction**: ~70% less code, 100% easier to maintain