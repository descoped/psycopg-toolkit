"""Integration tests for pgvector support - simple CRUD operations."""

from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel

from psycopg_toolkit.repositories.base import BaseRepository


class VectorModel(BaseModel):
    """Simple model with vector field."""

    id: UUID
    name: str
    embedding: list[float]
    metadata: dict[str, Any] | None = None


class VectorRepository(BaseRepository[VectorModel, UUID]):
    """Repository for vector data."""

    def __init__(self, connection):
        super().__init__(
            db_connection=connection,
            table_name="vectors",
            model_class=VectorModel,
            primary_key="id",
            auto_detect_json=True,
            auto_detect_vector=True,
        )


class TestPgvectorBasics:
    """Test basic pgvector CRUD operations."""

    @pytest.mark.asyncio
    async def test_vector_field_detection(self, db_connection):
        """Test that vector fields are detected correctly."""
        repo = VectorRepository(db_connection)

        # Vector field should be detected
        assert "embedding" in repo.vector_fields

        # Vector field should NOT be in JSON fields
        assert "embedding" not in repo.json_fields

        # Metadata should be in JSON fields
        assert "metadata" in repo.json_fields

    @pytest.mark.asyncio
    async def test_create_and_retrieve_vector(self, db_connection):
        """Test creating and retrieving a record with vector data."""
        repo = VectorRepository(db_connection)

        # Create 384-dimensional vector
        embedding = [0.1 * i for i in range(384)]

        model = VectorModel(
            id=uuid4(),
            name="test-vector",
            embedding=embedding,
            metadata={"source": "test"},
        )

        # Create record
        created = await repo.create(model)

        # Verify vector is returned as list[float]
        assert isinstance(created.embedding, list)
        assert len(created.embedding) == 384
        assert all(isinstance(x, float) for x in created.embedding)
        # Note: pgvector uses float32, slight precision loss expected
        assert all(abs(a - b) < 0.001 for a, b in zip(created.embedding, embedding, strict=True))

        # Retrieve by ID
        retrieved = await repo.get_by_id(created.id)
        assert all(abs(a - b) < 0.001 for a, b in zip(retrieved.embedding, embedding, strict=True))
        assert retrieved.metadata == {"source": "test"}

    @pytest.mark.asyncio
    async def test_update_vector(self, db_connection):
        """Test updating vector data."""
        repo = VectorRepository(db_connection)

        # Create initial record
        embedding = [0.1 * i for i in range(384)]
        model = VectorModel(id=uuid4(), name="update-test", embedding=embedding)
        created = await repo.create(model)

        # Update vector
        new_embedding = [0.2 * i for i in range(384)]
        updated = await repo.update(created.id, {"embedding": new_embedding, "metadata": {"updated": True}})

        # Note: pgvector uses float32, slight precision loss expected
        assert all(abs(a - b) < 0.001 for a, b in zip(updated.embedding, new_embedding, strict=True))
        assert updated.metadata == {"updated": True}

    @pytest.mark.asyncio
    async def test_get_all_with_vectors(self, db_connection):
        """Test retrieving all records with vectors."""
        repo = VectorRepository(db_connection)

        # Create multiple records
        for i in range(3):
            embedding = [float(i) * 0.1 * j for j in range(384)]
            model = VectorModel(id=uuid4(), name=f"batch-{i}", embedding=embedding)
            await repo.create(model)

        # Get all
        all_records = await repo.get_all()

        # Verify all have valid vectors
        assert len(all_records) >= 3
        for record in all_records:
            assert isinstance(record.embedding, list)
            assert len(record.embedding) == 384
            assert all(isinstance(x, float) for x in record.embedding)
