# JSONB Performance Benchmarks

This directory contains performance benchmarks for JSONB operations in psycopg-toolkit.

## Overview

The benchmarks compare the performance of JSONB operations against regular (non-JSONB) operations to help understand the overhead and optimize usage patterns.

## Running the Benchmarks

### Quick Run
```bash
# Run all benchmarks
python -m pytest tests/performance/test_jsonb_performance.py -v

# Run with output
python tests/performance/test_jsonb_performance.py
```

### Individual Tests
```bash
# Run specific benchmark
pytest tests/performance/test_jsonb_performance.py::TestJSONBPerformance::test_insert_performance -v
```

## Benchmark Categories

### 1. Serialization/Deserialization
- Measures the overhead of JSON encoding/decoding
- Tests small, medium, and large JSON documents
- Helps understand the CPU cost of JSON processing

### 2. Insert Performance
- Single record inserts
- Bulk insert operations
- Compares simple fields vs JSONB fields
- Tests auto-detection vs manual field specification

### 3. Query Performance
- `get_all()` - Retrieve all records
- `get_by_id()` - Single record lookup
- JSONB containment queries (`@>` operator)
- Impact of GIN indexes

### 4. Update Performance
- Single record updates
- Compares updating simple fields vs JSONB fields
- Measures serialization overhead during updates

### 5. JSON Field Detection
- Performance of automatic JSON field detection
- Tests with models of varying complexity
- Demonstrates the benefit of caching

### 6. Memory Usage
- Memory consumption for large JSONB datasets
- Per-record memory overhead
- Helps with capacity planning

## Understanding Results

### Sample Output
```
=== Single Insert Performance ===
insert_small (simple): avg=0.0012s, min=0.0010s, max=0.0015s, std=0.0001s
insert_small (jsonb_auto): avg=0.0025s, min=0.0022s, max=0.0030s, std=0.0002s
insert_small (jsonb_manual): avg=0.0023s, min=0.0020s, max=0.0028s, std=0.0002s
```

### Key Metrics
- **avg**: Average time per operation
- **min/max**: Range of execution times
- **std**: Standard deviation (consistency)

### Performance Ratios
- JSONB typically has 2-3x overhead vs simple fields
- Bulk operations reduce per-record overhead by 50-70%
- GIN indexes make JSONB queries nearly as fast as regular queries

## Best Practices Based on Results

### 1. Use Bulk Operations
```python
# Slower: Individual inserts
for item in items:
    await repo.create(item)

# Faster: Bulk insert
await repo.create_bulk(items, batch_size=100)
```

### 2. Optimize JSON Document Size
- Keep JSONB documents reasonably sized
- Consider splitting very large objects
- Use compression for archival data

### 3. Create Appropriate Indexes
```sql
-- For containment queries
CREATE INDEX idx_data ON table USING GIN (jsonb_column);

-- For specific key queries (smaller, faster)
CREATE INDEX idx_data_key ON table USING GIN ((jsonb_column -> 'key'));
```

### 4. Consider Manual Field Specification
```python
# Slightly faster with explicit fields
class MyRepository(BaseRepository):
    def __init__(self, conn):
        super().__init__(
            # ...
            json_fields={"data", "metadata"},
            auto_detect_json=False
        )
```

## Factors Affecting Performance

### Document Size
- Small (<1KB): Minimal overhead
- Medium (1-10KB): Noticeable but acceptable overhead
- Large (>10KB): Consider optimization strategies

### Query Patterns
- Simple key lookups: Use GIN indexes
- Complex path queries: Consider jsonb_path_ops
- Frequent updates: Monitor write amplification

### Hardware Considerations
- CPU: JSON parsing is CPU-intensive
- Memory: Large documents increase memory usage
- Storage: GIN indexes require additional disk space

## Benchmark Configuration

The benchmarks use:
- PostgreSQL 17 (via testcontainers)
- Various JSON document sizes
- Multiple iterations for statistical significance
- Garbage collection between measurements

## Extending Benchmarks

To add new benchmarks:

1. Add test method to `TestJSONBPerformance`
2. Use `measure_operation()` for consistent timing
3. Include multiple data sizes/scenarios
4. Document findings in the summary

## Interpreting Results for Your Use Case

1. **High-throughput applications**: Focus on bulk operation results
2. **Real-time systems**: Check min/max times for consistency
3. **Large datasets**: Review memory usage benchmarks
4. **Complex queries**: Test your specific JSONB query patterns

Remember: These benchmarks provide general guidance. Always test with your specific data patterns and workload.