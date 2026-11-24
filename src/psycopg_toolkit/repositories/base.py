import logging
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from datetime import date, datetime
from typing import Any, Generic, TypeVar

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier
from psycopg.types.json import Json
from pydantic import BaseModel

from ..exceptions import (
    JSONDeserializationError,
    JSONProcessingError,
    JSONSerializationError,
    OperationError,
    RecordNotFoundError,
)
from ..utils import PsycopgHelper
from ..utils.json_handler import DecimalMode, JSONHandler, check_decimal_mode
from ..utils.type_inspector import TypeInspector

# Generic type variables for model and primary key
T = TypeVar("T", bound=BaseModel)
K = TypeVar("K")

logger = logging.getLogger(__name__)


class BaseRepository(Generic[T, K]):
    """
    Generic base repository implementing common database operations.

    This class provides a foundation for implementing the repository pattern with
    PostgreSQL databases. It includes basic CRUD operations and uses generics to
    ensure type safety with different model and primary key types.

    Type Parameters:
        T: The model type this repository handles. Must be a Pydantic model.
        K: The primary key type (e.g., UUID, int, str).

    Attributes:
        db_connection (AsyncConnection): Active database connection.
        table_name (str): Name of the database table.
        model_class (type[T]): The Pydantic model class for type T.
        primary_key (str): Name of the primary key column in the table.
        json_fields (Set[str]): Set of field names that should be treated as JSON.
        auto_detect_json (bool): Whether to automatically detect JSON fields from type hints.

    Example:
        ```python
        class DocumentRepository(BaseRepository[Document, UUID]):
            def __init__(self, db_connection: AsyncConnection):
                super().__init__(
                    db_connection=db_connection, table_name="documents", model_class=Document, primary_key="document_id"
                )


        # Or with an integer primary key
        class UserRepository(BaseRepository[User, int]):
            def __init__(self, db_connection: AsyncConnection):
                super().__init__(
                    db_connection=db_connection, table_name="users", model_class=User, primary_key="user_id"
                )
        ```
    """

    def __init__(
        self,
        db_connection: AsyncConnection,
        table_name: str,
        model_class: type[T],
        primary_key: str = "id",
        json_fields: set[str] | None = None,
        auto_detect_json: bool = True,
        strict_json_processing: bool = False,
        date_fields: set[str] | None = None,
        array_fields: set[str] | None = None,
        vector_fields: set[str] | None = None,
        auto_detect_vector: bool = True,
        decimal_as: DecimalMode = "float",
    ):
        """
        Initialize the base repository.

        Args:
            db_connection (AsyncConnection): Active database connection to use for operations.
            table_name (str): Name of the database table being accessed.
            model_class (type[T]): The Pydantic model class used for type T.
            primary_key (str, optional): Name of the primary key column. Defaults to "id".
            json_fields (Optional[Set[str]], optional): Explicit set of field names to treat as JSON.
                If provided, overrides auto-detection. Defaults to None.
            auto_detect_json (bool, optional): Whether to automatically detect JSON fields from
                Pydantic type hints. Ignored if json_fields is provided. Defaults to True.
            strict_json_processing (bool, optional): Whether to raise exceptions for JSON
                deserialization errors instead of logging warnings. Defaults to False.
            date_fields (Optional[Set[str]], optional): Set of field names that contain
                date/datetime values needing conversion to ISO strings. Include ALL date,
                timestamp, and timestamptz fields from your model. Defaults to None.
            array_fields (Optional[Set[str]], optional): Set of field names that should be
                treated as PostgreSQL arrays rather than JSONB. Only relevant when
                auto_detect_json=False. Defaults to None.
            vector_fields (Optional[Set[str]], optional): Explicit set of field names to treat
                as pgvector columns. Vector fields are returned as strings from PostgreSQL and
                automatically parsed to list[float] using JSON parsing. If provided, overrides
                auto-detection. Defaults to None.
            auto_detect_vector (bool, optional): Whether to automatically detect vector fields
                (list[float]) from Pydantic type hints. Ignored if vector_fields is provided.
                Defaults to True.
            decimal_as (DecimalMode, optional): How Decimal values inside JSON fields are
                written. "float" (default) may lose digits; "str" keeps every digit by writing
                the value as a JSON string, which reads back as ``str`` (convert with
                ``Decimal(value)``). Applies to the toolkit's own JSON serialization, not to
                values wrapped with ``Json()`` when ``auto_detect_json=False``.

        Note:
            The model_class should be a Pydantic model that matches the database schema.
            The primary_key should match the actual primary key column name in the database.
            The primary key type K is inferred from the model's type hints.

            JSON field detection:
            - If json_fields is provided, those fields will be treated as JSON
            - If json_fields is None and auto_detect_json is True, fields will be auto-detected
            - If both are disabled, no JSON processing will occur
        """
        self.db_connection = db_connection
        self.table_name = table_name
        self._decimal_as: DecimalMode = check_decimal_mode(decimal_as)
        self.model_class = model_class
        self.primary_key = primary_key

        # Vector field detection and configuration
        if vector_fields is not None:
            self._vector_fields: set[str] = vector_fields
            logger.debug("Using explicit vector fields for %s: %s", table_name, vector_fields)
        elif auto_detect_vector:
            self._vector_fields = TypeInspector.detect_vector_fields(model_class)
            logger.debug("Auto-detected vector fields for %s: %s", table_name, self._vector_fields)
        else:
            self._vector_fields = set()
            logger.debug("Vector field detection disabled for %s", table_name)

        # JSON field detection and configuration
        if json_fields is not None:
            self._json_fields: set[str] = json_fields
            logger.debug("Using explicit JSON fields for %s: %s", table_name, json_fields)
        elif auto_detect_json:
            detected_fields = TypeInspector.detect_json_fields(model_class)
            # Exclude array fields and vector fields from JSON fields
            self._json_fields = detected_fields - (array_fields or set()) - self._vector_fields
            logger.debug("Auto-detected JSON fields for %s: %s", table_name, detected_fields)
            logger.debug("JSON fields after excluding arrays and vectors: %s", self._json_fields)
        else:
            self._json_fields = set()
            logger.debug("JSON field processing disabled for %s", table_name)

        # JSON fields whose model type admits a plain str: there a str is a JSON string value,
        # so it is serialized on write and not decoded again on read. For dict/list-only fields
        # a str stays what it has always been: an already-serialized JSON document.
        model_fields = model_class.model_fields
        self._str_json_fields: set[str] = {
            name
            for name in self._json_fields
            if name in model_fields and TypeInspector.accepts_str(model_fields[name].annotation)
        }

        # Cache for performance and configuration
        self._auto_detect_json = auto_detect_json
        self._auto_detect_vector = auto_detect_vector
        self._strict_json_processing = strict_json_processing
        self._date_fields = date_fields or set()
        self._array_fields = array_fields or set()

    @property
    def json_fields(self) -> set[str]:
        """Get the set of field names that should be treated as JSON.

        Returns:
            Set of field names that are configured for JSON serialization/deserialization.
        """
        return self._json_fields.copy()

    @property
    def vector_fields(self) -> set[str]:
        """Get the set of field names that should be treated as pgvector.

        Returns:
            Set of field names that are configured as vector fields.
        """
        return self._vector_fields.copy()

    def _preprocess_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Preprocess data by handling JSON fields according to processing mode.

        In psycopg adapter mode, JSON fields are wrapped with Json() adapter.
        In custom processing mode, JSON fields are serialized to strings.

        Args:
            data (Dict[str, Any]): The data dictionary to preprocess.

        Returns:
            Dict[str, Any]: The preprocessed data with JSON fields handled.

        Example:
            ```python
            # With psycopg adapters:
            data = {"metadata": {"key": "value"}}
            processed = repo._preprocess_data(data)
            # processed["metadata"] is now Json({"key": "value"})

            # With custom processing:
            data = {"metadata": {"key": "value"}}
            processed = repo._preprocess_data(data)
            # processed["metadata"] is now '{"key": "value"}'
            ```
        """
        processed_data = data.copy()

        # Convert date fields to appropriate format if needed
        for field_name in self._date_fields:
            if field_name in data and data[field_name] is not None:
                value = data[field_name]
                if isinstance(value, date | datetime):
                    # Convert date/datetime to ISO string for storage
                    processed_data[field_name] = value.isoformat()
                    logger.debug(
                        f"Converted date field '{field_name}' from {type(value).__name__} to ISO string for {self.table_name}"
                    )

        # For custom JSON processing, determine which fields need processing
        json_fields = self._json_fields

        # If no JSON fields should be processed
        if not json_fields:
            # When auto_detect_json is False, wrap dict/list values with Json()
            # unless they are explicitly marked as array fields
            if not self._auto_detect_json:
                for field_name, value in data.items():
                    if value is not None and isinstance(value, dict | list):
                        # Skip array fields - they should remain as PostgreSQL arrays
                        if field_name in self._array_fields:
                            logger.debug("Preserving array field '%s' for PostgreSQL array handling", field_name)
                            continue
                        # Wrap other dict/list fields with Json()
                        processed_data[field_name] = Json(value)
                        logger.debug("Wrapped field '%s' with Json() for PostgreSQL JSONB handling", field_name)
            return processed_data

        # Custom JSON processing mode - serialize to strings
        for field_name in json_fields:
            if field_name in processed_data and processed_data[field_name] is not None:
                value = processed_data[field_name]
                if isinstance(value, dict | list):
                    try:
                        # Serialize to JSON string for manual processing
                        serialized = JSONHandler.serialize(value, decimal_as=self._decimal_as)
                        processed_data[field_name] = serialized
                        logger.debug("Serialized JSON field '%s' for %s", field_name, self.table_name)
                    except Exception as e:
                        raise JSONSerializationError(
                            f"JSON serialization failed for field '{field_name}': {e}",
                            field_name=field_name,
                            value=value,
                            original_error=e,
                        ) from e
                elif not isinstance(value, str) or field_name in self._str_json_fields:
                    # Not dict/list: serialize it as a JSON value. A str is serialized only where
                    # the field accepts str; elsewhere it is an already-serialized document.
                    try:
                        serialized = JSONHandler.serialize(value, decimal_as=self._decimal_as)
                        processed_data[field_name] = serialized
                        logger.debug("Serialized non-standard JSON field '%s' for %s", field_name, self.table_name)
                    except Exception as e:
                        raise JSONSerializationError(
                            f"JSON serialization failed for field '{field_name}': {e}",
                            field_name=field_name,
                            value=value,
                            original_error=e,
                        ) from e

        return processed_data

    def _postprocess_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """Postprocess data by deserializing JSON fields after database operations.

        This method takes a dictionary of data retrieved from the database and
        deserializes any fields that are configured as JSON fields using the JSONHandler.
        Non-JSON fields are left unchanged.

        Args:
            data (Dict[str, Any]): The data dictionary to postprocess.

        Returns:
            Dict[str, Any]: The postprocessed data with JSON fields deserialized.

        Note:
            This method handles None values gracefully. When strict_json_processing is False
            (default), it logs warnings for deserialization failures rather than raising
            exceptions to prevent data retrieval failures. When strict_json_processing is True,
            it raises JSONDeserializationError for any deserialization failures.

        Example:
            ```python
            data = {
                "name": "test",
                "metadata": '{"key": "value"}',  # Will be deserialized
                "value": 42,  # Will remain unchanged
            }
            processed = repo._postprocess_data(data)
            # processed["metadata"] is now {"key": "value"}
            ```
        """
        # Check which fields should be processed
        json_fields = self._json_fields

        processed_data = data.copy()

        # Convert date fields from database format to string if needed
        for field_name in self._date_fields:
            if field_name in processed_data and processed_data[field_name] is not None:
                value = processed_data[field_name]
                if isinstance(value, date | datetime):
                    # Convert date/datetime to ISO string for Pydantic
                    processed_data[field_name] = value.isoformat()
                    logger.debug(
                        f"Converted date field '{field_name}' from {type(value).__name__} to ISO string for {self.table_name}"
                    )

        # Parse vector fields from PostgreSQL string format to Python list[float]
        # PostgreSQL returns vectors as strings like '[0.1,0.2,0.3]'
        for field_name in self._vector_fields:
            if field_name in processed_data and processed_data[field_name] is not None:
                value = processed_data[field_name]
                if isinstance(value, str):
                    try:
                        # Parse string to list[float] using json.loads()
                        parsed_vector = JSONHandler.deserialize(value)
                        if isinstance(parsed_vector, list):
                            processed_data[field_name] = parsed_vector
                            logger.debug(
                                f"Parsed vector field '{field_name}' from string to list[float] for {self.table_name}"
                            )
                        else:
                            logger.warning(
                                f"Vector field '{field_name}' parsed to {type(parsed_vector).__name__} instead of list for {self.table_name}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Failed to parse vector field '{field_name}' in {self.table_name}: {e}. Keeping as string."
                        )

        # If no JSON fields should be processed, return the processed data
        if not json_fields:
            logger.debug("No JSON fields configured for %s, skipping JSON postprocessing", self.table_name)
            return processed_data

        for field_name in self._json_fields:
            if field_name in processed_data and processed_data[field_name] is not None:
                serialized_value = processed_data[field_name]
                if not isinstance(serialized_value, str | bytes):
                    # psycopg always decodes json/jsonb columns to Python objects,
                    # so a dict/list here is already deserialized
                    continue
                if isinstance(serialized_value, str) and field_name in self._str_json_fields:
                    # A JSON string value psycopg has already decoded; decoding it again would turn
                    # "123" into 123 or fail on "hello".
                    continue
                try:
                    deserialized_value = JSONHandler.deserialize(serialized_value)
                    processed_data[field_name] = deserialized_value
                    logger.debug("Deserialized JSON field '%s' for %s", field_name, self.table_name)
                except Exception as e:
                    if self._strict_json_processing:
                        raise JSONDeserializationError(
                            f"JSON deserialization failed for field '{field_name}': {e}",
                            field_name=field_name,
                            json_data=str(serialized_value),
                            original_error=e,
                        ) from e
                    else:
                        logger.warning(
                            "Failed to deserialize JSON field '%s' in %s: %s", field_name, self.table_name, e
                        )
                        # Keep the original value to prevent data loss
                        logger.warning("Keeping original value for field '%s' in %s", field_name, self.table_name)

        logger.debug("Postprocessed %s JSON fields for %s", len(self._json_fields), self.table_name)
        return processed_data

    def row_to_model(self, row: Mapping[str, Any]) -> T:
        """Convert a fetched row into the model, applying the repository's field handling.

        Use this in custom queries instead of building the model yourself: it decodes JSON fields,
        parses vector fields and converts date fields exactly as the built-in methods do. Fetch
        with ``row_factory=dict_row`` so rows are mappings.

        Args:
            row: A row as a mapping of column name to value, e.g. from ``dict_row``. Not modified.

        Returns:
            T: The validated model instance.

        Raises:
            JSONDeserializationError: If a JSON field cannot be decoded and strict_json_processing is True.
            pydantic.ValidationError: If the row does not validate against the model.

        Example:
            ```python
            async with self.db_connection.cursor(row_factory=dict_row) as cur:
                await cur.execute(query, params)
                return [self.row_to_model(row) for row in await cur.fetchall()]
            ```
        """
        return self.model_class(**self._postprocess_data(dict(row)))

    @asynccontextmanager
    async def _errors(
        self, operation: str, message: str, passthrough: tuple[type[Exception], ...] = ()
    ) -> AsyncGenerator[None, None]:
        """Translate errors raised by a CRUD operation into the repository exception contract.

        Exceptions of a ``passthrough`` type are re-raised unchanged; anything else becomes an
        ``OperationError("<message>: <error>")`` chained to the original. Each failure is logged
        once here: missing records at DEBUG (an expected outcome), everything else at ERROR.
        """
        try:
            yield
        except Exception as e:
            if isinstance(e, RecordNotFoundError):
                logger.debug("%s: %s", operation, e)
            else:
                logger.error("Error in %s: %s", operation, e)
            if isinstance(e, passthrough):
                raise
            raise OperationError(f"{message}: {e!s}") from e

    async def create(self, item: T) -> T:
        """
        Create a new record in the database.

        Args:
            item (T): The model instance to create in the database.

        Returns:
            T: The created model instance with any database-generated fields.

        Raises:
            OperationError: If the database operation fails or returns no row.
            JSONSerializationError: If JSON serialization fails for any field.

        Example:
            ```python
            new_item = ItemModel(name="test", description="test item")
            created_item = await repo.create(new_item)
            ```

        Note:
            If the model has JSON fields, they will be automatically serialized before
            insertion and deserialized when returning the created record.
        """
        async with self._errors("create", "Failed to create record", (OperationError, JSONProcessingError)):
            data = item.model_dump()
            # Preprocess data to serialize JSON fields
            processed_data = self._preprocess_data(data)
            insert_query = PsycopgHelper.build_insert_query(self.table_name, processed_data)

            async with self.db_connection.cursor(row_factory=dict_row) as cur:
                await cur.execute(insert_query + SQL(" RETURNING *"), list(processed_data.values()))
                result = await cur.fetchone()
                if not result:
                    raise OperationError(f"Failed to create {self.table_name} record")

                return self.row_to_model(result)

    async def create_bulk(self, items: list[T], batch_size: int = 100) -> list[T]:
        """
        Create multiple records in batches.

        Args:
            items (List[T]): List of model instances to create.
            batch_size (int, optional): Number of records per batch. Defaults to 100.

        Returns:
            List[T]: List of created model instances with database-generated fields.

        Raises:
            OperationError: If the database operation fails, or if JSON serialization fails
                for any record. Unlike ``create``, a serialization failure is not raised
                directly: it is wrapped, with the JSONSerializationError as ``__cause__``.

        Example:
            ```python
            items = [ItemModel(name=f"item_{i}") for i in range(500)]
            created_items = await repo.create_bulk(items, batch_size=50)
            ```

        Note:
            Uses database transactions to ensure all-or-nothing batch operations.
            Large lists are automatically processed in batches for better performance.
            If the model has JSON fields, they will be automatically serialized before
            insertion and deserialized when returning the created records.
        """
        all_results = []
        async with self._errors("create_bulk", "Failed to create records in bulk"):
            async with self.db_connection.transaction():
                for i in range(0, len(items), batch_size):
                    batch = items[i : i + batch_size]
                    data_list = [item.model_dump() for item in batch]
                    if not data_list:
                        continue

                    # Preprocess each item's data to serialize JSON fields
                    processed_data_list = [self._preprocess_data(data) for data in data_list]

                    batch_insert_query = PsycopgHelper.build_insert_query(
                        self.table_name, processed_data_list[0], batch_size=len(processed_data_list)
                    )
                    batch_values = [val for data in processed_data_list for val in data.values()]

                    async with self.db_connection.cursor(row_factory=dict_row) as cur:
                        full_query = batch_insert_query + SQL(" RETURNING *")
                        await cur.execute(full_query, batch_values)
                        results = await cur.fetchall()

                        all_results.extend(self.row_to_model(row) for row in results)
            return all_results

    async def get_by_id(self, record_id: K) -> T:
        """
        Retrieve a record by its ID.

        Args:
            record_id (K): The unique identifier of the record.

        Returns:
            T: The found model instance.

        Raises:
            RecordNotFoundError: If no record has this ID.
            OperationError: If the database query fails.
            JSONDeserializationError: If JSON deserialization fails and strict_json_processing is True.

        Example:
            ```python
            # With UUID primary key
            item = await repo.get_by_id(uuid.UUID("..."))

            # With integer primary key
            user = await user_repo.get_by_id(123)
            ```

        Note:
            If the model has JSON fields, they will be automatically deserialized
            from the database representation before creating the model instance.
        """
        async with self._errors("get_by_id", "Failed to get record", (RecordNotFoundError, JSONProcessingError)):
            select_query = PsycopgHelper.build_select_query(self.table_name, where_clause={self.primary_key: record_id})
            async with self.db_connection.cursor(row_factory=dict_row) as cur:
                await cur.execute(select_query, [record_id])
                result = await cur.fetchone()
                if not result:
                    raise RecordNotFoundError(f"Record with id {record_id} not found")

                return self.row_to_model(result)

    async def get_all(self) -> list[T]:
        """
        Retrieve all records from the table.

        Returns:
            List[T]: List of all model instances in the table.

        Raises:
            OperationError: If the database query fails.
            JSONDeserializationError: If JSON deserialization fails and strict_json_processing is True.

        Example:
            ```python
            all_items = await repo.get_all()
            for item in all_items:
                print(f"Item: {item.name}")
            ```

        Warning:
            Use with caution on large tables as it loads all records into memory.

        Note:
            If the model has JSON fields, they will be automatically deserialized
            from the database representation before creating the model instances.
        """
        async with (
            self._errors("get_all", "Failed to get all records", (JSONProcessingError,)),
            self.db_connection.cursor(row_factory=dict_row) as cur,
        ):
            query = SQL("SELECT * FROM {}").format(Identifier(self.table_name))
            await cur.execute(query)
            rows = await cur.fetchall()

            return [self.row_to_model(row) for row in rows]

    async def update(self, record_id: K, data: dict[str, Any]) -> T:
        """
        Update a record by its ID.

        Args:
            record_id (K): The unique identifier of the record to update.
            data (Dict[str, Any]): Dictionary of fields and values to update.

        Returns:
            T: The updated model instance.

        Raises:
            OperationError: If the database operation fails.
            RecordNotFoundError: If the record is not found.
            JSONSerializationError: If JSON serialization fails for any field.
            JSONDeserializationError: If JSON deserialization fails and strict_json_processing is True.

        Example:
            ```python
            # With UUID primary key
            updated_doc = await doc_repo.update(uuid.UUID("..."), {"name": "new name"})

            # With integer primary key
            updated_user = await user_repo.update(123, {"email": "new@email.com"})
            ```

        Note:
            If the data contains JSON fields, they will be automatically serialized before
            the update and deserialized when returning the updated record.
        """
        async with self._errors("update", "Failed to update record", (RecordNotFoundError, JSONProcessingError)):
            # Preprocess data to serialize JSON fields
            processed_data = self._preprocess_data(data)
            update_query = PsycopgHelper.build_update_query(
                self.table_name, processed_data, where_clause={self.primary_key: record_id}
            )
            values = [*list(processed_data.values()), record_id]
            async with self.db_connection.cursor(row_factory=dict_row) as cur:
                await cur.execute(update_query + SQL(" RETURNING *"), values)
                result = await cur.fetchone()
                if not result:
                    raise RecordNotFoundError(f"Record with id {record_id} not found")

                return self.row_to_model(result)

    async def delete(self, record_id: K) -> None:
        """
        Delete a record by its ID.

        Args:
            record_id (K): The unique identifier of the record to delete.

        Raises:
            RecordNotFoundError: If no record has the given ID.
            OperationError: If the database operation fails.

        Example:
            ```python
            # With UUID primary key
            await doc_repo.delete(uuid.UUID("..."))

            # With integer primary key
            await user_repo.delete(123)
            ```

        Note:
            This is a hard delete. Consider implementing soft delete if needed.
        """
        async with self._errors("delete", "Failed to delete record", (RecordNotFoundError,)):
            delete_query = PsycopgHelper.build_delete_query(self.table_name, where_clause={self.primary_key: record_id})
            async with self.db_connection.cursor() as cur:
                await cur.execute(delete_query, [record_id])
                if cur.rowcount == 0:
                    raise RecordNotFoundError(f"Record with id {record_id} not found")

    async def exists(self, record_id: K) -> bool:
        """
        Check if a record exists by its ID.

        Args:
            record_id (K): The unique identifier to check.

        Returns:
            bool: True if the record exists, False otherwise.

        Raises:
            OperationError: If the database query fails.

        Example:
            ```python
            # With UUID primary key
            if await doc_repo.exists(uuid.UUID("...")):
                print("Document exists")

            # With integer primary key
            if await user_repo.exists(123):
                print("User exists")
            ```
        """
        async with self._errors("exists", "Failed to check record existence"):
            query = SQL("SELECT 1 FROM {} WHERE {} = %s").format(
                Identifier(self.table_name), Identifier(self.primary_key)
            )
            async with self.db_connection.cursor() as cur:
                await cur.execute(query, [record_id])
                return bool(await cur.fetchone())
