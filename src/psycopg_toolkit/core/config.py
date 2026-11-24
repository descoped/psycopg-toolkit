import math
from dataclasses import asdict, dataclass
from typing import Any

from psycopg.conninfo import make_conninfo

_CONNECTION_FIELDS = ("host", "port", "dbname", "user", "password")


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
        enable_json_adapters (bool): Reset every connection the toolkit hands out to the standard
            library's JSON loads/dumps, overriding loaders registered globally with
            ``psycopg.types.json.set_json_loads`` (default: True). With False the connection keeps
            its own loaders. psycopg decodes json/jsonb to Python objects either way.
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

        Values are quoted by libpq rules where needed (spaces, quotes, backslashes), so any
        password or name is passed through intact.

        Args:
            timeout (Optional[float]): Optional connection timeout override in seconds

        Returns:
            str: Formatted connection string for psycopg
        """
        params: dict[str, Any] = {
            "host": self.host,
            "port": self.port,
            "dbname": self.dbname,
            "user": self.user,
            "password": self.password,
        }
        if timeout is not None and timeout > 0:
            # libpq takes whole seconds and reads 0 as 'wait forever', so round up: 0.5 must not become 0.
            params["connect_timeout"] = max(1, math.ceil(timeout))
        return make_conninfo(**params)

    def to_dict(self, connection_only: bool = True) -> dict[str, Any]:
        """Convert settings to a dictionary.

        Args:
            connection_only (bool): If True, include only connection parameters.
                                  If False, include every setting, pool and timeout configuration included.

        Returns:
            Dict[str, Any]: Dictionary containing the settings
        """
        if connection_only:
            return {name: getattr(self, name) for name in _CONNECTION_FIELDS}
        return asdict(self)
