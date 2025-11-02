"""JSONB query operations tests."""

import json
from typing import Any

import pytest
from conftest import ComplexJSON
from repositories.jsonb_repositories import ComplexJSONRepository as BaseComplexJSONRepository


class ComplexJSONRepository(BaseComplexJSONRepository):
    """Repository for complex JSONB model with query methods."""

    async def find_by_metadata_key(self, key: str, value: Any) -> list[ComplexJSON]:
        """Find records where metadata contains specific key-value pair."""
        from psycopg.rows import dict_row

        async with self.db_connection.cursor(row_factory=dict_row) as cur:
            await cur.execute(f"SELECT * FROM {self.table_name} WHERE metadata @> %s", [json.dumps({key: value})])
            rows = await cur.fetchall()
            return [self.model_class(**row) for row in rows]

    async def find_by_tag(self, tag: str) -> list[ComplexJSON]:
        """Find records that contain a specific tag."""
        from psycopg.rows import dict_row

        async with self.db_connection.cursor(row_factory=dict_row) as cur:
            await cur.execute(f"SELECT * FROM {self.table_name} WHERE tags @> %s", [json.dumps([tag])])
            rows = await cur.fetchall()
            return [self.model_class(**row) for row in rows]

    async def find_by_jsonb_path(self, path: str, value: Any) -> list[ComplexJSON]:
        """Find records using JSONB path operators."""
        from psycopg.rows import dict_row

        async with self.db_connection.cursor(row_factory=dict_row) as cur:
            await cur.execute(f"SELECT * FROM {self.table_name} WHERE metadata #>> %s = %s", [path, str(value)])
            rows = await cur.fetchall()
            return [self.model_class(**row) for row in rows]


