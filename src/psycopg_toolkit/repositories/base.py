import logging
from datetime import date, datetime
from typing import Any, Generic, TypeVar

from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.sql import SQL, Identifier
from psycopg.types.json import Json

from ..exceptions import (
    JSONDeserializationError,
    JSONProcessingError,
    JSONSerializationError,
    OperationError,
    RecordNotFoundError,
)
from ..utils import PsycopgHelper
from ..utils.json_handler import JSONHandler
from ..utils.type_inspector import TypeInspector

# Generic type variables for model and primary key
T = TypeVar("T")
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
                date values that need conversion between datetime.date and ISO strings.
                Defaults to None.
            array_fields (Optional[Set[str]], optional): Set of field names that should be
                treated as PostgreSQL arrays rather than JSONB. Only relevant when
                auto_detect_json=False. Defaults to None.

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
        self.model_class = model_class
        self.primary_key = primary_key

        # JSON field detection and configuration
        if json_fields is not None:
            self._json_fields = json_fields
            logger.debug(f"Using explicit JSON fields for {table_name}: {json_fields}")
        elif auto_detect_json:
            detected_fields = TypeInspector.detect_json_fields(model_class)
            # Exclude array fields from JSON fields
            self._json_fields = detected_fields - (array_fields or set())
            logger.debug(f"Auto-detected JSON fields for {table_name}: {detected_fields}")
            logger.debug(f"JSON fields after excluding arrays: {self._json_fields}")
        else:
            self._json_fields = set()
            logger.debug(f"JSON field processing disabled for {table_name}")

        # Cache for performance and configuration
        self._auto_detect_json = auto_detect_json
        self._strict_json_processing = strict_json_processing
        self._date_fields = date_fields or set()
        self._array_fields = array_fields or set()

        # Check if psycopg JSON adapters are enabled
        self._use_psycopg_adapters = self._check_psycopg_adapters()

    def _check_psycopg_adapters(self) -> bool:
        """Check if psycopg JSON adapters are enabled on the connection.

        Returns:
            bool: True if psycopg JSON adapters are enabled, False otherwise.
        """
        # Never use psycopg adapters - this causes issues with arrays
        # When auto_detect_json=False, users expect NO JSON processing
        return False

    @property
    def json_fields(self) -> set[str]:
        """Get the set of field names that should be treated as JSON.

        Returns:
            Set of field names that are configured for JSON serialization/deserialization.
        """
        return self._json_fields.copy()

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
                if isinstance(value, date) and not isinstance(value, datetime):
                    # Convert date to ISO string for storage
                    processed_data[field_name] = value.isoformat()
                    logger.debug(f"Converted date field '{field_name}' to ISO string for {self.table_name}")

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
                            logger.debug(f"Preserving array field '{field_name}' for PostgreSQL array handling")
                            continue
                        # Wrap other dict/list fields with Json()
                        processed_data[field_name] = Json(value)
                        logger.debug(f"Wrapped field '{field_name}' with Json() for PostgreSQL JSONB handling")
            return processed_data

        # Custom JSON processing mode - serialize to strings
        for field_name in json_fields:
            if field_name in processed_data and processed_data[field_name] is not None:
                value = processed_data[field_name]
                if isinstance(value, dict | list):
                    try:
                        # Serialize to JSON string for manual processing
                        serialized = JSONHandler.serialize(value)
                        processed_data[field_name] = serialized
                        logger.debug(f"Serialized JSON field '{field_name}' for {self.table_name}")
                    except Exception as e:
                        logger.error(f"Failed to serialize JSON field '{field_name}' in {self.table_name}: {e}")
                        raise JSONSerializationError(
                            f"JSON serialization failed for field '{field_name}': {e}",
                            field_name=field_name,
                            value=value,
                            original_error=e,
                        ) from e
                elif not isinstance(value, str):
                    # Value is not dict/list/str, try to serialize it anyway
                    try:
                        serialized = JSONHandler.serialize(value)
                        processed_data[field_name] = serialized
                        logger.debug(f"Serialized non-standard JSON field '{field_name}' for {self.table_name}")
                    except Exception as e:
                        logger.error(f"Failed to serialize JSON field '{field_name}' in {self.table_name}: {e}")
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
                if isinstance(value, date) and not isinstance(value, datetime):
                    # Convert date to ISO string for Pydantic
                    processed_data[field_name] = value.isoformat()
                    logger.debug(f"Converted date field '{field_name}' from date to ISO string for {self.table_name}")

        # If no JSON fields should be processed, return the processed data
        if not json_fields:
            logger.debug(f"No JSON fields configured for {self.table_name}, skipping JSON postprocessing")
            return processed_data

        # Convert date fields to appropriate format if needed
        for field_name in self._date_fields:
            if field_name in data and data[field_name] is not None:
                value = data[field_name]
                if isinstance(value, date) and not isinstance(value, datetime):
                    # Convert date to ISO string for storage
                    processed_data[field_name] = value.isoformat()
                    logger.debug(f"Converted date field '{field_name}' to ISO string for {self.table_name}")

        for field_name in self._json_fields:
            if field_name in processed_data and processed_data[field_name] is not None:
                try:
                    serialized_value = processed_data[field_name]
                    deserialized_value = JSONHandler.deserialize(serialized_value)
                    processed_data[field_name] = deserialized_value
                    logger.debug(f"Deserialized JSON field '{field_name}' for {self.table_name}")
                except Exception as e:
                    if self._strict_json_processing:
                        logger.error(f"Failed to deserialize JSON field '{field_name}' in {self.table_name}: {e}")
                        raise JSONDeserializationError(
                            f"JSON deserialization failed for field '{field_name}': {e}",
                            field_name=field_name,
                            json_data=str(serialized_value) if serialized_value is not None else None,
                            original_error=e,
                        ) from e
                    else:
                        logger.warning(f"Failed to deserialize JSON field '{field_name}' in {self.table_name}: {e}")
                        # Keep the original value to prevent data loss
                        logger.warning(f"Keeping original value for field '{field_name}' in {self.table_name}")

        logger.debug(f"Postprocessed {len(self._json_fields)} JSON fields for {self.table_name}")
        return processed_data

    async def create(self, item: T) -> T:
        """
        Create a new record in the database.

        Args:
            item (T): The model instance to create in the database.

        Returns:
            T: The created model instance with any database-generated fields.

        Raises:
            HTTPException: If the creation fails or database error occurs.
            OperationError: If the database operation doesn't return a result.
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
        try:
            data = item.model_dump()
            # Preprocess data to serialize JSON fields
            processed_data = self._preprocess_data(data)
            insert_query = PsycopgHelper.build_insert_query(self.table_name, processed_data)

            async with self.db_connection.cursor(row_factory=dict_row) as cur:
                await cur.execute(insert_query + SQL(" RETURNING *"), list(processed_data.values()))
                result = await cur.fetchone()
                if not result:
                    raise OperationError(f"Failed to create {self.table_name} record")

                # Postprocess the result to deserialize JSON fields
                postprocessed_result = self._postprocess_data(dict(result))
                return self.model_class(**postprocessed_result)
        except Exception as e:
            logger.error(f"Error in create: {e}")
            if isinstance(e, OperationError | JSONProcessingError):
                raise
            raise OperationError(f"Failed to create record: {e!s}") from e

    async def create_bulk(self, items: list[T], batch_size: int = 100) -> list[T]:
        """
        Create multiple records in batches.

        Args:
            items (List[T]): List of model instances to create.
            batch_size (int, optional): Number of records per batch. Defaults to 100.

        Returns:
            List[T]: List of created model instances with database-generated fields.

        Raises:
            HTTPException: If the bulk creation fails or database error occurs.
            OperationError: If the database operation fails.
            JSONSerializationError: If JSON serialization fails for any record.

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
        try:
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

                        # Postprocess each result to deserialize JSON fields
                        postprocessed_results = [self._postprocess_data(dict(row)) for row in results]
                        all_results.extend([self.model_class(**row) for row in postprocessed_results])
            return all_results
        except Exception as e:
            logger.error(f"Error in create_bulk: {e}")
            raise OperationError(f"Failed to create records in bulk: {e!s}") from e

    async def get_by_id(self, record_id: K) -> T | None:
        """
        Retrieve a record by its ID.

        Args:
            record_id (K): The unique identifier of the record.

        Returns:
            Optional[T]: The found model instance or None if not found.

        Raises:
            HTTPException: If the database query fails.
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
        try:
            select_query = PsycopgHelper.build_select_query(self.table_name, where_clause={self.primary_key: record_id})
            async with self.db_connection.cursor(row_factory=dict_row) as cur:
                await cur.execute(select_query, [record_id])
                result = await cur.fetchone()
                if not result:
                    raise RecordNotFoundError(f"Record with id {record_id} not found")

                # Postprocess the result to deserialize JSON fields
                postprocessed_result = self._postprocess_data(dict(result))
                return self.model_class(**postprocessed_result)
        except Exception as e:
            logger.error(f"Error in get_by_id: {e}")
            if isinstance(e, RecordNotFoundError | JSONProcessingError):
                raise
            raise OperationError(f"Failed to get record: {e!s}") from e

    async def get_all(self) -> list[T]:
        """
        Retrieve all records from the table.

        Returns:
            List[T]: List of all model instances in the table.

        Raises:
            HTTPException: If the database query fails.
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
        try:
            async with self.db_connection.cursor(row_factory=dict_row) as cur:
                query = SQL("SELECT * FROM {}").format(Identifier(self.table_name))
                await cur.execute(query)
                rows = await cur.fetchall()

                # Postprocess each row to deserialize JSON fields
                postprocessed_rows = [self._postprocess_data(dict(row)) for row in rows]
                return [self.model_class(**row) for row in postprocessed_rows]
        except Exception as e:
            logger.error(f"Error in get_all: {e}")
            if isinstance(e, JSONProcessingError):
                raise
            raise OperationError(f"Failed to get all records: {e!s}") from e

    async def update(self, record_id: K, data: dict[str, Any]) -> T:
        """
        Update a record by its ID.

        Args:
            record_id (K): The unique identifier of the record to update.
            data (Dict[str, Any]): Dictionary of fields and values to update.

        Returns:
            T: The updated model instance.

        Raises:
            HTTPException: If the update fails or database error occurs.
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
        try:
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

                # Postprocess the result to deserialize JSON fields
                postprocessed_result = self._postprocess_data(dict(result))
                return self.model_class(**postprocessed_result)
        except Exception as e:
            logger.error(f"Error in update: {e}")
            if isinstance(e, RecordNotFoundError | JSONProcessingError):
                raise
            raise OperationError(f"Failed to update record: {e!s}") from e

    async def delete(self, record_id: K) -> None:
        """
        Delete a record by its ID.

        Args:
            record_id (K): The unique identifier of the record to delete.

        Raises:
            HTTPException: If the deletion fails or database error occurs.

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
        try:
            delete_query = PsycopgHelper.build_delete_query(self.table_name, where_clause={self.primary_key: record_id})
            async with self.db_connection.cursor() as cur:
                await cur.execute(delete_query, [record_id])
                if cur.rowcount == 0:
                    raise RecordNotFoundError(f"Record with id {record_id} not found")
        except Exception as e:
            logger.error(f"Error in delete: {e}")
            if isinstance(e, RecordNotFoundError):
                raise
            raise OperationError(f"Failed to delete record: {e!s}") from e

    async def exists(self, record_id: K) -> bool:
        """
        Check if a record exists by its ID.

        Args:
            record_id (K): The unique identifier to check.

        Returns:
            bool: True if the record exists, False otherwise.

        Raises:
            HTTPException: If the database query fails.

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
        try:
            async with self.db_connection.cursor() as cur:
                await cur.execute(f"SELECT 1 FROM {self.table_name} WHERE {self.primary_key} = %s", [record_id])
                return bool(await cur.fetchone())
        except Exception as e:
            logger.error(f"Error in exists: {e}")
            raise OperationError(f"Failed to check record existence: {e!s}") from e
