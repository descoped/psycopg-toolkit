# src/psyco_db/exceptions.py

from typing import Optional


class PsycoDBException(Exception):
    """Base exception for all psyco-db exceptions."""
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
