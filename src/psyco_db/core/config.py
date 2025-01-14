from dataclasses import dataclass
from typing import Optional


@dataclass
class DatabaseSettings:
    """Database connection settings."""
    host: str
    port: int
    dbname: str
    user: str
    password: str
    min_pool_size: int = 5
    max_pool_size: int = 20
    pool_timeout: int = 30
    connection_timeout: float = 5.0  # seconds
    statement_timeout: Optional[float] = None

    @property
    def connection_string(self) -> str:
        """Generate connection string from settings."""
        return (
            f"host={self.host} "
            f"port={self.port} "
            f"dbname={self.dbname} "
            f"user={self.user} "
            f"password={self.password}"
        )
