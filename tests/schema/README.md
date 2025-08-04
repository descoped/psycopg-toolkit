# JSONB Test Schema

This directory contains SQL schema definitions and utilities for testing JSONB functionality in psycopg-toolkit.

## Files

- **`jsonb_test_schema.sql`** - Main schema definition with all test tables and indexes
- **`setup_jsonb_tests.sql`** - Setup script that creates schema and inserts sample data
- **`teardown_jsonb_tests.sql`** - Cleanup script to remove test data or drop schema
- **`manage_test_schema.py`** - Python utility to manage the test schema lifecycle

## Test Tables

### 1. **user_profiles**
- Tests basic JSONB fields with user preferences, metadata, and tags
- Includes GIN indexes for query performance
- UUID primary key with auto-generation

### 2. **product_catalog**
- Tests complex nested JSONB structures
- Multiple JSONB fields: specifications, pricing, inventory, attributes
- Demonstrates real-world e-commerce use case

### 3. **configuration**
- Tests optional JSONB fields (nullable metadata)
- Key-value configuration storage pattern
- Simple integer primary key

### 4. **transaction_test**
- Used specifically for transaction testing
- Tracks data changes and history in JSONB
- Auto-incrementing primary key

### 5. **jsonb_performance_test**
- Designed for performance benchmarking
- Multiple JSONB columns of different sizes (small, medium, large)
- Includes helper function to generate data of specific sizes

### 6. **jsonb_edge_cases**
- Tests edge cases and special scenarios
- Stores various JSONB patterns for testing limits

## Indexes

All JSONB columns have GIN (Generalized Inverted Index) indexes for efficient querying:
- Supports containment queries (`@>`, `<@`)
- Enables fast key/value lookups
- Optimizes JSONB-specific operators

## Helper Functions

### `update_updated_at_column()`
Trigger function that automatically updates the `updated_at` timestamp on row modifications.

### `generate_json_data(target_size_kb INTEGER)`
Generates JSONB data of approximately the specified size for performance testing.

## Usage

### Using the Python utility:

```bash
# Create schema and insert test data
python manage_test_schema.py setup

# Check current status
python manage_test_schema.py status

# Clean test data (preserve schema)
python manage_test_schema.py teardown

# Reset (drop and recreate everything)
python manage_test_schema.py reset

# Complete removal
python manage_test_schema.py drop
```

### Using SQL directly:

```bash
# Setup
psql -d your_database -f setup_jsonb_tests.sql

# Teardown
psql -d your_database -f teardown_jsonb_tests.sql
```

### Environment Variables

The Python utility uses these environment variables (with defaults):
- `POSTGRES_HOST` (default: localhost)
- `POSTGRES_PORT` (default: 5432)
- `POSTGRES_DB` (default: psycopg_test)
- `POSTGRES_USER` (default: postgres)
- `POSTGRES_PASSWORD` (default: postgres)

## Integration with Tests

Integration tests can use this schema by:

1. Running setup before tests:
   ```python
   # In test setup
   async def setup_module():
       # Run schema setup
       await execute_sql_file("tests/schema/jsonb_test_schema.sql")
   ```

2. Using the test tables:
   ```python
   # In tests
   repo = BaseRepository(
       db_connection=conn,
       table_name="user_profiles",
       model_class=UserProfile,
       primary_key="id"
   )
   ```

3. Cleaning up after tests:
   ```python
   # In test teardown
   async def teardown_module():
       # Clean test data
       await conn.execute("TRUNCATE TABLE user_profiles CASCADE")
   ```

## Sample Data

The setup script includes sample data for each table:
- 4 user profiles with different preference patterns
- 3 products (laptop, phone, tablet) with detailed specifications
- 3 configuration entries for app settings and feature flags
- 100 performance test records with various JSON sizes
- 8 edge case examples including empty objects, deep nesting, and Unicode

## Performance Considerations

- GIN indexes significantly improve JSONB query performance
- Index size grows with JSONB document complexity
- Use the `jsonb_table_stats` view to monitor table and index sizes
- The `generate_json_data()` function helps create consistent test data for benchmarking

## Best Practices

1. Always use GIN indexes for JSONB columns that will be queried
2. Consider partial indexes for specific query patterns
3. Use JSONB operators (`@>`, `?`, `->`, `->>`) for efficient queries
4. Monitor index bloat and rebuild periodically in production
5. Test with realistic data sizes and complexity