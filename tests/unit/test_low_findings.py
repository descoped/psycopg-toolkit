"""Review findings L1, L2 and L7, plus TypeInspector.accepts_str."""

import typing
from dataclasses import asdict, fields
from typing import Annotated, Any, Optional, Union

import pytest
from psycopg.conninfo import conninfo_to_dict
from pydantic import BaseModel

from psycopg_toolkit import DatabaseSettings, TypeInspector


def settings(**kw: Any) -> DatabaseSettings:
    return DatabaseSettings(host="h", port=5432, dbname="d", user="u", password="p", **kw)


class TestConnectTimeout:
    """L1: libpq takes whole seconds and treats 0 as 'wait forever'."""

    @pytest.mark.parametrize(("timeout", "expected"), [(5.0, "5"), (5, "5"), (2.5, "3"), (0.5, "1"), (0.01, "1")])
    def test_positive_timeout_never_becomes_zero(self, timeout: float, expected: str) -> None:
        assert conninfo_to_dict(settings().get_connection_string(timeout))["connect_timeout"] == expected

    @pytest.mark.parametrize("timeout", [None, 0, 0.0, -1])
    def test_no_or_non_positive_timeout_is_omitted(self, timeout: float | None) -> None:
        assert "connect_timeout" not in conninfo_to_dict(settings().get_connection_string(timeout))


class TestToDict:
    """L7: to_dict(False) covers every setting, so a new field cannot be missed."""

    def test_full_dict_has_every_field(self) -> None:
        s = settings(statement_timeout=3.0)
        assert s.to_dict(connection_only=False) == asdict(s)
        assert set(s.to_dict(connection_only=False)) == {f.name for f in fields(DatabaseSettings)}

    def test_connection_only_keys_unchanged(self) -> None:
        assert settings().to_dict() == {"host": "h", "port": 5432, "dbname": "d", "user": "u", "password": "p"}


class TestBareTypingAliases:
    """L2: typing.List / typing.Dict behave like list / dict."""

    @pytest.mark.parametrize(
        ("annotation", "is_json"),
        [
            (list, False),
            (typing.List, False),  # noqa: UP006 - the legacy alias is what is under test
            (Optional[typing.List], False),  # noqa: UP006, UP045
            (dict, True),
            (typing.Dict, True),  # noqa: UP006
            (list[str], True),
            (typing.List[str], True),  # noqa: UP006
            (dict[str, Any] | None, True),
        ],
    )
    def test_detection(self, annotation: Any, is_json: bool) -> None:
        model = type("M", (BaseModel,), {"__annotations__": {"f": annotation}})
        assert ("f" in TypeInspector.detect_json_fields(model)) is is_json


class TestAcceptsStr:
    @pytest.mark.parametrize(
        ("annotation", "expected"),
        [
            (str, True),
            (Any, True),
            (dict[str, Any] | str, True),
            (Union[list[int], str, None], True),  # noqa: UP007
            (Annotated[str | None, "meta"], True),
            (dict[str, Any], False),
            (list[str] | None, False),
            (int, False),
        ],
    )
    def test_accepts_str(self, annotation: Any, expected: bool) -> None:
        assert TypeInspector.accepts_str(annotation) is expected