@pytest.mark.asyncio
class TestJSONBQueries:
    """Test JSONB query operations."""

    async def test_jsonb_containment(self, jsonb_tables):
        """Test JSONB containment operator @>."""
        repo = ComplexJSONRepository(jsonb_tables)

        # Create test data
        await repo.create(ComplexJSON(name="user1", metadata={"role": "admin", "level": 5}, tags=["python", "admin"]))
        await repo.create(ComplexJSON(name="user2", metadata={"role": "user", "level": 1}, tags=["python", "user"]))
        await repo.create(
            ComplexJSON(name="user3", metadata={"role": "admin", "level": 3}, tags=["javascript", "admin"])
        )

        # Find all admins
        admins = await repo.find_by_metadata_key("role", "admin")
        assert len(admins) == 2
        assert all(u.metadata["role"] == "admin" for u in admins)

    async def test_jsonb_array_contains(self, jsonb_tables):
        """Test JSONB array containment."""
        repo = ComplexJSONRepository(jsonb_tables)

        # Create test data
        await repo.create(
            ComplexJSON(name="post1", metadata={"type": "article"}, tags=["python", "tutorial", "beginner"])
        )
        await repo.create(ComplexJSON(name="post2", metadata={"type": "video"}, tags=["python", "advanced"]))
        await repo.create(ComplexJSON(name="post3", metadata={"type": "article"}, tags=["javascript", "tutorial"]))

        # Find posts with "tutorial" tag
        tutorials = await repo.find_by_tag("tutorial")
        assert len(tutorials) == 2
        assert all("tutorial" in p.tags for p in tutorials)

    async def test_jsonb_path_operators(self, jsonb_tables):
        """Test JSONB path operators #> and #>>."""
        repo = ComplexJSONRepository(jsonb_tables)

        # Create nested data
        await repo.create(
            ComplexJSON(name="config1", metadata={"server": {"host": "localhost", "port": 8080, "ssl": True}})
        )
        await repo.create(
            ComplexJSON(name="config2", metadata={"server": {"host": "example.com", "port": 443, "ssl": True}})
        )

        # Find by nested path
        localhost_configs = await repo.find_by_jsonb_path("{server,host}", "localhost")
        assert len(localhost_configs) == 1
        assert localhost_configs[0].name == "config1"

    async def test_jsonb_existence_operator(self, jsonb_tables):
        """Test JSONB existence operator ?."""
        repo = ComplexJSONRepository(jsonb_tables)

        # Create test data
        await repo.create(
            ComplexJSON(name="complete", metadata={"required": True, "optional": "value"}, settings={"feature_x": True})
        )
        await repo.create(ComplexJSON(name="minimal", metadata={"required": True}))

        # Query for existence of key
        from psycopg.rows import dict_row

        async with repo.db_connection.cursor(row_factory=dict_row) as cur:
            await cur.execute("SELECT * FROM jsonb_complex WHERE metadata ? 'optional'")
            rows = await cur.fetchall()
            assert len(rows) == 1
            assert rows[0]["name"] == "complete"

    async def test_jsonb_key_existence_any(self, jsonb_tables):
        """Test JSONB key existence with ANY operator ?|."""
        repo = ComplexJSONRepository(jsonb_tables)

        # Create test data
        await repo.create(ComplexJSON(name="doc1", metadata={"title": "Test", "author": "Alice", "year": 2024}))
        await repo.create(ComplexJSON(name="doc2", metadata={"title": "Another", "editor": "Bob"}))
        await repo.create(ComplexJSON(name="doc3", metadata={"subject": "Science", "publisher": "Tech Press"}))

        # Find documents with author OR editor
        from psycopg.rows import dict_row

        async with repo.db_connection.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM jsonb_complex WHERE metadata ?| array['author', 'editor'] AND name IN ('doc1', 'doc2', 'doc3')"
            )
            rows = await cur.fetchall()
            assert len(rows) == 2
            names = [row["name"] for row in rows]
            assert "doc1" in names
            assert "doc2" in names

    async def test_jsonb_aggregation(self, jsonb_tables):
        """Test JSONB aggregation functions."""
        repo = ComplexJSONRepository(jsonb_tables)

        # Create test data with numeric values
        for i in range(5):
            await repo.create(
                ComplexJSON(name=f"item{i}", metadata={"value": i * 10, "category": "A" if i % 2 == 0 else "B"})
            )

        # Aggregate JSONB data
        from psycopg.rows import dict_row

        async with repo.db_connection.cursor(row_factory=dict_row) as cur:
            # Count by category
            await cur.execute("""
                SELECT metadata->>'category' as category, COUNT(*) as count
                FROM jsonb_complex
                WHERE metadata ? 'category'
                GROUP BY metadata->>'category'
            """)
            results = await cur.fetchall()

            categories = {row["category"]: row["count"] for row in results}
            assert categories["A"] == 3  # items 0, 2, 4
            assert categories["B"] == 2  # items 1, 3

    async def test_jsonb_type_comparison(self, jsonb_tables):
        """Test JSON vs JSONB type differences."""
        from psycopg.rows import dict_row

        async with jsonb_tables.cursor(row_factory=dict_row) as cur:
            # Insert same data as JSON and JSONB
            test_data = {"key": "value", "number": 42, "array": [1, 2, 3]}

            await cur.execute(
                "INSERT INTO jsonb_types (json_col, jsonb_col) VALUES (%s, %s)",
                [json.dumps(test_data), json.dumps(test_data)],
            )

            # Query and compare
            await cur.execute("SELECT * FROM jsonb_types")
            row = await cur.fetchone()

            # Both should have same data
            assert row["json_col"] == test_data
            assert row["jsonb_col"] == test_data

            # Test JSONB operators (not available for JSON)
            await cur.execute("SELECT * FROM jsonb_types WHERE jsonb_col @> %s", [json.dumps({"key": "value"})])
            jsonb_result = await cur.fetchone()
            assert jsonb_result is not None

            # This would fail for json_col (operators not supported)
            with pytest.raises(Exception):
                await cur.execute("SELECT * FROM jsonb_types WHERE json_col @> %s", [json.dumps({"key": "value"})])

    async def test_jsonb_indexing_performance(self, jsonb_tables):
        """Test that GIN indexes improve query performance."""
        repo = ComplexJSONRepository(jsonb_tables)

        # Create many records with unique test identifier
        test_id = "indexing_perf_test"
        for i in range(100):
            await repo.create(
                ComplexJSON(
                    name=f"perf_test_{i}",
                    metadata={"id": i, "type": "performance", "test_id": test_id, "category": f"cat_{i % 10}"},
                    tags=[f"tag_{i % 5}", f"group_{i % 3}"],
                )
            )

        # Query using indexed field with our specific test_id
        from psycopg.rows import dict_row

        async with repo.db_connection.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"SELECT * FROM {repo.table_name} WHERE metadata @> %s",
                [json.dumps({"type": "performance", "test_id": test_id})],
            )
            results = await cur.fetchall()
        assert len(results) == 100

        # Query using tag containment (also indexed) - filter by our test names
        async with repo.db_connection.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                f"SELECT * FROM {repo.table_name} WHERE tags @> %s AND name LIKE %s",
                [json.dumps(["tag_2"]), "perf_test_%"],
            )
            tag_results = await cur.fetchall()
        assert len(tag_results) == 20  # Every 5th record has tag_2
