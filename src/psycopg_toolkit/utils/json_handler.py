"""JSON handling utilities for JSONB field support."""

import json
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for common Python types.
    
    Handles serialization of UUID, datetime, date, Decimal, set, and Pydantic models
    that are commonly used in applications but not natively JSON serializable.
    """
    
    def default(self, obj: Any) -> Any:
        """Convert objects to JSON-serializable format.
        
        Args:
            obj: The object to serialize
            
        Returns:
            JSON-serializable representation of the object
            
        Raises:
            TypeError: If the object cannot be serialized
        """
        if isinstance(obj, UUID):
            return str(obj)
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, set):
            return list(obj)
        elif hasattr(obj, 'model_dump'):  # Pydantic model
            return obj.model_dump()
        
        # Let the base class handle the error for unsupported types
        return super().default(obj)