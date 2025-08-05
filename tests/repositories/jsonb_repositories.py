"""JSONB repository implementations for tests."""

from conftest import ComplexJSON, SimpleJSON
from psycopg import sql

from psycopg_toolkit import BaseRepository


class SimpleJSONRepository(BaseRepository[SimpleJSON, int]):
    """Repository for simple JSONB model with proper SERIAL ID handling."""

    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection, table_name="jsonb_simple", model_class=SimpleJSON, primary_key="id"
        )

    async def create(self, item: SimpleJSON) -> SimpleJSON:
        """Create with proper SERIAL ID handling."""
        # Get data excluding None id
        data = item.model_dump(exclude_none=True)

        # Build custom insert query excluding id
        import json

        from psycopg.rows import dict_row

        columns = [k for k in data if k != "id" or data[k] is not None]
        values = []
        for k in columns:
            v = data[k]
            if isinstance(v, dict | list):
                try:
                    values.append(json.dumps(v))
                except (ValueError, TypeError) as e:
                    from psycopg_toolkit import JSONSerializationError

                    raise JSONSerializationError(
                        f"Failed to serialize field '{k}': {e!s}", field_name=k, original_error=e
                    ) from e
            else:
                values.append(v)

        query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING *").format(
            sql.Identifier(self.table_name),
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            sql.SQL(", ").join(sql.Placeholder() * len(columns)),
        )

        async with self.db_connection.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, values)
            result = await cur.fetchone()
            return self.model_class(**result)

    async def update(self, record_id: int, data: dict) -> SimpleJSON:
        """Update with proper JSONB handling."""
        import json

        from psycopg.rows import dict_row

        # Build custom update query
        columns = []
        values = []
        for k, v in data.items():
            columns.append(k)
            if isinstance(v, dict | list):
                try:
                    values.append(json.dumps(v))
                except (ValueError, TypeError) as e:
                    from psycopg_toolkit import JSONSerializationError

                    raise JSONSerializationError(
                        f"Failed to serialize field '{k}': {e!s}", field_name=k, original_error=e
                    ) from e
            else:
                values.append(v)

        if not columns:
            # No data to update, just return the existing record
            return await self.get_by_id(record_id)

        values.append(record_id)  # Add id for WHERE clause

        query = sql.SQL("UPDATE {} SET {} WHERE {} = %s RETURNING *").format(
            sql.Identifier(self.table_name),
            sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(col)) for col in columns),
            sql.Identifier(self.primary_key),
        )

        async with self.db_connection.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, values)
            result = await cur.fetchone()
            if not result:
                from psycopg_toolkit import RecordNotFoundError

                raise RecordNotFoundError(f"Record with id {record_id} not found")
            return self.model_class(**result)


class ComplexJSONRepository(BaseRepository[ComplexJSON, int]):
    """Repository for complex JSONB model with proper SERIAL ID handling."""

    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection, table_name="jsonb_complex", model_class=ComplexJSON, primary_key="id"
        )

    async def create(self, item: ComplexJSON) -> ComplexJSON:
        """Create with proper SERIAL ID handling."""
        # Get data excluding None id
        data = item.model_dump(exclude_none=True)

        # Build custom insert query excluding id
        import json

        from psycopg.rows import dict_row

        columns = [k for k in data if k != "id" or data[k] is not None]
        values = []
        for k in columns:
            v = data[k]
            if isinstance(v, dict | list):
                try:
                    values.append(json.dumps(v))
                except (ValueError, TypeError) as e:
                    from psycopg_toolkit import JSONSerializationError

                    raise JSONSerializationError(
                        f"Failed to serialize field '{k}': {e!s}", field_name=k, original_error=e
                    ) from e
            else:
                values.append(v)

        query = sql.SQL("INSERT INTO {} ({}) VALUES ({}) RETURNING *").format(
            sql.Identifier(self.table_name),
            sql.SQL(", ").join(map(sql.Identifier, columns)),
            sql.SQL(", ").join(sql.Placeholder() * len(columns)),
        )

        async with self.db_connection.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, values)
            result = await cur.fetchone()
            return self.model_class(**result)

    async def update(self, record_id: int, data: dict) -> ComplexJSON:
        """Update with proper JSONB handling."""
        import json

        from psycopg.rows import dict_row

        # Build custom update query
        columns = []
        values = []
        for k, v in data.items():
            columns.append(k)
            if isinstance(v, dict | list):
                try:
                    values.append(json.dumps(v))
                except (ValueError, TypeError) as e:
                    from psycopg_toolkit import JSONSerializationError

                    raise JSONSerializationError(
                        f"Failed to serialize field '{k}': {e!s}", field_name=k, original_error=e
                    ) from e
            else:
                values.append(v)

        if not columns:
            # No data to update, just return the existing record
            return await self.get_by_id(record_id)

        values.append(record_id)  # Add id for WHERE clause

        query = sql.SQL("UPDATE {} SET {} WHERE {} = %s RETURNING *").format(
            sql.Identifier(self.table_name),
            sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(col)) for col in columns),
            sql.Identifier(self.primary_key),
        )

        async with self.db_connection.cursor(row_factory=dict_row) as cur:
            await cur.execute(query, values)
            result = await cur.fetchone()
            if not result:
                from psycopg_toolkit import RecordNotFoundError

                raise RecordNotFoundError(f"Record with id {record_id} not found")
            return self.model_class(**result)

    async def create_bulk(self, items: list[ComplexJSON], batch_size: int = 100) -> list[ComplexJSON]:
        """Bulk create with proper SERIAL ID handling."""
        # We need to create items one by one because BaseRepository's bulk create
        # doesn't handle SERIAL IDs properly
        created_items = []
        for item in items:
            created = await self.create(item)
            created_items.append(created)
        return created_items
