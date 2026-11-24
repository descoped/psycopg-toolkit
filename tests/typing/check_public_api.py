"""Static type checks for the public API, verified by pyright (not collected by pytest).

Run: `pyright tests/typing` and `uv run ty check`. Each `assert_type` must hold, and each
`pyright: ignore[...]` / `ty: ignore[...]` marks an error that MUST occur: pyright's
reportUnnecessaryTypeIgnoreComment and ty's unused-ignore-comment fail the check if a
deliberately wrong usage stops being an error.
"""

# pyright: reportUnnecessaryTypeIgnoreComment=true

from typing import assert_type
from uuid import UUID

from psycopg import AsyncConnection
from psycopg.sql import Composed
from pydantic import BaseModel

from psycopg_toolkit import BaseRepository, DecimalMode, JSONHandler
from psycopg_toolkit.utils import PsycopgHelper


class User(BaseModel):
    id: UUID
    name: str


class UserRepository(BaseRepository[User, UUID]):
    pass


class NotAModel:
    pass


async def repository_types(conn: AsyncConnection, user_id: UUID, user: User) -> None:
    repo = UserRepository(conn, "users", User)

    # get_by_id raises RecordNotFoundError when missing, it never returns None
    assert_type(await repo.get_by_id(user_id), User)
    assert_type(await repo.get_all(), list[User])
    assert_type(await repo.create(user), User)
    assert_type(await repo.create_bulk([user]), list[User])
    assert_type(await repo.update(user_id, {"name": "x"}), User)
    assert_type(await repo.exists(user_id), bool)

    # The model type must be a Pydantic model
    BaseRepository[NotAModel, int]  # pyright: ignore[reportInvalidTypeArguments]  # ty: ignore[invalid-type-arguments]

    # decimal_as only accepts the DecimalMode literals
    UserRepository(conn, "users", User, decimal_as="str")
    UserRepository(conn, "users", User, decimal_as="int")  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]


def json_handler_types(mode: DecimalMode) -> None:
    assert_type(JSONHandler.serialize({}, decimal_as=mode), str)
    JSONHandler.serialize({}, decimal_as="decimal")  # pyright: ignore[reportArgumentType]  # ty: ignore[invalid-argument-type]


def helper_types(data: dict[str, object]) -> None:
    assert_type(PsycopgHelper.build_select_query("t"), Composed)
    assert_type(PsycopgHelper.build_insert_query("t", data), Composed)
    assert_type(PsycopgHelper.build_update_query("t", data, {"id": 1}), Composed)
    assert_type(PsycopgHelper.build_delete_query("t", {"id": 1}), Composed)
    PsycopgHelper.get_columns(data.keys())
