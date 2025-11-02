"""Type inspection utilities for detecting JSON fields in Pydantic models."""

import logging
import sys
import types
import typing
from typing import Any, Union

from pydantic import BaseModel
from pydantic.fields import FieldInfo

logger = logging.getLogger(__name__)


class TypeInspector:
    """Inspect Pydantic models to detect JSON-serializable fields.

    Analyzes Pydantic model type annotations to automatically identify fields
    that should be treated as JSON/JSONB fields in the database.
    """

    @staticmethod
    def detect_json_fields(model_class: type[BaseModel]) -> set[str]:
        """Detect which fields should be treated as JSON based on type annotations.

        Analyzes the Pydantic model's field annotations to identify fields with
        types that should be stored as JSON/JSONB in the database, such as:
        - Dict[str, Any] and similar dictionary types
        - List[T] and similar list types
        - Optional[Dict[...]] and Optional[List[...]]
        - Union types containing dict or list components

        Args:
            model_class: The Pydantic model class to inspect

        Returns:
            Set of field names that should be treated as JSON fields

        Example:
            >>> class User(BaseModel):
            ...     id: int
            ...     name: str
            ...     metadata: Dict[str, Any]
            ...     tags: List[str]
            >>> TypeInspector.detect_json_fields(User)
            {'metadata', 'tags'}
        """
        json_fields = set()

        try:
            for field_name, field_info in model_class.model_fields.items():
                if TypeInspector._is_json_field(field_info):
                    json_fields.add(field_name)
                    logger.debug(f"Detected JSON field '{field_name}' in {model_class.__name__}")
        except Exception as e:
            logger.warning(f"Error detecting JSON fields in {model_class.__name__}: {e}")

        logger.debug(f"Detected {len(json_fields)} JSON fields in {model_class.__name__}: {json_fields}")
        return json_fields

    @staticmethod
    def detect_vector_fields(model_class: type[BaseModel]) -> set[str]:
        """Detect which fields should be treated as pgvector based on type annotations.

        Analyzes the Pydantic model's field annotations to identify fields with
        list[float] type that should be stored as vector in PostgreSQL using pgvector.

        Args:
            model_class: The Pydantic model class to inspect

        Returns:
            Set of field names that should be treated as vector fields

        Example:
            >>> class Embedding(BaseModel):
            ...     id: int
            ...     vector_data: list[float]
            ...     tags: list[str]  # Not detected - not list[float]
            >>> TypeInspector.detect_vector_fields(Embedding)
            {'vector_data'}
        """
        vector_fields = set()

        try:
            for field_name, field_info in model_class.model_fields.items():
                if TypeInspector._is_vector_field(field_info):
                    vector_fields.add(field_name)
                    logger.debug(f"Detected vector field '{field_name}' in {model_class.__name__}")
        except Exception as e:
            logger.warning(f"Error detecting vector fields in {model_class.__name__}: {e}")

        logger.debug(f"Detected {len(vector_fields)} vector fields in {model_class.__name__}: {vector_fields}")
        return vector_fields

    @staticmethod
    def _is_vector_field(field_info: FieldInfo) -> bool:
        """Check if a field should be treated as vector based on its type annotation.

        Args:
            field_info: Pydantic field information including type annotation

        Returns:
            True if the field should be treated as vector (list[float]), False otherwise
        """
        annotation = field_info.annotation
        return TypeInspector._is_vector_type(annotation)

    @staticmethod
    def _is_vector_type(annotation: Any) -> bool:
        """Check if a type annotation represents a vector type (list[float]).

        Args:
            annotation: Type annotation to analyze

        Returns:
            True if the type is list[float], False otherwise
        """
        if annotation is None:
            return False

        # Check direct list[float]
        if TypeInspector._is_list_of_float(annotation):
            return True

        # Check Union types (e.g., list[float] | None, Optional[list[float]])
        origin = typing.get_origin(annotation)
        if origin is Union or (sys.version_info >= (3, 10) and isinstance(annotation, types.UnionType)):
            args = typing.get_args(annotation)
            # Check if any non-None type in the Union is list[float]
            for arg in args:
                if arg is not type(None) and TypeInspector._is_list_of_float(arg):
                    return True

        return False

    @staticmethod
    def _is_list_of_float(annotation: Any) -> bool:
        """Check if annotation is specifically list[float].

        Args:
            annotation: Type annotation to check

        Returns:
            True if annotation is list[float], False otherwise
        """
        origin = typing.get_origin(annotation)

        # Check for list origin
        if origin is list:
            args = typing.get_args(annotation)
            # Must have exactly one argument and it must be float
            if args and len(args) == 1 and args[0] is float:
                return True

        # Check for legacy typing.List[float]
        if hasattr(annotation, "__origin__") and annotation.__origin__ is list:
            args = getattr(annotation, "__args__", ())
            if args and len(args) == 1 and args[0] is float:
                return True

        return False

    @staticmethod
    def _is_json_field(field_info: FieldInfo) -> bool:
        """Check if a field should be treated as JSON based on its type annotation.

        Args:
            field_info: Pydantic field information including type annotation

        Returns:
            True if the field should be treated as JSON, False otherwise
        """
        annotation = field_info.annotation
        return TypeInspector._is_json_type(annotation)

    @staticmethod
    def _is_json_type(annotation: Any) -> bool:
        """Check if a type annotation represents a JSON-serializable type.

        Recursively analyzes type annotations to determine if they represent
        data structures that should be stored as JSON.

        Args:
            annotation: Type annotation to analyze

        Returns:
            True if the type should be treated as JSON, False otherwise
        """
        if annotation is None:
            return False

        # Check direct origin types
        if TypeInspector._check_origin_type(annotation):
            return True

        # Check Union types
        if TypeInspector._check_union_type(annotation):
            return True

        # Check legacy typing module types
        if TypeInspector._check_legacy_typing(annotation):
            return True

        # Check string annotations
        return bool(TypeInspector._check_string_annotation(annotation))

    @staticmethod
    def _check_origin_type(annotation: Any) -> bool:
        """Check if annotation has dict or list origin."""
        origin = typing.get_origin(annotation)
        return origin in (dict, list)

    @staticmethod
    def _check_union_type(annotation: Any) -> bool:
        """Check Union types for JSON-serializable members."""
        origin = typing.get_origin(annotation)

        # Handle both typing.Union and types.UnionType (Python 3.10+ X | Y syntax)
        if origin is Union or (sys.version_info >= (3, 10) and isinstance(annotation, types.UnionType)):
            args = typing.get_args(annotation)
            # Check if any non-None type in the Union is a JSON type
            for arg in args:
                if arg is not type(None) and TypeInspector._is_json_type(arg):
                    return True
        return False

    @staticmethod
    def _check_legacy_typing(annotation: Any) -> bool:
        """Check for legacy typing module types."""
        # Check for __origin__ attribute (older Python versions)
        if hasattr(annotation, "__origin__"):
            origin = annotation.__origin__
            if origin in (dict, list):
                return True

        # Handle generic aliases like typing.Dict, typing.List
        return bool(hasattr(annotation, "_name") and annotation._name in ("Dict", "List"))

    @staticmethod
    def _check_string_annotation(annotation: Any) -> bool:
        """Check string annotations (forward references)."""
        if isinstance(annotation, str):
            # Simple heuristic for string annotations
            annotation_lower = annotation.lower()
            return any(keyword in annotation_lower for keyword in ["dict", "list"])
        return False

    @staticmethod
    def get_field_types(model_class: type[BaseModel]) -> dict[str, Any]:
        """Get mapping of field names to their type annotations.

        Args:
            model_class: The Pydantic model class to inspect

        Returns:
            Dictionary mapping field names to their type annotations
        """
        try:
            return {field_name: field_info.annotation for field_name, field_info in model_class.model_fields.items()}
        except Exception as e:
            logger.warning(f"Error getting field types for {model_class.__name__}: {e}")
            return {}

    @staticmethod
    def analyze_field_type(annotation: Any) -> dict[str, Any]:
        """Analyze a type annotation and return detailed information.

        Provides detailed analysis of a type annotation for debugging
        and inspection purposes.

        Args:
            annotation: Type annotation to analyze

        Returns:
            Dictionary with analysis results including:
            - is_json: Whether it should be treated as JSON
            - origin: The origin type (dict, list, Union, etc.)
            - args: Type arguments if applicable
            - is_optional: Whether the type is Optional
        """
        analysis = {
            "is_json": False,
            "origin": None,
            "args": None,
            "is_optional": False,
            "annotation_str": str(annotation),
        }

        try:
            analysis["is_json"] = TypeInspector._is_json_type(annotation)
            analysis["origin"] = typing.get_origin(annotation)
            analysis["args"] = typing.get_args(annotation)

            # Check if Optional (Union with None)
            if analysis["origin"] is Union or (sys.version_info >= (3, 10) and isinstance(annotation, types.UnionType)):
                args = analysis["args"]
                analysis["is_optional"] = type(None) in args

        except Exception as e:
            logger.debug(f"Error analyzing type annotation {annotation}: {e}")

        return analysis
