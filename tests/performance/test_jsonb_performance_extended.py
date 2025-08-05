"""Extended JSONB performance benchmarks with larger datasets and more variations."""

import json
import random
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from psycopg_toolkit.utils.json_handler import JSONHandler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from conftest import ComplexJSON
from repositories.jsonb_repositories import ComplexJSONRepository


async def measure_time(func, iterations: int = 1, warmup: int = 0) -> dict[str, float]:
    """Measure execution time of an async function with optional warmup."""
    # Warmup runs
    for _ in range(warmup):
        await func()

    # Actual measurements
    times = []
    for _ in range(iterations):
        start = time.perf_counter()
        await func()
        end = time.perf_counter()
        times.append(end - start)

    return {
        "avg": statistics.mean(times),
        "min": min(times),
        "max": max(times),
        "median": statistics.median(times),
        "stddev": statistics.stdev(times) if len(times) > 1 else 0,
        "total": sum(times),
        "iterations": iterations,
    }


def generate_complex_data(size: str) -> dict[str, Any]:
    """Generate complex nested data structures of various sizes."""
    if size == "tiny":
        return {"id": 1, "name": "tiny", "value": 42}

    elif size == "small":
        return {
            "id": 1,
            "name": "small",
            "metadata": {"type": "test", "version": 1},
            "items": [{"id": i, "value": f"item_{i}"} for i in range(10)],
        }

    elif size == "medium":
        return {
            "id": 1,
            "name": "medium",
            "metadata": {
                "type": "test",
                "version": 1,
                "tags": [f"tag_{i}" for i in range(20)],
                "properties": {f"prop_{i}": random.random() for i in range(20)},
            },
            "items": [
                {"id": i, "value": f"item_{i}", "attributes": {f"attr_{j}": j * i for j in range(5)}} for i in range(50)
            ],
            "settings": {
                f"section_{i}": {"enabled": i % 2 == 0, "config": {f"param_{j}": j * 10 for j in range(10)}}
                for i in range(10)
            },
        }

    elif size == "large":
        return {
            "id": 1,
            "name": "large",
            "metadata": {
                "type": "test",
                "version": 1,
                "created": datetime.now().isoformat(),
                "tags": [f"tag_{i}" for i in range(100)],
                "categories": [f"cat_{i}" for i in range(50)],
                "properties": {f"prop_{i}": {"value": random.random(), "meta": f"meta_{i}"} for i in range(100)},
            },
            "sections": {
                f"section_{i}": {
                    "title": f"Section {i}",
                    "content": " ".join([f"word_{j}" for j in range(100)]),
                    "items": [
                        {"id": j, "name": f"item_{i}_{j}", "data": {f"field_{k}": k * j for k in range(10)}}
                        for j in range(20)
                    ],
                }
                for i in range(20)
            },
            "matrix": [[random.random() for _ in range(50)] for _ in range(50)],
        }

    elif size == "xlarge":
        # Extra large dataset for stress testing
        return {
            "id": 1,
            "name": "xlarge",
            "metadata": {
                "type": "stress_test",
                "version": 1,
                "created": datetime.now().isoformat(),
                "tags": [f"tag_{i}" for i in range(500)],
                "index": {f"key_{i}": {"value": i, "data": list(range(10))} for i in range(200)},
            },
            "data": {
                f"dataset_{i}": {
                    "values": [random.random() for _ in range(100)],
                    "metadata": {"mean": random.random(), "std": random.random(), "samples": 100},
                    "nested": {
                        f"level2_{j}": {"data": [k * 2 for k in range(20)], "meta": {"index": j}} for j in range(10)
                    },
                }
                for i in range(50)
            },
            "large_array": [{"id": i, "value": random.random(), "text": f"item_{i}" * 10} for i in range(1000)],
        }

    return {}


