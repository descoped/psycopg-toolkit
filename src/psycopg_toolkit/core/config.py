from dataclasses import dataclass
from typing import Optional, Any, Dict


@dataclass
class DatabaseSettings:
    """Database connection and pool settings."""
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
        """Generate connection string."""
        return self.get_connection_string()

    def get_connection_string(self, timeout: Optional[float] = None) -> str:
        """Generate connection string with optional timeout."""
        conn_str = (
            f"host={self.host} "
            f"port={self.port} "
            f"dbname={self.dbname} "
            f"user={self.user} "
            f"password={self.password}"
        )
        if timeout:
            conn_str += f" connect_timeout={int(timeout)}"
        return conn_str

    def to_dict(self, connection_only: bool = True) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        if connection_only:
            return {
                'host': self.host,
                'port': self.port,
                'dbname': self.dbname,
                'user': self.user,
                'password': self.password
            }

        return {
            'host': self.host,
            'port': self.port,
            'dbname': self.dbname,
            'user': self.user,
            'password': self.password,
            'min_pool_size': self.min_pool_size,
            'max_pool_size': self.max_pool_size,
            'pool_timeout': self.pool_timeout,
            'connection_timeout': self.connection_timeout,
            'statement_timeout': self.statement_timeout
        }
