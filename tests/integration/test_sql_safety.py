"""Regression tests for SQL composition and connection-string safety.

Covers identifiers that need quoting (reserved words, mixed case), savepoint names that are not bare
SQL words, and connection parameters that need quoting in libpq conninfo.
"""

from collections.abc import AsyncGenerator
from uuid import uuid4

import pytest
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from pydantic import BaseModel

from psycopg_toolkit import BaseRepository, Database, DatabaseConnectionError, DatabaseSettings, TransactionManager


class Item(BaseModel):
    id: int
    name: str


@pytest.fixture
async def database(test_settings: DatabaseSettings) -> AsyncGenerator[Database, None]:
    db = Database(test_settings)
    yield db
    await db.cleanup()


@pytest.fixture
async def quoted_tables(database: Database) -> AsyncGenerator[None, None]:
    """Tables whose names only work when quoted: a reserved word and a mixed-case name."""
    async with database.connection() as conn:
        for table in ("order", "MixedCase"):
            await conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table)))
            await conn.execute(sql.SQL("CREATE TABLE {} (id int PRIMARY KEY, name text)").format(sql.Identifier(table)))
            await conn.execute(sql.SQL("INSERT INTO {} VALUES (1, 'one')").format(sql.Identifier(table)))
        await conn.commit()
    yield
    async with database.connection() as conn:
        for table in ("order", "MixedCase"):
            await conn.execute(sql.SQL("DROP TABLE IF EXISTS {}").format(sql.Identifier(table)))
        await conn.commit()


class TestRepositoryIdentifierQuoting:
    @pytest.mark.parametrize("table", ["order", "MixedCase"])
    async def test_exists_quotes_identifiers(self, database: Database, quoted_tables: None, table: str) -> None:
        async with database.connection() as conn:
            repo = BaseRepository(conn, table, Item)
            assert await repo.exists(1) is True
            assert await repo.exists(2) is False

    @pytest.mark.parametrize("table", ["order", "MixedCase"])
    async def test_other_crud_methods_already_quote(self, database: Database, quoted_tables: None, table: str) -> None:
        """Characterization: the psycopg.sql based methods work on these tables today."""
        async with database.connection() as conn:
            repo = BaseRepository(conn, table, Item)
            assert (await repo.get_by_id(1)).name == "one"
            assert [i.id for i in await repo.get_all()] == [1]


class TestSavepointNames:
    @pytest.fixture
    async def tm(self, database: Database) -> TransactionManager:
        return TransactionManager(await database.get_pool())

    @pytest.mark.parametrize("name", ["sp1", "before-import", "Mixed Case", "select"])
    async def test_savepoint_names_are_quoted(self, tm: TransactionManager, name: str) -> None:
        async with tm.transaction(savepoint=name) as conn:
            assert (await (await conn.execute("SELECT 1")).fetchone()) == (1,)

    @pytest.mark.parametrize("name", ["sp1", "before-import"])
    async def test_error_inside_savepoint_rolls_back_and_propagates(self, tm: TransactionManager, name: str) -> None:
        """Characterization: errors still roll back and surface as DatabaseConnectionError with the cause."""
        table = f"sp_{uuid4().hex[:8]}"
        with pytest.raises(DatabaseConnectionError) as excinfo:
            async with tm.transaction(savepoint=name) as conn:
                await conn.execute(sql.SQL("CREATE TABLE {} (id int)").format(sql.Identifier(table)))
                raise ValueError("boom")
        assert isinstance(excinfo.value.__cause__, ValueError)
        async with tm.transaction() as conn:
            exists = await (await conn.execute("SELECT to_regclass(%s)", [table])).fetchone()
            assert exists == (None,)


SPECIAL_PASSWORDS = ["secret with space", "it's", r"back\slash", "key=value", "trailing "]


class TestConnectionString:
    @pytest.mark.parametrize("password", SPECIAL_PASSWORDS)
    def test_values_round_trip_through_conninfo(self, password: str) -> None:
        settings = DatabaseSettings(host="db.local", port=5433, dbname="app db", user="o'neil", password=password)
        parsed = conninfo_to_dict(settings.get_connection_string(7))
        assert parsed == {
            "host": "db.local",
            "port": "5433",
            "dbname": "app db",
            "user": "o'neil",
            "password": password,
            "connect_timeout": "7",
        }

    def test_plain_values_keep_the_existing_format(self) -> None:
        """Characterization: ordinary values produce exactly the same string as before."""
        settings = DatabaseSettings(
            host="localhost", port=5432, dbname="test_db", user="test_user", password="test_pass"
        )
        assert settings.get_connection_string(5) == (
            "host=localhost port=5432 dbname=test_db user=test_user password=test_pass connect_timeout=5"
        )
        assert settings.connection_string == "host=localhost port=5432 dbname=test_db user=test_user password=test_pass"

    async def test_connects_with_a_password_that_needs_quoting(
        self, database: Database, test_settings: DatabaseSettings
    ) -> None:
        role, password = f"role_{uuid4().hex[:8]}", "p w 'q' =x"
        async with database.connection() as conn:
            await conn.execute(
                sql.SQL("CREATE ROLE {} LOGIN PASSWORD {}").format(sql.Identifier(role), sql.Literal(password))
            )
            await conn.commit()
        try:
            special = DatabaseSettings(
                host=test_settings.host,
                port=test_settings.port,
                dbname=test_settings.dbname,
                user=role,
                password=password,
                min_pool_size=1,
                max_pool_size=1,
            )
            db = Database(special)
            try:
                async with db.connection() as conn:
                    assert (await (await conn.execute("SELECT current_user")).fetchone()) == (role,)
            finally:
                await db.cleanup()
        finally:
            async with database.connection() as conn:
                await conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(role)))
                await conn.commit()
