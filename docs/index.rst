README.rst
===========

psyco-db
--------

A Python PostgreSQL database utility that provides connection pooling and robust database management capabilities.

Features
~~~~~~~~

* Asynchronous connection pooling using ``psycopg-pool``
* Automatic retry mechanism for database connections
* Connection pool management with customizable settings
* Initialization callbacks support
* Error handling with custom exceptions

Installation
~~~~~~~~~~~

From PyPI
^^^^^^^^^

.. code-block:: bash

    pip install pysco-db

From TestPyPI
^^^^^^^^^^^^

.. code-block:: bash

    pip install --index-url https://test.pypi.org/simple/ pysco-db

Installing from Wheel File
^^^^^^^^^^^^^^^^^^^^^^^^

If you have a wheel file (``.whl``), you can install it directly using pip:

.. code-block:: bash

    pip install path/to/pysco_db-0.1.0-py3-none-any.whl

Or add it as a dependency in your project's ``pyproject.toml``:

.. code-block:: toml

    [tool.poetry.dependencies]
    pysco-db = { path = "path/to/pysco_db-0.1.0-py3-none-any.whl" }

Then run ``poetry install`` to install it.

Local Development Installation
^^^^^^^^^^^^^^^^^^^^^^^^^^^

1. Clone the repository
2. Install Poetry if you haven't already:

   .. code-block:: bash

       curl -sSL https://install.python-poetry.org | python3 -

3. Install dependencies:

   .. code-block:: bash

       poetry install

Publishing
~~~~~~~~~

To TestPyPI
^^^^^^^^^^

1. Configure TestPyPI repository:

   .. code-block:: bash

       poetry config repositories.testpypi https://test.pypi.org/simple/

2. Set your TestPyPI API token:

   .. code-block:: bash

       poetry config pypi-token.testpypi YOUR_TESTPYPI_TOKEN

3. Build and publish to TestPyPI:

   .. code-block:: bash

       poetry publish -r testpypi --build

To Production PyPI
^^^^^^^^^^^^^^^^

1. Set your PyPI API token:

   .. code-block:: bash

       poetry config pypi-token.pypi YOUR_PYPI_TOKEN

2. Build and publish to PyPI:

   .. code-block:: bash

       poetry publish --build

Usage
~~~~~

Basic Setup
^^^^^^^^^^

.. code-block:: python

    from psyco_db import Database, DatabaseSettings

    # Configure database settings
    settings = DatabaseSettings(
        host="localhost",
        port=5432,
        dbname="your_database",
        user="your_user",
        password="your_password",
        min_pool_size=5,    # Optional (default: 5)
        max_pool_size=20,   # Optional (default: 20)
        pool_timeout=30     # Optional (default: 30)
    )

    # Create database instance
    db = Database(settings)

Initialization and Cleanup
^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    async def main():
        # Initialize the database pool
        await db.init_db()

        # ... your application code ...

        # Cleanup when shutting down
        await db.cleanup()

Using Database Connections
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    async def example_query():
        async with db.connection() as conn:
            # Execute a query
            async with conn.cursor() as cur:
                await cur.execute("SELECT * FROM your_table")
                results = await cur.fetchall()
                return results

Registration Callbacks
^^^^^^^^^^^^^^^^^^^

You can register initialization callbacks that will be executed after the pool is created:

.. code-block:: python

    async def init_callback(pool):
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("CREATE TABLE IF NOT EXISTS ...")

    # Register the callback
    db.register_init_callback(init_callback)

Error Handling
^^^^^^^^^^^^

The library provides custom exceptions for different scenarios:

.. code-block:: python

    from psyco_db import (
        PsycoDBException,
        DatabaseConnectionError,
        DatabasePoolError,
        DatabaseNotAvailable
    )

    async def example_with_error_handling():
        try:
            async with db.connection() as conn:
                # Your database operations
                pass
        except DatabaseConnectionError as e:
            print(f"Connection error: {e}")
        except DatabasePoolError as e:
            print(f"Pool error: {e}")
        except DatabaseNotAvailable as e:
            print(f"Database not available: {e}")
        except PsycoDBException as e:
            print(f"General database error: {e}")

Connection Pool Management
^^^^^^^^^^^^^^^^^^^^^^^

The library automatically manages the connection pool:

* Retries connection attempts with exponential backoff
* Maintains minimum and maximum pool sizes
* Handles connection timeouts
* Automatically closes connections when they're no longer needed

Database Health Check
^^^^^^^^^^^^^^^^^^

.. code-block:: python

    # Check if database is reachable
    try:
        is_available = db.ping_postgres()
        print(f"Database is available: {is_available}")
    except DatabaseConnectionError as e:
        print(f"Database is not available: {e}")

Development
~~~~~~~~~~

Running Tests
^^^^^^^^^^^

.. code-block:: bash

    poetry run pytest

License
~~~~~~~

This project is licensed under the MIT License.

transaction_manager.rst
=====================

Transaction Management
--------------------

The ``TransactionManager`` provides a robust interface for managing database transactions in psyco-db. It handles transaction lifecycle, automatic rollback on errors, and proper resource cleanup.

Quick Start
~~~~~~~~~

.. code-block:: python

    from psyco_db import Database, DatabaseSettings

    # Initialize database
    db = Database(settings)
    await db.init_db()

    # Get transaction manager
    tm = await db.get_transaction_manager()

    # Use in transaction
    async with tm.transaction() as conn:
        async with conn.cursor() as cur:
            await cur.execute("INSERT INTO users (id, name) VALUES (%s, %s)",
                            (user_id, name))


