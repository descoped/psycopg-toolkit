"""Test cases for date_fields parameter functionality."""

from datetime import date
from uuid import UUID, uuid4

import pytest
from psycopg import AsyncConnection
from pydantic import BaseModel

from psycopg_toolkit import BaseRepository


class ModelWithStringDates(BaseModel):
    """Model expecting ISO date strings (common pattern)."""

    id: UUID
    name: str
    created_date: str  # Expects ISO date string
    updated_date: str | None = None  # Optional date string
    metadata: dict[str, str] | None = None


class ModelWithDateObjects(BaseModel):
    """Model using native date objects."""

    id: UUID
    name: str
    created_date: date
    updated_date: date | None = None
    metadata: dict[str, str] | None = None


class StringDateRepository(BaseRepository[ModelWithStringDates, UUID]):
    """Repository for model with string date fields."""

    def __init__(self, db_connection: AsyncConnection):
        super().__init__(
            db_connection=db_connection,
            table_name="date_test",
            model_class=ModelWithStringDates,
            primary_key="id",
            date_fields={"created_date", "updated_date"}  # Convert dates to strings
        )


class DateObjectRepository(BaseRepository[ModelWithDateObjects, UUID]):
    """Repository for model with date object fields."""

    def __init__(self, db_connection: AsyncConnection):
        super().__init__(
            db_connection=db_connection,
            table_name="date_test",
            model_class=ModelWithDateObjects,
            primary_key="id",
            date_fields={"created_date", "updated_date"}  # Handle date conversion
        )


@pytest.fixture
async def date_test_table(db_connection):
    """Create test table with date fields."""
    async with db_connection.cursor() as cur:
        await cur.execute("DROP TABLE IF EXISTS date_test CASCADE")

        await cur.execute("""
            CREATE TABLE date_test (
                id UUID PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                created_date DATE NOT NULL,
                updated_date DATE,
                metadata JSONB
            )
        """)

        await db_connection.commit()

    yield db_connection

    async with db_connection.cursor() as cur:
        await cur.execute("DROP TABLE IF EXISTS date_test CASCADE")
        await db_connection.commit()


class TestDateFields:
    """Test date_fields parameter functionality."""

    @pytest.mark.asyncio
    async def test_date_to_string_conversion(self, date_test_table):
        """Test that PostgreSQL dates are converted to strings for string-typed models."""
        conn = date_test_table
        repo = StringDateRepository(conn)

        # Insert data directly with PostgreSQL date
        test_id = uuid4()
        await conn.execute("""
            INSERT INTO date_test (id, name, created_date, updated_date)
            VALUES (%s, %s, %s, %s)
        """, [test_id, "test", date(2024, 1, 15), date(2024, 1, 20)])
        await conn.commit()

        # Retrieve - dates should be converted to strings
        retrieved = await repo.get_by_id(test_id)
        assert retrieved.created_date == "2024-01-15"
        assert retrieved.updated_date == "2024-01-20"
        assert isinstance(retrieved.created_date, str)
        assert isinstance(retrieved.updated_date, str)

    @pytest.mark.asyncio
    async def test_date_object_preservation(self, date_test_table):
        """Test that date objects are preserved when model expects date type."""
        conn = date_test_table
        repo = DateObjectRepository(conn)

        model = ModelWithDateObjects(
            id=uuid4(),
            name="date_test",
            created_date=date(2024, 3, 1),
            updated_date=date(2024, 3, 15)
        )

        created = await repo.create(model)
        assert created.created_date == date(2024, 3, 1)
        assert isinstance(created.created_date, date)

        # Retrieve and verify
        retrieved = await repo.get_by_id(created.id)
        assert retrieved.created_date == date(2024, 3, 1)
        assert isinstance(retrieved.created_date, date)

    @pytest.mark.asyncio
    async def test_optional_date_with_none(self, date_test_table):
        """Test that optional date fields handle None correctly."""
        conn = date_test_table
        repo = StringDateRepository(conn)

        # Insert with None date
        test_id = uuid4()
        await conn.execute("""
            INSERT INTO date_test (id, name, created_date, updated_date)
            VALUES (%s, %s, %s, %s)
        """, [test_id, "none_test", date(2024, 1, 1), None])
        await conn.commit()

        retrieved = await repo.get_by_id(test_id)
        assert retrieved.created_date == "2024-01-01"
        assert retrieved.updated_date is None

    @pytest.mark.asyncio
    async def test_date_field_in_create_and_update(self, date_test_table):
        """Test date handling in create and update operations."""
        conn = date_test_table
        repo = StringDateRepository(conn)

        # Create with string dates
        model = ModelWithStringDates(
            id=uuid4(),
            name="crud_test",
            created_date="2024-02-01",
            updated_date="2024-02-05"
        )

        # Should handle string to date conversion for storage
        created = await repo.create(model)
        assert created.created_date == "2024-02-01"

        # Update with new date
        updated = await repo.update(created.id, {
            "updated_date": "2024-02-10"
        })
        assert updated.updated_date == "2024-02-10"

    @pytest.mark.asyncio
    async def test_no_date_fields_parameter(self, date_test_table):
        """Test behavior without date_fields parameter."""
        conn = date_test_table

        # Repository without date_fields
        class NoDateFieldsRepo(BaseRepository[ModelWithStringDates, UUID]):
            def __init__(self, db_connection: AsyncConnection):
                super().__init__(
                    db_connection=db_connection,
                    table_name="date_test",
                    model_class=ModelWithStringDates,
                    primary_key="id"
                    # No date_fields parameter
                )

        repo = NoDateFieldsRepo(conn)

        # Insert data
        test_id = uuid4()
        await conn.execute("""
            INSERT INTO date_test (id, name, created_date)
            VALUES (%s, %s, %s)
        """, [test_id, "no_conversion", date(2024, 1, 1)])
        await conn.commit()

        # Without date_fields, this will fail with validation error
        # because PostgreSQL returns date object but model expects string
        with pytest.raises(Exception) as exc_info:
            await repo.get_by_id(test_id)

        assert "validation" in str(exc_info.value).lower() or "string" in str(exc_info.value).lower()
