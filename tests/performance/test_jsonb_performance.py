"""JSONB performance benchmarks."""

import json
import statistics
import sys
import time
from pathlib import Path

import pytest

from psycopg_toolkit.utils.json_handler import JSONHandler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import ComplexJSON, SimpleJSON
from repositories.jsonb_repositories import ComplexJSONRepository, SimpleJSONRepository

# Using the custom repositories from the main test suite
# These handle SERIAL IDs properly


async def measure_time(func, iterations: int = 1) -> dict[str, float]:
    """Measure execution time of an async function."""
    times = []

    for _ in range(iterations):
        start = time.perf_counter()
        await func()
        end = time.perf_counter()
        times.append(end - start)

    return {"avg": statistics.mean(times), "min": min(times), "max": max(times), "total": sum(times)}


@pytest.mark.asyncio
@pytest.mark.performance
class TestJSONBPerformance:
    """Performance benchmarks for JSONB operations."""

    async def test_serialization_performance(self):
        """Benchmark JSON serialization performance."""
        test_data = {
            "small": {"key": "value", "number": 42},
            "medium": {"data": {f"key_{i}": f"value_{i}" for i in range(50)}, "array": list(range(100))},
            "large": {
                "nested": {f"level1_{i}": {f"level2_{j}": list(range(10)) for j in range(10)} for i in range(10)}
            },
        }

        print("\n=== Serialization Performance ===")

        for size, data in test_data.items():
            # Measure serialization
            def serialize(data=data):
                return JSONHandler.serialize(data)

            async def async_serialize():
                return serialize()

            result = await measure_time(async_serialize, 1000)
            print(f"{size}: avg={result['avg'] * 1000:.3f}ms")

    async def test_insert_performance(self, jsonb_tables):
        """Benchmark insert performance."""
        repo = SimpleJSONRepository(jsonb_tables)

        # Test data
        small_data = {"key": "value"}
        medium_data = {
            "metadata": {"type": "test", "version": 1},
            "items": [{"id": i, "value": f"item_{i}"} for i in range(10)],
        }
        large_data = {f"section_{i}": {"data": [j * 2 for j in range(50)], "metadata": {"index": i}} for i in range(20)}

        print("\n=== Insert Performance ===")

        for name, data in [("small", small_data), ("medium", medium_data), ("large", large_data)]:

            async def insert(data=data):
                await repo.create(SimpleJSON(data=data))

            result = await measure_time(insert, 100)
            print(f"{name}: avg={result['avg'] * 1000:.3f}ms")

    async def test_bulk_insert_performance(self, jsonb_tables):
        """Benchmark bulk insert performance."""
        repo = ComplexJSONRepository(jsonb_tables)

        print("\n=== Bulk Insert Performance ===")

        for batch_size in [10, 50, 100]:
            # Generate test data
            records = [
                ComplexJSON(
                    name=f"bulk_{i}",
                    metadata={"index": i, "batch": True},
                    tags=[f"tag_{i % 5}"],
                    settings={"enabled": i % 2 == 0},
                )
                for i in range(batch_size)
            ]

            async def bulk_insert(records=records):
                await repo.create_bulk(records)

            result = await measure_time(bulk_insert, 10)
            per_record = (result["avg"] / batch_size) * 1000
            print(f"Batch {batch_size}: total={result['avg'] * 1000:.1f}ms, per record={per_record:.3f}ms")

    async def test_query_performance(self, jsonb_tables):
        """Benchmark query performance."""
        repo = ComplexJSONRepository(jsonb_tables)

        # Insert test data
        print("\n=== Preparing query test data ===")
        for i in range(1000):
            await repo.create(
                ComplexJSON(
                    name=f"query_test_{i}",
                    metadata={"type": "performance", "index": i, "category": f"cat_{i % 10}"},
                    tags=[f"tag_{i % 20}"],
                    settings={"active": i % 2 == 0},
                )
            )

        print("\n=== Query Performance ===")

        # Test different query types
        async def query_all():
            await repo.get_all()

        async def query_by_id():
            await repo.get_by_id(500)

        async def query_jsonb_containment():
            async with repo.db_connection.cursor() as cur:
                await cur.execute(
                    "SELECT * FROM jsonb_complex WHERE metadata @> %s", [json.dumps({"type": "performance"})]
                )
                await cur.fetchall()

        async def query_jsonb_key():
            async with repo.db_connection.cursor() as cur:
                await cur.execute("SELECT * FROM jsonb_complex WHERE metadata->>'category' = 'cat_5'")
                await cur.fetchall()

        # Measure queries
        for name, func in [
            ("get_all (1000 records)", query_all),
            ("get_by_id", query_by_id),
            ("jsonb containment (@>)", query_jsonb_containment),
            ("jsonb key extraction (->>')", query_jsonb_key),
        ]:
            result = await measure_time(func, 10)
            print(f"{name}: avg={result['avg'] * 1000:.3f}ms")

    async def test_update_performance(self, jsonb_tables):
        """Benchmark update performance."""
        repo = ComplexJSONRepository(jsonb_tables)

        # Create test records
        records = []
        for i in range(100):
            record = await repo.create(ComplexJSON(name=f"update_test_{i}", metadata={"version": 1}, tags=["original"]))
            records.append(record)

        print("\n=== Update Performance ===")

        # Test different update sizes
        updates = {
            "small": {"metadata": {"version": 2}},
            "medium": {
                "metadata": {"version": 2, "updated": True},
                "tags": ["updated", "modified"],
                "settings": {"new_field": "value"},
            },
            "large": {
                "metadata": {"version": 2, "history": [{"action": "update", "timestamp": i} for i in range(20)]},
                "tags": [f"tag_{i}" for i in range(10)],
                "settings": {f"setting_{i}": i * 2 for i in range(20)},
            },
        }

        for name, update_data in updates.items():

            async def update(update_data=update_data):
                await repo.update(records[0].id, update_data)

            result = await measure_time(update, 50)
            print(f"{name} update: avg={result['avg'] * 1000:.3f}ms")

    async def test_jsonb_vs_regular_performance(self, jsonb_tables):
        """Compare JSONB vs regular column performance."""
        print("\n=== JSONB vs Regular Column Comparison ===")

        # Create comparison table
        async with jsonb_tables.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS regular_table (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    value INTEGER,
                    description TEXT
                )
            """)

        # Insert comparison
        async def insert_jsonb():
            async with jsonb_tables.cursor() as cur:
                await cur.execute(
                    "INSERT INTO jsonb_simple (data) VALUES (%s)",
                    [json.dumps({"name": "test", "value": 42, "description": "test desc"})],
                )

        async def insert_regular():
            async with jsonb_tables.cursor() as cur:
                await cur.execute(
                    "INSERT INTO regular_table (name, value, description) VALUES (%s, %s, %s)",
                    ["test", 42, "test desc"],
                )

        jsonb_result = await measure_time(insert_jsonb, 100)
        regular_result = await measure_time(insert_regular, 100)

        print(f"JSONB insert: avg={jsonb_result['avg'] * 1000:.3f}ms")
        print(f"Regular insert: avg={regular_result['avg'] * 1000:.3f}ms")
        print(f"JSONB overhead: {((jsonb_result['avg'] / regular_result['avg']) - 1) * 100:.1f}%")

        # Query comparison
        async def query_jsonb():
            async with jsonb_tables.cursor() as cur:
                await cur.execute("SELECT * FROM jsonb_simple WHERE data->>'name' = 'test'")
                await cur.fetchall()

        async def query_regular():
            async with jsonb_tables.cursor() as cur:
                await cur.execute("SELECT * FROM regular_table WHERE name = 'test'")
                await cur.fetchall()

        jsonb_query = await measure_time(query_jsonb, 100)
        regular_query = await measure_time(query_regular, 100)

        print(f"\nJSONB query: avg={jsonb_query['avg'] * 1000:.3f}ms")
        print(f"Regular query: avg={regular_query['avg'] * 1000:.3f}ms")
        print(f"JSONB overhead: {((jsonb_query['avg'] / regular_query['avg']) - 1) * 100:.1f}%")
