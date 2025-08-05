"""
PsycopgHelper: A utility class for safe SQL query construction using psycopg3.

This class provides methods to build SQL queries safely using psycopg3's SQL composition
functionality, preventing SQL injection attacks by properly escaping all user inputs.

Key security features:
- Uses psycopg.sql.SQL for safe query composition
- Uses psycopg.sql.Identifier for table and column names
- Uses psycopg.sql.Placeholder for parameter values
"""

from typing import Any

from psycopg.sql import SQL, Identifier, Placeholder


class PsycopgHelper:
    @staticmethod
    def get_columns(keys: dict[str, Any]) -> list[Identifier]:
        """
        Convert dictionary keys to a list of SQL Identifiers for safe column name handling.

        Args:
            keys: Dictionary keys representing column names

        Returns:
            List of SQL-safe Identifier objects
        """
        return [Identifier(k) for k in keys]

    @staticmethod
    def get_columns_as_list(keys: dict[str, Any]) -> list[str]:
        """
        Convert dictionary keys to a list of column names as strings.

        Args:
            keys: Dictionary keys representing column names

        Returns:
            List of column names as strings
        """
        return list(keys)

    @staticmethod
    def get_placeholders(count: int) -> list[Placeholder]:
        """
        Generate a list of SQL placeholders for parameterized queries.

        Args:
            count: Number of placeholders needed

        Returns:
            List of Placeholder objects for safe parameter binding
        """
        return [Placeholder() for _ in range(count)]

    @staticmethod
    def build_select_query(
        table_name: str, columns: list[str] | None = None, where_clause: dict[str, Any] | None = None
    ) -> SQL:
        """
        Build a safe SELECT query with optional column selection and WHERE clause.

        Args:
            table_name: Name of the table to query
            columns: Optional list of column names to select (defaults to *)
            where_clause: Optional dictionary of column-value pairs for WHERE conditions

        Returns:
            SQL object representing the parameterized query
        """
        select_columns = SQL("*") if not columns else SQL(", ").join(map(Identifier, columns))

        if where_clause:
            conditions = SQL(" AND ").join([SQL("{} = {}").format(Identifier(k), Placeholder()) for k in where_clause])
            where_sql = SQL(" WHERE {}").format(conditions)
        else:
            where_sql = SQL("")

        query = SQL("SELECT {} FROM {}{}").format(select_columns, Identifier(table_name), where_sql)

        return query

    @staticmethod
    def build_insert_query(table_name: str, data: dict[str, Any], batch_size: int = 1) -> SQL:
        """
        Build a safe INSERT query, supporting batch inserts.

        Args:
            table_name: Name of the table to insert into
            data: Dictionary of column-value pairs to insert (single record)
            batch_size: Number of records to insert (for batch inserts)

        Returns:
            SQL object representing the parameterized query

        Example:
            >>> query = PsycopgHelper.build_insert_query("users", {"name": "John", "age": 30}, batch_size=1)
            >>> cur.execute(query, list(data.values()))
        """
        columns = PsycopgHelper.get_columns(data.keys())

        # Generate placeholders for batch insert
        batch_placeholders = []
        for _ in range(batch_size):
            placeholders = PsycopgHelper.get_placeholders(len(data))
            batch_placeholders.append(SQL("({})").format(SQL(", ").join(placeholders)))

        return SQL("INSERT INTO {} ({}) VALUES {}").format(
            Identifier(table_name), SQL(", ").join(columns), SQL(", ").join(batch_placeholders)
        )

    @staticmethod
    def build_update_query(table_name: str, data: dict[str, Any], where_clause: dict[str, Any]) -> SQL:
        """
        Build a safe UPDATE query with SET and WHERE clauses.

        Args:
            table_name: Name of the table to update
            data: Dictionary of column-value pairs to update
            where_clause: Dictionary of column-value pairs for WHERE conditions

        Returns:
            SQL object representing the parameterized query

        Example:
            >>> query = PsycopgHelper.build_update_query("users",
                                                         {"name": "John"},
                                                         {"id": 1})
            >>> cur.execute(query, list(data.values()) + list(where_clause.values()))
        """
        set_items = SQL(", ").join([SQL("{} = {}").format(Identifier(k), Placeholder()) for k in data])

        where_conditions = SQL(" AND ").join(
            [SQL("{} = {}").format(Identifier(k), Placeholder()) for k in where_clause]
        )

        return SQL("UPDATE {} SET {} WHERE {}").format(Identifier(table_name), set_items, where_conditions)

    @staticmethod
    def build_delete_query(table_name: str, where_clause: dict[str, Any]) -> SQL:
        """
        Build a safe DELETE query with WHERE clause.

        Args:
            table_name: Name of the table to delete from
            where_clause: Dictionary of column-value pairs for WHERE conditions

        Returns:
            SQL object representing the parameterized query

        Example:
            >>> query = PsycopgHelper.build_delete_query("users", {"id": 1})
            >>> cur.execute(query, list(where_clause.values()))
        """
        conditions = SQL(" AND ").join([SQL("{} = {}").format(Identifier(k), Placeholder()) for k in where_clause])

        return SQL("DELETE FROM {} WHERE {}").format(Identifier(table_name), conditions)
