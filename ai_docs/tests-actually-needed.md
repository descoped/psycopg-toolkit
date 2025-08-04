# Tests Actually Needed for psycopg-toolkit

## Overview
After removing 6 mock-based test files (~2,500 lines), we've reduced the test suite from 316 to 198 tests, achieving a **37% reduction** while maintaining all valuable tests.

## Current Test Suite Status

### What We Kept (High Value)
1. **Integration Tests** (7 files, ~2,000 lines)
   - Real PostgreSQL database testing using testcontainers
   - Tests actual JSONB behavior, transactions, and psycopg3 integration
   
2. **Edge Case Tests** (1 file, ~400 lines)
   - Tests malformed JSON, circular references, unicode issues
   - Uses real database to verify error handling

3. **Useful Unit Tests** (3 files, ~500 lines)
   - Type inspection utilities
   - Exception classes
   - Model validation

### What We Removed (Low Value)
Moved to `tests-old/unit/`:
- `test_base_repository_crud_json.py` (1,342 lines of mocked CRUD)
- `test_base_repository_json_detection.py` (~400 lines)
- `test_json_handler.py` (~300 lines)
- `test_custom_json_encoder.py` (~250 lines)
- `test_database_json_adapters.py` (~200 lines)
- `test_base_repository_json_exception_handling.py` (~200 lines)

## Tests We Actually Need (Gap Analysis)

### 1. **Connection Pool Testing** ❌ MISSING
```python
# test_connection_pool_jsonb.py
- Pool exhaustion with JSONB operations
- Connection recovery after failures
- Concurrent JSONB queries under load
- Pool configuration impact on performance
```

### 2. **PostgreSQL-Specific JSONB Features** ❌ MISSING
```python
# test_jsonb_operators.py
- JSONB containment operators (@>, <@)
- JSONB path queries (->>, #>>, @?)
- JSONB indexing (GIN, GiST)
- JSONB aggregation functions
```

### 3. **Real-World Failure Scenarios** ❌ MISSING
```python
# test_jsonb_failures.py
- Network interruption during JSONB write
- Transaction deadlocks with JSONB
- Constraint violations on JSONB fields
- Disk full during large JSONB insert
```

### 4. **Performance Benchmarks** ⚠️ PARTIAL
```python
# Fix existing test_jsonb_performance.py
- JSONB vs JSON column performance
- Index scan vs sequential scan
- Bulk insert optimization
- Query plan analysis
```

### 5. **Type Safety with psycopg3** ✅ COVERED
Already well tested in integration tests

### 6. **Repository Pattern** ✅ COVERED
Base repository functionality tested with real DB

## Recommended New Test Files

### Priority 1: Connection Pool Tests
```python
# tests/integration/test_connection_pool_jsonb.py
class TestConnectionPoolJSONB:
    async def test_pool_exhaustion_recovery(self, postgres_container):
        """Test that pool recovers when all connections are used"""
        
    async def test_concurrent_jsonb_updates(self, postgres_container):
        """Test multiple connections updating same JSONB"""
        
    async def test_connection_leak_detection(self, postgres_container):
        """Test that leaked connections are detected"""
```

### Priority 2: PostgreSQL JSONB Operators
```python
# tests/integration/test_jsonb_operators.py
class TestJSONBOperators:
    async def test_containment_operator(self, db_connection):
        """Test @> and <@ operators"""
        
    async def test_path_operators(self, db_connection):
        """Test ->, ->>, #>, #>> operators"""
        
    async def test_jsonb_indexing(self, db_connection):
        """Test GIN index on JSONB column"""
```

### Priority 3: Failure Scenarios
```python
# tests/integration/test_jsonb_failures.py
class TestJSONBFailures:
    async def test_network_interruption(self, db_connection):
        """Test behavior when connection drops mid-operation"""
        
    async def test_deadlock_recovery(self, db_connection):
        """Test automatic retry on deadlock"""
```

## Summary

### Current State
- **Tests**: 198 (down from 316)
- **Coverage**: Good for basic functionality
- **Quality**: High - focused on real behavior

### Next Steps
1. Fix the one failing performance test
2. Add connection pool tests (Priority 1)
3. Add PostgreSQL-specific JSONB tests (Priority 2)
4. Add failure scenario tests (Priority 3)

### Result
By removing mock tests and focusing on real PostgreSQL behavior, we've created a leaner, more valuable test suite that actually validates the library's real-world usage.