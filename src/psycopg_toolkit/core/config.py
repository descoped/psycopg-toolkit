from dataclasses import dataclass
from typing import Any


@dataclass
class DatabaseSettings:
    """Database connection and pool configuration settings.

    This class manages PostgreSQL database connection parameters and connection pool settings.
    It provides methods to generate connection strings and convert settings to dictionaries.

    Attributes:
        host (str): Database server hostname or IP address
        port (int): Database server port number
        dbname (str): Name of the database to connect to
        user (str): Username for database authentication
        password (str): Password for database authentication
        min_pool_size (int): Minimum number of connections in the pool (default: 5)
        max_pool_size (int): Maximum number of connections in the pool (default: 20)
        pool_timeout (int): Maximum time in seconds to wait for a connection (default: 30)
        connection_timeout (float): Connection establishment timeout in seconds (default: 5.0)
        statement_timeout (Optional[float]): SQL statement execution timeout in seconds (default: None)
        enable_json_adapters (bool): Whether to enable psycopg JSON adapters for JSONB support (default: True)
    """

    host: str
    port: int
    dbname: str
    user: str
    password: str
    min_pool_size: int = 5
    max_pool_size: int = 20
    pool_timeout: int = 30
    connection_timeout: float = 5.0
    statement_timeout: float | None = None
    enable_json_adapters: bool = True

    @property
    def connection_string(self) -> str:
        """Generate a PostgreSQL connection string using current settings.

        Returns:
            str: Formatted connection string for psycopg
        """
        return self.get_connection_string()

    def get_connection_string(self, timeout: float | None = None) -> str:
        """Generate a PostgreSQL connection string with optional timeout override.

        Args:
            timeout (Optional[float]): Optional connection timeout override in seconds

        Returns:
            str: Formatted connection string for psycopg
        """
        conn_str = f"host={self.host} port={self.port} dbname={self.dbname} user={self.user} password={self.password}"
        if timeout:
            conn_str += f" connect_timeout={int(timeout)}"
        return conn_str

    def to_dict(self, connection_only: bool = True) -> dict[str, Any]:
        """Convert settings to a dictionary.

        Args:
            connection_only (bool): If True, include only connection parameters.
                                  If False, include all settings including pool configuration.

        Returns:
            Dict[str, Any]: Dictionary containing the settings
        """
        if connection_only:
            return {
                "host": self.host,
                "port": self.port,
                "dbname": self.dbname,
                "user": self.user,
                "password": self.password,
            }

        return {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "password": self.password,
            "min_pool_size": self.min_pool_size,
            "max_pool_size": self.max_pool_size,
            "pool_timeout": self.pool_timeout,
            "connection_timeout": self.connection_timeout,
            "statement_timeout": self.statement_timeout,
            "enable_json_adapters": self.enable_json_adapters,
        }
