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
    connection_timeout: float = 5.0
    statement_timeout: Optional[float] = None

    @property
    def connection_string(self) -> str:
        """Generate database connection string."""
        return self.get_connection_string()

    def get_connection_string(self, timeout: Optional[float] = None) -> str:
        """Generate connection string with optional timeout override."""
        conn_str = (f"host={self.host} "
                    f"port={self.port} "
                    f"dbname={self.dbname} "
                    f"user={self.user} "
                    f"password={self.password}")

        if timeout:
            conn_str += f" connect_timeout={int(timeout)}"  # Changed from timeout to connect_timeout
        return conn_str