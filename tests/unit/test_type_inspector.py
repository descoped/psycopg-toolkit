"""Unit tests for TypeInspector."""

import types
from typing import Any, Union
from uuid import UUID

from pydantic import BaseModel, Field

from psycopg_toolkit.utils.type_inspector import TypeInspector


class TestTypeInspector:
    """Test TypeInspector field detection capabilities."""

    def test_detect_dict_fields(self):
        """Test detection of Dict fields."""

        class TestModel(BaseModel):
            id: int
            name: str
            data: dict[str, Any]
            metadata: dict[str, str]
            config: dict[str, str | int]

        json_fields = TypeInspector.detect_json_fields(TestModel)
        assert json_fields == {"data", "metadata", "config"}

    def test_detect_list_fields(self):
        """Test detection of List fields."""

        class TestModel(BaseModel):
            id: int
            name: str
            tags: list[str]
            items: list[dict[str, Any]]
            numbers: list[int]
            complex_list: list[str | dict[str, Any]]

        json_fields = TypeInspector.detect_json_fields(TestModel)
        assert json_fields == {"tags", "items", "numbers", "complex_list"}

    def test_detect_optional_json_fields(self):
        """Test detection of Optional JSON fields."""

        class TestModel(BaseModel):
            id: int
            name: str
            settings: dict[str, Any] | None = None
            tags: list[str] | None = None
            metadata: dict[str, str] | None = None
            optional_list: list[int] | None = None

        json_fields = TypeInspector.detect_json_fields(TestModel)
        assert json_fields == {"settings", "tags", "metadata", "optional_list"}

    def test_detect_union_json_fields(self):
        """Test detection of Union types with JSON components."""

        class TestModel(BaseModel):
            id: int
            name: str
            flexible: str | dict[str, Any]
            mixed: int | list[str] | dict[str, str]
            optional_union: None | dict[str, Any] | list[str]

        json_fields = TypeInspector.detect_json_fields(TestModel)
        assert json_fields == {"flexible", "mixed", "optional_union"}

    def test_ignore_non_json_fields(self):
        """Test that non-JSON fields are ignored."""

        class TestModel(BaseModel):
            id: int
            uuid_field: UUID
            name: str
            active: bool
            value: float
            count: int | None = None
            union_basic: str | int

        json_fields = TypeInspector.detect_json_fields(TestModel)
        assert json_fields == set()

    def test_complex_nested_types(self):
        """Test complex nested type structures."""

        class TestModel(BaseModel):
            id: int
            name: str
            complex_field: dict[str, str | list[dict[str, Any]]]
            optional_complex: list[dict[str, str | None]] | None = None
            deeply_nested: dict[str, dict[str, list[str | int]]]

        json_fields = TypeInspector.detect_json_fields(TestModel)
        assert json_fields == {"complex_field", "optional_complex", "deeply_nested"}

    def test_empty_model(self):
        """Test empty model returns empty set."""

        class EmptyModel(BaseModel):
            pass

        json_fields = TypeInspector.detect_json_fields(EmptyModel)
        assert json_fields == set()

    def test_mixed_model(self):
        """Test model with mix of JSON and non-JSON fields."""

        class MixedModel(BaseModel):
            # Non-JSON fields
            id: UUID
            name: str
            active: bool
            count: int

            # JSON fields
            metadata: dict[str, Any]
            tags: list[str]
            settings: dict[str, str] | None = None

            # More non-JSON fields
            created_at: str | None = None
            value: int | str  # Union without dict/list

        json_fields = TypeInspector.detect_json_fields(MixedModel)
        assert json_fields == {"metadata", "tags", "settings"}

    def test_get_field_types(self):
        """Test getting field types mapping."""

        class TestModel(BaseModel):
            id: int
            name: str
            metadata: dict[str, Any]
            tags: list[str] | None = None

        field_types = TypeInspector.get_field_types(TestModel)

        assert len(field_types) == 4
        assert "id" in field_types
        assert "name" in field_types
        assert "metadata" in field_types
        assert "tags" in field_types

    def test_analyze_field_type_dict(self):
        """Test analyzing Dict type annotation."""
        analysis = TypeInspector.analyze_field_type(dict[str, Any])

        assert analysis["is_json"] is True
        assert analysis["origin"] is dict
        assert analysis["is_optional"] is False
        assert "dict" in analysis["annotation_str"]

    def test_analyze_field_type_list(self):
        """Test analyzing List type annotation."""
        analysis = TypeInspector.analyze_field_type(list[str])

        assert analysis["is_json"] is True
        assert analysis["origin"] is list
        assert analysis["is_optional"] is False
        assert "list" in analysis["annotation_str"]

    def test_analyze_field_type_optional(self):
        """Test analyzing Optional type annotation."""
        analysis = TypeInspector.analyze_field_type(dict[str, str] | None)

        assert analysis["is_json"] is True
        assert analysis["origin"] in (Union, types.UnionType)
        assert analysis["is_optional"] is True
        assert type(None) in analysis["args"]

    def test_analyze_field_type_union(self):
        """Test analyzing Union type annotation."""
        analysis = TypeInspector.analyze_field_type(str | dict[str, Any])

        assert analysis["is_json"] is True
        assert analysis["origin"] in (Union, types.UnionType)
        assert analysis["is_optional"] is False

    def test_analyze_field_type_basic(self):
        """Test analyzing basic type annotation."""
        analysis = TypeInspector.analyze_field_type(str)

        assert analysis["is_json"] is False
        assert analysis["origin"] is None
        assert analysis["is_optional"] is False
        assert analysis["annotation_str"] == "<class 'str'>"

    def test_pydantic_field_with_default(self):
        """Test fields with default values and Field specifications."""

        class TestModel(BaseModel):
            id: int
            metadata: dict[str, Any] = Field(default_factory=dict)
            tags: list[str] = Field(default_factory=list)
            optional_data: dict[str, str] | None = Field(default=None)
            name: str = Field(default="default_name")

        json_fields = TypeInspector.detect_json_fields(TestModel)
        assert json_fields == {"metadata", "tags", "optional_data"}

    def test_inheritance_model(self):
        """Test detection in inherited models."""

        class BaseTestModel(BaseModel):
            id: int
            base_metadata: dict[str, Any]

        class DerivedTestModel(BaseTestModel):
            name: str
            derived_tags: list[str]
            settings: dict[str, str] | None = None

        json_fields = TypeInspector.detect_json_fields(DerivedTestModel)
        # Should detect fields from both base and derived classes
        assert json_fields == {"base_metadata", "derived_tags", "settings"}

    def test_generic_model(self):
        """Test detection with generic type parameters."""
        from typing import Generic, TypeVar

        T = TypeVar("T")

        class GenericModel(BaseModel, Generic[T]):
            id: int
            data: dict[str, T]
            items: list[T]

        # Instantiate with specific type
        class ConcreteModel(GenericModel[str]):
            name: str

        json_fields = TypeInspector.detect_json_fields(ConcreteModel)
        assert json_fields == {"data", "items"}

    def test_edge_cases(self):
        """Test edge cases and potential error conditions."""

        class EdgeCaseModel(BaseModel):
            # Nested Union types
            complex_union: dict[str, Any] | list[str] | int
            # Multiple Optional levels
            nested_optional: dict[str, str] | None | None
            # Empty containers
            empty_dict: dict[str, Any]
            empty_list: list[Any]

        json_fields = TypeInspector.detect_json_fields(EdgeCaseModel)
        assert json_fields == {"complex_union", "nested_optional", "empty_dict", "empty_list"}

    def test_typing_module_compatibility(self):
        """Test compatibility with different typing module constructs."""

        class TypingModel(BaseModel):
            # Different ways to specify the same types
            dict1: dict[str, Any]
            dict2: dict[str, Any]
            list1: list[str]
            list2: list[str]
            optional1: dict[str, str] | None
            optional2: dict[str, str] | None
            union1: dict[str, Any] | list[str]
            union2: dict[str, Any] | list[str]

        json_fields = TypeInspector.detect_json_fields(TypingModel)
        expected_fields = {"dict1", "dict2", "list1", "list2", "optional1", "optional2", "union1", "union2"}
        assert json_fields == expected_fields

    def test_error_handling(self):
        """Test error handling for malformed models."""

        # Test with non-BaseModel class
        class NotPydantic:
            def __init__(self):
                self.field = "value"

        # Should return empty set and log warning
        json_fields = TypeInspector.get_field_types(NotPydantic)
        assert json_fields == {}

    def test_real_world_model(self):
        """Test with a realistic, complex model."""
        from datetime import datetime
        from decimal import Decimal

        class UserProfile(BaseModel):
            # Basic fields (not JSON)
            id: UUID
            username: str
            email: str
            is_active: bool
            created_at: datetime

            # JSON fields
            metadata: dict[str, Any]
            preferences: dict[str, str | bool | int]
            tags: list[str]
            permissions: list[dict[str, str | bool]]

            # Optional JSON fields
            settings: dict[str, Any] | None = None
            custom_fields: list[dict[str, str]] | None = None

            # Complex JSON field
            profile_data: dict[str, str | int | list[str] | dict[str, Any]]

            # Non-JSON optional fields
            last_login: datetime | None = None
            balance: Decimal | None = None

        json_fields = TypeInspector.detect_json_fields(UserProfile)
        expected_json_fields = {
            "metadata",
            "preferences",
            "tags",
            "permissions",
            "settings",
            "custom_fields",
            "profile_data",
        }
        assert json_fields == expected_json_fields
