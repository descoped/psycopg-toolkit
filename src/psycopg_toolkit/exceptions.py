from typing import Any

# Database exceptions


class PsycoDBException(Exception):
    """Base exception for all psycopg-toolkit exceptions."""

    pass


class DatabaseConnectionError(PsycoDBException):
    """Raised when database connection fails."""

    def __init__(self, message: str, original_error: Exception | None = None):
        self.original_error = original_error
        super().__init__(message)


class DatabasePoolError(PsycoDBException):
    """Raised when pool operations fail."""

    pass


class DatabaseNotAvailable(PsycoDBException):
    """Raised when database is not available."""

    pass


# Repository exceptions


class RepositoryError(PsycoDBException):
    """Base exception for repository-related errors."""

    pass


class RecordNotFoundError(RepositoryError):
    """Raised when a requested record is not found."""

    pass


class InvalidDataError(RepositoryError):
    """Raised when data validation fails."""

    pass


class OperationError(RepositoryError):
    """Raised when a repository operation fails."""

    pass


# JSON-specific exceptions


class JSONProcessingError(RepositoryError):
    """Base exception for JSON processing errors."""

    def __init__(self, message: str, field_name: str | None = None, original_error: Exception | None = None):
        self.field_name = field_name
        self.original_error = original_error
        super().__init__(message)


class JSONSerializationError(JSONProcessingError):
    """Raised when JSON serialization fails."""

    def __init__(
        self,
        message: str,
        field_name: str | None = None,
        value: Any | None = None,
        original_error: Exception | None = None,
    ):
        self.value = value
        super().__init__(message, field_name, original_error)


class JSONDeserializationError(JSONProcessingError):
    """Raised when JSON deserialization fails."""

    def __init__(
        self,
        message: str,
        field_name: str | None = None,
        json_data: str | None = None,
        original_error: Exception | None = None,
    ):
        self.json_data = json_data
        super().__init__(message, field_name, original_error)
