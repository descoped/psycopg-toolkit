"""Test cases for array_fields parameter functionality."""

from uuid import UUID, uuid4

import pytest
from psycopg import AsyncConnection
from pydantic import BaseModel

from psycopg_toolkit import BaseRepository


class ModelWithArrays(BaseModel):
    """Model with both array and JSONB fields."""

    id: UUID
    name: str
    tags: list[str]  # Should be PostgreSQL array
    categories: list[str]  # Should be PostgreSQL array
    metadata: dict[str, str]  # Should be JSONB
    settings: dict[str, str] | None = None  # Should be JSONB


class ArrayFieldRepository(BaseRepository[ModelWithArrays, UUID]):
    """Repository demonstrating array field handling."""

    def __init__(self, db_connection: AsyncConnection):
        super().__init__(
            db_connection=db_connection,
            table_name="array_test",
            model_class=ModelWithArrays,
            primary_key="id",
            auto_detect_json=True,  # Will detect all list/dict fields as JSON
            array_fields={"tags", "categories"},  # But these should remain arrays
        )


@pytest.fixture
async def array_test_table(db_connection):
    """Create test table with array fields."""
    async with db_connection.cursor() as cur:
        await cur.execute("DROP TABLE IF EXISTS array_test CASCADE")

        await cur.execute("""
            CREATE TABLE array_test (
                id UUID PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                tags TEXT[],
                categories TEXT[],
                metadata JSONB,
                settings JSONB
            )
        """)

        await db_connection.commit()

    yield db_connection

    async with db_connection.cursor() as cur:
        await cur.execute("DROP TABLE IF EXISTS array_test CASCADE")
        await db_connection.commit()


class TestArrayFields:
    """Test array_fields parameter functionality."""

    @pytest.mark.asyncio
    async def test_array_fields_preserved(self, array_test_table):
        """Test that fields in array_fields are preserved as PostgreSQL arrays."""
        conn = array_test_table
        repo = ArrayFieldRepository(conn)

        # Create model with array fields
        model = ModelWithArrays(
            id=uuid4(),
            name="test",
            tags=["python", "async", "database"],
            categories=["backend", "orm"],
            metadata={"version": "1.0", "author": "test"},
            settings={"theme": "dark"},
        )

        # Create should work with arrays preserved
        created = await repo.create(model)
        assert created.tags == model.tags
        assert created.categories == model.categories

        # Verify arrays are stored correctly in database
        async with conn.cursor() as cur:
            await cur.execute("SELECT tags, categories FROM array_test WHERE id = %s", [created.id])
            result = await cur.fetchone()

            # Should be PostgreSQL arrays, not JSON
            assert result[0] == ["python", "async", "database"]
            assert result[1] == ["backend", "orm"]

    @pytest.mark.asyncio
    async def test_array_fields_with_auto_detect_false(self, array_test_table):
        """Test array fields when auto_detect_json is False."""
        conn = array_test_table

        class NoAutoDetectRepo(BaseRepository[ModelWithArrays, UUID]):
            def __init__(self, db_connection: AsyncConnection):
                super().__init__(
                    db_connection=db_connection,
                    table_name="array_test",
                    model_class=ModelWithArrays,
                    primary_key="id",
                    auto_detect_json=False,
                    json_fields={"metadata", "settings"},  # Explicit JSON fields
                    array_fields={"tags", "categories"},
                )

        repo = NoAutoDetectRepo(conn)

        model = ModelWithArrays(id=uuid4(), name="test2", tags=["test"], categories=["test"], metadata={"key": "value"})

        created = await repo.create(model)
        assert created.tags == ["test"]
        assert created.metadata == {"key": "value"}

    @pytest.mark.asyncio
    async def test_empty_arrays(self, array_test_table):
        """Test that empty arrays work correctly."""
        conn = array_test_table
        repo = ArrayFieldRepository(conn)

        model = ModelWithArrays(id=uuid4(), name="empty_test", tags=[], categories=[], metadata={})

        created = await repo.create(model)
        assert created.tags == []
        assert created.categories == []

        # Retrieve and verify
        retrieved = await repo.get_by_id(created.id)
        assert retrieved.tags == []
        assert retrieved.categories == []

    @pytest.mark.asyncio
    async def test_array_field_update(self, array_test_table):
        """Test updating array fields."""
        conn = array_test_table
        repo = ArrayFieldRepository(conn)

        # Create initial model
        model = ModelWithArrays(
            id=uuid4(), name="update_test", tags=["v1"], categories=["initial"], metadata={"version": "1.0"}
        )

        created = await repo.create(model)

        # Update arrays
        updated = await repo.update(created.id, {"tags": ["v1", "v2", "v3"], "categories": ["initial", "updated"]})

        assert updated.tags == ["v1", "v2", "v3"]
        assert updated.categories == ["initial", "updated"]

        # Verify in database
        async with conn.cursor() as cur:
            await cur.execute("SELECT tags, categories FROM array_test WHERE id = %s", [created.id])
            result = await cur.fetchone()
            assert len(result[0]) == 3
            assert len(result[1]) == 2