@pytest.mark.asyncio
@pytest.mark.performance
class TestJSONBPerformanceExtended:
    """Extended performance benchmarks for JSONB operations."""

    async def test_serialization_performance_extended(self):
        """Benchmark JSON serialization with various data sizes and complexities."""
        print("\n=== Extended Serialization Performance ===")
        print("(Testing with warmup runs and multiple iterations)")

        sizes = ["tiny", "small", "medium", "large", "xlarge"]

        for size in sizes:
            data = generate_complex_data(size)
            data_size_kb = len(json.dumps(data)) / 1024

            async def serialize(data=data):
                return JSONHandler.serialize(data)

            # More iterations for smaller data, fewer for larger
            iterations = (
                10000
                if size == "tiny"
                else 5000
                if size == "small"
                else 1000
                if size == "medium"
                else 100
                if size == "large"
                else 10
            )

            result = await measure_time(serialize, iterations=iterations, warmup=10)

            print(f"\n{size.upper()} ({data_size_kb:.1f} KB):")
            print(f"  Avg: {result['avg'] * 1000:.3f}ms")
            print(f"  Min: {result['min'] * 1000:.3f}ms")
            print(f"  Max: {result['max'] * 1000:.3f}ms")
            print(f"  Median: {result['median'] * 1000:.3f}ms")
            print(f"  StdDev: {result['stddev'] * 1000:.3f}ms")
            print(f"  Throughput: {data_size_kb / result['avg']:.1f} KB/s")

    async def test_bulk_operations_scaling(self, jsonb_tables):
        """Test how bulk operations scale with different batch sizes."""
        repo = ComplexJSONRepository(jsonb_tables)

        print("\n=== Bulk Operations Scaling ===")

        batch_sizes = [1, 10, 50, 100, 250, 500, 1000]

        for batch_size in batch_sizes:
            # Generate diverse test data
            records = [
                ComplexJSON(
                    name=f"bulk_{i}",
                    metadata={
                        "index": i,
                        "batch": batch_size,
                        "category": f"cat_{i % 20}",
                        "timestamp": datetime.now().isoformat(),
                        "random": random.random(),
                    },
                    tags=[f"tag_{i % 50}", f"batch_{batch_size}", f"group_{i // 10}"],
                    settings={
                        "enabled": i % 2 == 0,
                        "priority": i % 5,
                        "config": {f"param_{j}": j * i for j in range(5)},
                    },
                )
                for i in range(batch_size)
            ]

            async def bulk_insert(records=records):
                await repo.create_bulk(records)

            # Fewer iterations for larger batches
            iterations = max(1, 100 // (batch_size // 10 + 1))
            result = await measure_time(bulk_insert, iterations=iterations, warmup=1)

            per_record = (result["avg"] / batch_size) * 1000
            total_ms = result["avg"] * 1000
            throughput = batch_size / result["avg"]

            print(
                f"\nBatch {batch_size:4d}: {total_ms:7.1f}ms total, {per_record:6.3f}ms/record, {throughput:6.1f} records/s"
            )

    async def test_query_performance_comprehensive(self, jsonb_tables):
        """Comprehensive query performance testing with various patterns."""
        repo = ComplexJSONRepository(jsonb_tables)

        print("\n=== Preparing comprehensive query test data ===")

        # Insert varied test data
        total_records = 5000
        for i in range(total_records):
            await repo.create(
                ComplexJSON(
                    name=f"query_test_{i}",
                    metadata={
                        "type": "performance",
                        "index": i,
                        "category": f"cat_{i % 50}",
                        "priority": i % 10,
                        "timestamp": datetime.now().isoformat(),
                        "nested": {"level1": f"value_{i % 20}", "level2": {"data": i * 2, "flag": i % 3 == 0}},
                    },
                    tags=[f"tag_{i % 100}", f"group_{i // 100}", f"type_{i % 10}"],
                    settings={
                        "active": i % 2 == 0,
                        "score": random.randint(0, 100),
                        "config": {"option1": i % 5 == 0, "option2": f"value_{i % 20}"},
                    },
                )
            )

        print(f"Inserted {total_records} records for query testing")
        print("\n=== Query Performance Results ===")

        # Define various query patterns
        queries = [
            ("Full table scan", "SELECT * FROM jsonb_complex", None),
            ("ID lookup (middle)", "SELECT * FROM jsonb_complex WHERE id = %s", [total_records // 2]),
            (
                "JSONB containment (simple)",
                "SELECT * FROM jsonb_complex WHERE metadata @> %s",
                [json.dumps({"type": "performance"})],
            ),
            (
                "JSONB containment (nested)",
                "SELECT * FROM jsonb_complex WHERE metadata @> %s",
                [json.dumps({"nested": {"level1": "value_10"}})],
            ),
            ("JSONB key extraction", "SELECT * FROM jsonb_complex WHERE metadata->>'category' = %s", ["cat_25"]),
            (
                "JSONB nested key extraction",
                "SELECT * FROM jsonb_complex WHERE metadata->'nested'->>'level1' = %s",
                ["value_15"],
            ),
            ("JSONB array contains", "SELECT * FROM jsonb_complex WHERE tags @> %s", [json.dumps(["tag_50"])]),
            ("JSONB numeric comparison", "SELECT * FROM jsonb_complex WHERE (metadata->>'priority')::int > %s", [5]),
            (
                "JSONB complex condition",
                """SELECT * FROM jsonb_complex
                WHERE metadata @> %s
                AND tags @> %s
                AND (settings->>'score')::int > %s""",
                [json.dumps({"type": "performance"}), json.dumps(["group_10"]), 50],
            ),
            ("JSONB path exists", "SELECT * FROM jsonb_complex WHERE metadata ? 'nested'", None),
        ]

        for name, query, params in queries:

            async def run_query(query=query, params=params):
                async with repo.db_connection.cursor() as cur:
                    if params:
                        await cur.execute(query, params)
                    else:
                        await cur.execute(query)
                    results = await cur.fetchall()
                    return len(results)

            # First run to get result count
            count = await run_query()

            # Performance measurement
            iterations = 20 if "full table" in name.lower() else 50
            result = await measure_time(run_query, iterations=iterations, warmup=2)

            print(f"\n{name}:")
            print(f"  Results: {count} rows")
            print(f"  Avg: {result['avg'] * 1000:.3f}ms")
            print(f"  Min: {result['min'] * 1000:.3f}ms")
            print(f"  Max: {result['max'] * 1000:.3f}ms")
            print(f"  StdDev: {result['stddev'] * 1000:.3f}ms")

    async def test_update_performance_patterns(self, jsonb_tables):
        """Test various update patterns and their performance."""
        repo = ComplexJSONRepository(jsonb_tables)

        print("\n=== Update Performance Patterns ===")

        # Create test records with varied data
        records = []
        for i in range(500):
            record = await repo.create(
                ComplexJSON(
                    name=f"update_test_{i}",
                    metadata={"version": 1, "index": i, "data": {f"field_{j}": j for j in range(10)}},
                    tags=[f"original_{i % 10}"],
                    settings={"score": i, "active": True},
                )
            )
            records.append(record)

        update_patterns = [
            ("Single field update", {"metadata": {"version": 2}}),
            (
                "Multiple fields update",
                {
                    "metadata": {"version": 2, "updated": True},
                    "tags": ["updated", "modified", "v2"],
                    "settings": {"active": False},
                },
            ),
            (
                "Deep nested update",
                {
                    "metadata": {
                        "version": 2,
                        "data": {f"field_{j}": j * 2 for j in range(20)},
                        "nested": {"level1": {"level2": {"level3": "deep_value"}}},
                    }
                },
            ),
            (
                "Array append simulation",
                {"tags": [f"tag_{i}" for i in range(50)], "metadata": {"array_data": list(range(100))}},
            ),
            (
                "Large payload update",
                {
                    "metadata": generate_complex_data("medium"),
                    "settings": {f"setting_{i}": {"value": i, "data": list(range(10))} for i in range(50)},
                },
            ),
        ]

        for name, update_data in update_patterns:
            # Pick different records for each pattern
            target_records = random.sample(records, 50)

            async def update(record=target_records[0], data=update_data):
                await repo.update(record.id, data)

            result = await measure_time(update, iterations=50, warmup=5)

            update_size_kb = len(json.dumps(update_data)) / 1024
            print(f"\n{name} ({update_size_kb:.1f} KB):")
            print(f"  Avg: {result['avg'] * 1000:.3f}ms")
            print(f"  Min: {result['min'] * 1000:.3f}ms")
            print(f"  Max: {result['max'] * 1000:.3f}ms")
            print(f"  StdDev: {result['stddev'] * 1000:.3f}ms")

    async def test_jsonb_vs_regular_detailed(self, jsonb_tables):
        """Detailed comparison of JSONB vs regular columns with various scenarios."""
        print("\n=== Detailed JSONB vs Regular Column Comparison ===")
        sys.stdout.flush()

        # Create comparison tables
        try:
            async with jsonb_tables.cursor() as cur:
                # Clean up any existing data
                await cur.execute("DROP TABLE IF EXISTS regular_normalized CASCADE")

                # Regular normalized table
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS regular_normalized (
                    id SERIAL PRIMARY KEY,
                    name TEXT,
                    type TEXT,
                    priority INTEGER,
                    score NUMERIC,
                    active BOOLEAN,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
            """)

                # Create indexes for fair comparison
                await cur.execute("CREATE INDEX IF NOT EXISTS idx_regular_type ON regular_normalized(type)")
                await cur.execute("CREATE INDEX IF NOT EXISTS idx_regular_priority ON regular_normalized(priority)")
                await cur.execute("CREATE INDEX IF NOT EXISTS idx_jsonb_metadata ON jsonb_complex USING GIN (metadata)")
        except Exception as e:
            print(f"ERROR creating tables: {e}")
            sys.stdout.flush()
            raise

        scenarios = [
            ("Simple insert", 100),
            ("Bulk insert", 1000),
            ("Complex query", 100),
            ("Update single field", 100),
            ("Update multiple fields", 100),
        ]

        results = []
        print(f"DEBUG: Starting {len(scenarios)} scenarios...")
        sys.stdout.flush()

        for scenario, iterations in scenarios:
            print(f"\n{scenario}:")
            sys.stdout.flush()

            if "insert" in scenario.lower():
                if "simple" in scenario.lower():

                    async def jsonb_op():
                        async with jsonb_tables.cursor() as cur:
                            await cur.execute(
                                "INSERT INTO jsonb_simple (data) VALUES (%s)",
                                [
                                    json.dumps(
                                        {
                                            "name": "test",
                                            "type": "performance",
                                            "priority": random.randint(1, 10),
                                            "score": random.random() * 100,
                                            "active": random.choice([True, False]),
                                            "created_at": datetime.now().isoformat(),
                                        }
                                    )
                                ],
                            )

                    async def regular_op():
                        async with jsonb_tables.cursor() as cur:
                            await cur.execute(
                                """INSERT INTO regular_normalized
                                   (name, type, priority, score, active, created_at)
                                   VALUES (%s, %s, %s, %s, %s, %s)""",
                                [
                                    "test",
                                    "performance",
                                    random.randint(1, 10),
                                    random.random() * 100,
                                    random.choice([True, False]),
                                    datetime.now(),
                                ],
                            )

                elif "bulk" in scenario.lower():
                    # Prepare bulk data
                    jsonb_data = [
                        json.dumps(
                            {
                                "name": f"bulk_{i}",
                                "type": "performance",
                                "priority": i % 10,
                                "score": random.random() * 100,
                                "active": i % 2 == 0,
                            }
                        )
                        for i in range(100)
                    ]

                    regular_data = [
                        (f"bulk_{i}", "performance", i % 10, random.random() * 100, i % 2 == 0, datetime.now())
                        for i in range(100)
                    ]

                    async def jsonb_op(data=jsonb_data):
                        async with jsonb_tables.cursor() as cur:
                            await cur.executemany("INSERT INTO jsonb_simple (data) VALUES (%s)", [(d,) for d in data])

                    async def regular_op(data=regular_data):
                        async with jsonb_tables.cursor() as cur:
                            await cur.executemany(
                                """INSERT INTO regular_normalized
                                   (name, type, priority, score, active, created_at)
                                   VALUES (%s, %s, %s, %s, %s, %s)""",
                                data,
                            )

                    iterations = 10  # Fewer iterations for bulk

            elif "query" in scenario.lower():

                async def jsonb_op():
                    async with jsonb_tables.cursor() as cur:
                        await cur.execute(
                            """SELECT * FROM jsonb_simple
                               WHERE data @> %s
                               AND (data->>'priority')::int > %s""",
                            [json.dumps({"type": "performance"}), 5],
                        )
                        await cur.fetchall()

                async def regular_op():
                    async with jsonb_tables.cursor() as cur:
                        await cur.execute(
                            """SELECT * FROM regular_normalized
                               WHERE type = %s AND priority > %s""",
                            ["performance", 5],
                        )
                        await cur.fetchall()

            elif "update" in scenario.lower():
                if "single" in scenario.lower():

                    async def jsonb_op():
                        async with jsonb_tables.cursor() as cur:
                            await cur.execute(
                                """UPDATE jsonb_simple
                                   SET data = jsonb_set(data, '{priority}', %s)
                                   WHERE (data->>'type') = %s""",
                                [str(random.randint(1, 10)), "performance"],
                            )

                    async def regular_op():
                        async with jsonb_tables.cursor() as cur:
                            await cur.execute(
                                """UPDATE regular_normalized
                                   SET priority = %s
                                   WHERE type = %s""",
                                [random.randint(1, 10), "performance"],
                            )

                else:  # multiple fields

                    async def jsonb_op():
                        async with jsonb_tables.cursor() as cur:
                            await cur.execute(
                                """UPDATE jsonb_simple
                                   SET data = data || %s
                                   WHERE (data->>'type') = %s""",
                                [
                                    json.dumps(
                                        {
                                            "priority": random.randint(1, 10),
                                            "score": random.random() * 100,
                                            "active": random.choice([True, False]),
                                            "updated_at": datetime.now().isoformat(),
                                        }
                                    ),
                                    "performance",
                                ],
                            )

                    async def regular_op():
                        async with jsonb_tables.cursor() as cur:
                            await cur.execute(
                                """UPDATE regular_normalized
                                   SET priority = %s, score = %s, active = %s, updated_at = %s
                                   WHERE type = %s""",
                                [
                                    random.randint(1, 10),
                                    random.random() * 100,
                                    random.choice([True, False]),
                                    datetime.now(),
                                    "performance",
                                ],
                            )

            # Measure performance
            jsonb_result = await measure_time(jsonb_op, iterations=iterations, warmup=5)
            regular_result = await measure_time(regular_op, iterations=iterations, warmup=5)

            overhead = ((jsonb_result["avg"] / regular_result["avg"]) - 1) * 100

            print(f"  JSONB:   {jsonb_result['avg'] * 1000:.3f}ms (±{jsonb_result['stddev'] * 1000:.3f}ms)")
            print(f"  Regular: {regular_result['avg'] * 1000:.3f}ms (±{regular_result['stddev'] * 1000:.3f}ms)")
            print(f"  Overhead: {overhead:+.1f}%")
            sys.stdout.flush()

            results.append(
                {
                    "scenario": scenario,
                    "jsonb_ms": jsonb_result["avg"] * 1000,
                    "regular_ms": regular_result["avg"] * 1000,
                    "overhead_pct": overhead,
                }
            )

        # Summary
        print("\n=== Summary ===")
        print("Scenario                  JSONB(ms)  Regular(ms)  Overhead")
        print("-" * 60)
        for r in results:
            print(f"{r['scenario']:<24} {r['jsonb_ms']:>9.2f} {r['regular_ms']:>12.2f} {r['overhead_pct']:>+9.1f}%")
        sys.stdout.flush()
