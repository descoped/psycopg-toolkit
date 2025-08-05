# psycopg-toolkit Examples

This directory contains example scripts demonstrating various features of psycopg-toolkit.

## Available Examples

### Basic Examples

#### [basic_usage.py](basic_usage.py)
Basic introduction to psycopg-toolkit features:
- Database connection setup
- Simple CRUD operations
- Connection pooling
- Basic error handling

#### [repository_pattern.py](repository_pattern.py)
Demonstrates the repository pattern:
- Creating custom repositories
- Extending BaseRepository
- Implementing custom queries
- Type-safe operations with generics

### JSONB Examples

#### [jsonb_usage.py](jsonb_usage.py)
Introduction to JSONB support:
- Models with JSONB fields
- Automatic JSON serialization/deserialization
- Basic CRUD with JSONB data
- Using PostgreSQL JSONB operators

#### [jsonb_usage_simple.py](jsonb_usage_simple.py)
Simplified JSONB example using psycopg's native JSON adapters:
- Minimal configuration
- Direct JSONB operations
- Quick start example

#### [complex_json_operations.py](complex_json_operations.py)
Advanced JSONB operations and patterns:
- Complex nested JSON structures
- Bulk operations with JSONB
- Transaction handling
- Direct JSONB queries using PostgreSQL operators
- Time-series data in JSONB
- Performance optimization techniques
- Comprehensive error handling

#### [array_and_date_fields.py](array_and_date_fields.py)
PostgreSQL arrays and date field handling:
- Using `array_fields` to preserve PostgreSQL arrays (TEXT[], INTEGER[])
- Using `date_fields` for automatic date/string conversion
- Mixing JSONB, arrays, and date fields in one model
- Practical examples with OAuth clients and user profiles

### Advanced Examples

#### [bulk_operations.py](bulk_operations.py)
Efficient bulk data operations:
- Bulk inserts with batching
- Performance considerations
- Transaction management for bulk operations

#### [connection_pool.py](connection_pool.py)
Advanced connection pooling:
- Pool configuration
- Connection lifecycle
- Performance monitoring
- Pool size optimization

#### [custom_repository.py](custom_repository.py)
Creating sophisticated custom repositories:
- Complex query methods
- Aggregations
- Joins and relationships
- Custom result processing

#### [transaction_management.py](transaction_management.py)
Advanced transaction patterns:
- Nested transactions
- Savepoints
- Transaction isolation levels
- Error recovery strategies

## Running the Examples

### Prerequisites

1. PostgreSQL 15+ installed and running
2. Python 3.11+ installed
3. psycopg-toolkit installed:
   ```bash
   pip install psycopg-toolkit
   ```

### Database Setup

Most examples expect a PostgreSQL database with these credentials:
- Host: localhost
- Port: 5432
- Database: psycopg_test
- User: postgres
- Password: postgres

You can create the test database:
```sql
CREATE DATABASE psycopg_test;
```

### Running an Example

```bash
python examples/basic_usage.py
```

For JSONB examples with test data:
```bash
# Setup test schema (for complex examples)
python tests/schema/manage_test_schema.py setup

# Run the example
python examples/complex_json_operations.py
```

## Example Categories

### Getting Started
Start with these examples if you're new to psycopg-toolkit:
1. `basic_usage.py` - Learn the fundamentals
2. `repository_pattern.py` - Understand the repository pattern
3. `jsonb_usage_simple.py` - Quick JSONB introduction

### JSONB Features
For working with JSON data in PostgreSQL:
1. `jsonb_usage.py` - Comprehensive JSONB introduction
2. `complex_json_operations.py` - Advanced patterns and optimization
3. `array_and_date_fields.py` - PostgreSQL arrays vs JSONB and date handling

### Performance & Scale
For production applications:
1. `connection_pool.py` - Connection management
2. `bulk_operations.py` - Handling large datasets
3. `transaction_management.py` - Data consistency

## Best Practices Demonstrated

1. **Type Safety**: All examples use type hints and Pydantic models
2. **Error Handling**: Proper exception handling and recovery
3. **Performance**: Connection pooling and bulk operations
4. **Transactions**: ACID compliance and isolation
5. **JSONB**: Leveraging PostgreSQL's native JSON capabilities

## Contributing

Feel free to contribute additional examples! Make sure to:
- Include comprehensive comments
- Demonstrate best practices
- Handle errors appropriately
- Include setup/teardown as needed
- Update this README