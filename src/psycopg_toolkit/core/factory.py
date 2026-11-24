"""Factory for TransactionManager, kept for backward compatibility.

``Database.get_transaction_manager()`` constructs the manager directly; there is no import cycle
between ``database`` and ``transaction`` to break.
"""

from collections.abc import Callable

from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from .transaction import TransactionManager


def create_transaction_manager(
    pool: AsyncConnectionPool, json_adapter_configurator: Callable[[AsyncConnection], None] | None = None
) -> TransactionManager:
    """Create a TransactionManager instance.

    Equivalent to ``TransactionManager(pool, json_adapter_configurator)``.

    Args:
        pool: The connection pool to use
        json_adapter_configurator: Optional function to configure JSON adapters on connections

    Returns:
        TransactionManager: A new transaction manager instance
    """
    return TransactionManager(pool, json_adapter_configurator)
