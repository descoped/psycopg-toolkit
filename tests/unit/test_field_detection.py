"""Consolidated tests for field detection functionality.

This module combines tests for:
- TypeInspector field detection capabilities
- BaseRepository JSON field auto-detection
- Field detection edge cases and error handling
"""

import types
from datetime import datetime
from decimal import Decimal
from typing import Any, Generic, TypeVar, Union
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from pydantic import BaseModel, Field

from psycopg_toolkit.repositories.base import BaseRepository
from psycopg_toolkit.utils.type_inspector import TypeInspector


# Test Models
class SimpleTestModel(BaseModel):
    """Simple test model without JSON fields."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    active: bool
    value: int


class JsonTestModel(BaseModel):
    """Test model with various JSON field types."""

    id: UUID = Field(default_factory=uuid4)
    name: str

    # JSON fields
    metadata: dict[str, Any]
    tags: list[str]
    settings: dict[str, str] | None = None
    items: list[dict[str, Any]]
    preferences: dict[str, str | int]


class ComplexTestModel(BaseModel):
    """Complex test model with nested and union types."""

    id: int
    name: str

    # Complex JSON fields
    complex_field: dict[str, str | list[dict[str, Any]]]
    optional_complex: list[dict[str, str | None]] | None = None
    deeply_nested: dict[str, dict[str, list[str | int]]]
    flexible: str | dict[str, Any]
    mixed: int | list[str] | dict[str, str]


class InheritanceBaseModel(BaseModel):
    """Base model for inheritance testing."""

    id: int
    base_metadata: dict[str, Any]


class InheritanceDerivedModel(InheritanceBaseModel):
    """Derived model for inheritance testing."""

    name: str
    derived_tags: list[str]
    settings: dict[str, str] | None = None


T = TypeVar("T")


class GenericTestModel(BaseModel, Generic[T]):
    """Generic model for testing type parameters."""

    id: int
    data: dict[str, T]
    items: list[T]


class ConcreteGenericModel(GenericTestModel[str]):
    """Concrete implementation of generic model."""

    name: str


class RealWorldUserProfile(BaseModel):
    """Realistic complex model for comprehensive testing."""

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


class TestTypeInspectorFieldDetection:
    """Test TypeInspector field detection capabilities."""

    @pytest.mark.parametrize(
        "model_class,expected_fields",
        [
            (SimpleTestModel, set()),
            (JsonTestModel, {"metadata", "tags", "settings", "items", "preferences"}),
            (ComplexTestModel, {"complex_field", "optional_complex", "deeply_nested", "flexible", "mixed"}),
            (InheritanceDerivedModel, {"base_metadata", "derived_tags", "settings"}),
            (ConcreteGenericModel, {"data", "items"}),
            (
                RealWorldUserProfile,
                {"metadata", "preferences", "tags", "permissions", "settings", "custom_fields", "profile_data"},
            ),
        ],
    )
    def test_detect_json_fields_comprehensive(self, model_class, expected_fields):
        """Test comprehensive JSON field detection across different model types."""
        json_fields = TypeInspector.detect_json_fields(model_class)
        assert json_fields == expected_fields

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

    def test_empty_model(self):
        """Test empty model returns empty set."""

        class EmptyModel(BaseModel):
            pass

        json_fields = TypeInspector.detect_json_fields(EmptyModel)
        assert json_fields == set()

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


class TestTypeInspectorAnalysis:
    """Test TypeInspector field analysis capabilities."""

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

    @pytest.mark.parametrize(
        "type_annotation,expected_values",
        [
            (dict[str, Any], {"is_json": True, "origin": dict, "is_optional": False}),
            (list[str], {"is_json": True, "origin": list, "is_optional": False}),
            (dict[str, str] | None, {"is_json": True, "origin": Union, "is_optional": True}),
            (str | dict[str, Any], {"is_json": True, "origin": Union, "is_optional": False}),
            (str, {"is_json": False, "origin": None, "is_optional": False}),
        ],
    )
    def test_analyze_field_type(self, type_annotation, expected_values):
        """Test analyzing different type annotations."""
        analysis = TypeInspector.analyze_field_type(type_annotation)

        for key, expected_value in expected_values.items():
            if key == "origin" and expected_value == Union:
                # Handle both Union and UnionType (Python 3.10+)
                assert analysis[key] in (Union, types.UnionType)
            else:
                assert analysis[key] == expected_value

    def test_error_handling(self):
        """Test error handling for malformed models."""

        # Test with non-BaseModel class
        class NotPydantic:
            def __init__(self):
                self.field = "value"

        # Should return empty dict and handle gracefully
        field_types = TypeInspector.get_field_types(NotPydantic)
        assert field_types == {}


class TestBaseRepositoryJSONDetection:
    """Test BaseRepository JSON field detection functionality."""

    @pytest.fixture
    def mock_connection(self):
        """Create a mock database connection."""
        return AsyncMock()

    def test_auto_detect_json_fields(self, mock_connection):
        """Test automatic JSON field detection."""
        repo = BaseRepository(
            db_connection=mock_connection, table_name="test_table", model_class=JsonTestModel, primary_key="id"
        )

        expected_json_fields = {"metadata", "tags", "settings", "items", "preferences"}
        assert repo.json_fields == expected_json_fields

    def test_explicit_json_fields(self, mock_connection):
        """Test explicit JSON field specification overrides auto-detection."""
        explicit_fields = {"metadata", "custom_field"}

        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=JsonTestModel,
            primary_key="id",
            json_fields=explicit_fields,
        )

        assert repo.json_fields == explicit_fields

    def test_disable_auto_detection(self, mock_connection):
        """Test disabling auto-detection results in no JSON fields."""
        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=JsonTestModel,
            primary_key="id",
            auto_detect_json=False,
        )

        assert repo.json_fields == set()

    def test_explicit_fields_override_auto_detect_false(self, mock_connection):
        """Test explicit fields work even when auto_detect_json=False."""
        explicit_fields = {"metadata"}

        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=JsonTestModel,
            primary_key="id",
            json_fields=explicit_fields,
            auto_detect_json=False,
        )

        assert repo.json_fields == explicit_fields

    def test_simple_model_no_json_fields(self, mock_connection):
        """Test model without JSON fields returns empty set."""
        repo = BaseRepository(
            db_connection=mock_connection, table_name="simple_table", model_class=SimpleTestModel, primary_key="id"
        )

        assert repo.json_fields == set()

    def test_empty_explicit_json_fields(self, mock_connection):
        """Test explicitly providing empty set of JSON fields."""
        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=JsonTestModel,
            primary_key="id",
            json_fields=set(),
        )

        assert repo.json_fields == set()

    def test_json_fields_property_returns_copy(self, mock_connection):
        """Test that json_fields property returns a copy, not the original set."""
        repo = BaseRepository(
            db_connection=mock_connection, table_name="test_table", model_class=JsonTestModel, primary_key="id"
        )

        json_fields_copy1 = repo.json_fields
        json_fields_copy2 = repo.json_fields

        # Should be equal but not the same object
        assert json_fields_copy1 == json_fields_copy2
        assert json_fields_copy1 is not json_fields_copy2

        # Modifying the copy should not affect the original
        json_fields_copy1.add("new_field")
        assert "new_field" not in repo.json_fields

    @pytest.mark.parametrize(
        "model_class,auto_detect,expected_fields",
        [
            (SimpleTestModel, True, set()),
            (JsonTestModel, True, {"metadata", "tags", "settings", "items", "preferences"}),
            (ComplexTestModel, True, {"complex_field", "optional_complex", "deeply_nested", "flexible", "mixed"}),
            (JsonTestModel, False, set()),
            (ComplexTestModel, False, set()),
        ],
    )
    def test_auto_detection_with_different_models(self, mock_connection, model_class, auto_detect, expected_fields):
        """Test auto-detection behavior with different model types."""
        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=model_class,
            primary_key="id",
            auto_detect_json=auto_detect,
        )

        assert repo.json_fields == expected_fields

    def test_repository_attributes(self, mock_connection):
        """Test that all repository attributes are properly set."""
        json_fields = {"metadata", "tags"}

        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="test_table",
            model_class=JsonTestModel,
            primary_key="custom_id",
            json_fields=json_fields,
            auto_detect_json=False,
        )

        assert repo.db_connection == mock_connection
        assert repo.table_name == "test_table"
        assert repo.model_class == JsonTestModel
        assert repo.primary_key == "custom_id"
        assert repo.json_fields == json_fields
        assert repo._auto_detect_json is False

    def test_default_parameters(self, mock_connection):
        """Test repository with default parameters."""
        repo = BaseRepository(db_connection=mock_connection, table_name="test_table", model_class=JsonTestModel)

        # Should use defaults
        assert repo.primary_key == "id"
        assert repo._auto_detect_json is True
        assert repo.json_fields == {"metadata", "tags", "settings", "items", "preferences"}

    def test_real_world_model_detection(self, mock_connection):
        """Test JSON detection with realistic complex model."""
        repo = BaseRepository(
            db_connection=mock_connection,
            table_name="user_profiles",
            model_class=RealWorldUserProfile,
            primary_key="id",
        )

        expected_fields = {
            "metadata",
            "preferences",
            "tags",
            "permissions",
            "settings",
            "custom_fields",
            "profile_data",
        }
        assert repo.json_fields == expected_fields


class TestFieldDetectionIntegration:
    """Integration tests for field detection across TypeInspector and BaseRepository."""

    @pytest.fixture
    def mock_connection(self):
        """Create a mock database connection."""
        return AsyncMock()

    def test_type_inspector_repository_consistency(self, mock_connection):
        """Test that TypeInspector and BaseRepository detect the same fields."""
        test_models = [
            SimpleTestModel,
            JsonTestModel,
            ComplexTestModel,
            InheritanceDerivedModel,
            ConcreteGenericModel,
            RealWorldUserProfile,
        ]

        for model_class in test_models:
            # Get fields from TypeInspector
            inspector_fields = TypeInspector.detect_json_fields(model_class)

            # Get fields from BaseRepository with auto-detection enabled
            repo = BaseRepository(
                db_connection=mock_connection,
                table_name="test_table",
                model_class=model_class,
                primary_key="id",
                auto_detect_json=True,
            )
            repo_fields = repo.json_fields

            # Should be identical
            assert inspector_fields == repo_fields, (
                f"Mismatch for {model_class.__name__}: inspector={inspector_fields}, repo={repo_fields}"
            )

    def test_field_detection_edge_cases_integration(self, mock_connection):
        """Test edge cases across both TypeInspector and BaseRepository."""

        class EdgeCaseModel(BaseModel):
            # Mix of complex types
            id: UUID
            name: str
            complex_union: dict[str, Any] | list[str] | int
            nested_optional: list[dict[str, str | None]] | None = None
            generic_dict: dict[str, str | int | list[str]]
            empty_containers: list[Any]

        # TypeInspector detection
        inspector_fields = TypeInspector.detect_json_fields(EdgeCaseModel)
        expected_fields = {"complex_union", "nested_optional", "generic_dict", "empty_containers"}
        assert inspector_fields == expected_fields

        # BaseRepository detection
        repo = BaseRepository(
            db_connection=mock_connection, table_name="edge_case_table", model_class=EdgeCaseModel, primary_key="id"
        )
        assert repo.json_fields == expected_fields

        # Consistency check
        assert inspector_fields == repo.json_fields
