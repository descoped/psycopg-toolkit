from typing import Optional, Any


# Database exceptions

class PsycoDBException(Exception):
    """Base exception for all psycopg-toolkit exceptions."""
    pass


class DatabaseConnectionError(PsycoDBException):
    """Raised when database connection fails."""

    def __init__(self, message: str, original_error: Optional[Exception] = None):
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
    
    def __init__(self, message: str, field_name: Optional[str] = None, original_error: Optional[Exception] = None):
        self.field_name = field_name
        self.original_error = original_error
        super().__init__(message)


class JSONSerializationError(JSONProcessingError):
    """Raised when JSON serialization fails."""
    
    def __init__(self, message: str, field_name: Optional[str] = None, value: Optional[Any] = None, original_error: Optional[Exception] = None):
        self.value = value
        super().__init__(message, field_name, original_error)


class JSONDeserializationError(JSONProcessingError):
    """Raised when JSON deserialization fails."""
    
    def __init__(self, message: str, field_name: Optional[str] = None, json_data: Optional[str] = None, original_error: Optional[Exception] = None):
        self.json_data = json_data
        super().__init__(message, field_name, original_error)
