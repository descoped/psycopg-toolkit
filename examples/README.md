# psycopg-toolkit Examples

Runnable scripts demonstrating psycopg-toolkit features. Every example starts its own
throwaway PostgreSQL 18 container with [testcontainers](https://testcontainers-python.readthedocs.io/),
so no local database setup is needed.

## Available Examples

### Getting Started

#### [basic_usage.py](basic_usage.py)
- `DatabaseSettings` and `Database` setup against a PostgreSQL container
- Acquiring a pooled connection and running a query

#### [transaction_usage.py](transaction_usage.py)
- `TransactionManager` transactions
- Automatic commit and rollback

### JSONB

#### [jsonb_usage_simple.py](jsonb_usage_simple.py)
Quick start using psycopg's native JSON adapters:
- Minimal configuration
- CRUD with JSONB columns

#### [jsonb_usage.py](jsonb_usage.py)
JSON field handling in `BaseRepository`:
- Automatic JSON field detection from type hints
- Explicit `json_fields` and strict JSON processing
- Serialization error handling

#### [complex_json_operations.py](complex_json_operations.py)
Advanced JSONB patterns:
- Nested Pydantic models and complex JSON structures
- Bulk operations
- Transactions with rollback on validation errors
- Direct JSONB queries using PostgreSQL operators
- Time-series analytics data

#### [array_and_date_fields.py](array_and_date_fields.py)
PostgreSQL arrays and date handling:
- `array_fields` to keep PostgreSQL arrays (`TEXT[]`, `INTEGER[]`) instead of JSONB
- `date_fields` for automatic date/string conversion
- Mixing JSONB, arrays and date fields in one model

## Running the Examples

### Prerequisites

1. Python 3.11+
2. A running Docker daemon (Docker Desktop, Colima, Podman, ...)
3. The project's development environment:
   ```bash
   uv sync --all-groups
   ```

### Running an Example

```bash
uv run python examples/basic_usage.py
```

Note: the development environment deliberately excludes `charset-normalizer` to stay
lean (see `[tool.uv]` in `pyproject.toml`), so `requests` prints a one-time
`RequestsDependencyWarning` about character detection. It is harmless.

## Contributing

New examples are welcome. Please:
- Start a container with `PostgresContainer("postgres:18")` so the example is self-contained
- Include comments and handle errors explicitly
- Make sure the script exits with status 0
- Add it to this README
