# src/psyco_db/core/config.py

from dataclasses import dataclass


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
