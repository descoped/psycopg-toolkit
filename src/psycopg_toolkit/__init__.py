from .core.config import DatabaseSettings
from .core.database import Database
from .core.transaction import TransactionManager
from .exceptions import (
    DatabaseConnectionError,
    DatabaseNotAvailable,
    DatabasePoolError,
    InvalidDataError,
    JSONDeserializationError,
    JSONProcessingError,
    JSONSerializationError,
    OperationError,
    PsycoDBException,
    RecordNotFoundError,
    RepositoryError,
)
from .repositories.base import BaseRepository
from .utils.json_handler import CustomJSONEncoder, JSONHandler
from .utils.type_inspector import TypeInspector

__all__ = [
    "BaseRepository",
    "CustomJSONEncoder",
    # Core Database Components
    "Database",
    "DatabaseConnectionError",
    "DatabaseNotAvailable",
    "DatabasePoolError",
    "DatabaseSettings",
    "InvalidDataError",
    "JSONDeserializationError",
    # JSON/JSONB Support
    "JSONHandler",
    # JSON Exceptions
    "JSONProcessingError",
    "JSONSerializationError",
    "OperationError",
    # Base Exceptions
    "PsycoDBException",
    "RecordNotFoundError",
    "RepositoryError",
    "TransactionManager",
    "TypeInspector",
]
