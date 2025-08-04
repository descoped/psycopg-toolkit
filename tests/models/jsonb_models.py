"""Test models with various JSONB field configurations."""

from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    """User profile model with various JSON field types.
    
    This model represents a typical user profile with both regular fields
    and JSON fields for flexible data storage. Used to test basic JSONB
    functionality and auto-detection.
    """
    id: UUID = Field(default_factory=uuid4)
    username: str
    email: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    
    # Basic JSONB fields - should be auto-detected
    metadata: Dict[str, Any]
    preferences: Dict[str, str]
    tags: List[str]
    
    # Optional JSONB fields - should be auto-detected
    settings: Optional[Dict[str, Any]] = None
    custom_fields: Optional[List[Dict[str, str]]] = None
    
    # Complex nested structure - should be auto-detected
    profile_data: Dict[str, Union[str, int, List[str], Dict[str, Any]]]
    
    # Non-JSON optional fields - should NOT be auto-detected
    last_login: Optional[datetime] = None
    login_count: Optional[int] = 0


class ProductCatalog(BaseModel):
    """Product catalog model with complex JSONB specifications.
    
    This model represents a product with complex nested JSON structures
    including specifications, variants, pricing, and reviews. Used to test
    complex nested JSONB handling and serialization of special types.
    """
    id: int
    name: str
    category: str
    sku: str
    is_available: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    
    # Complex JSONB fields with nested structures
    specifications: Dict[str, Any]
    variants: List[Dict[str, Any]]
    pricing: Dict[str, Union[Decimal, str, List[str]]]
    
    # Nested object structures with mixed types
    manufacturer: Dict[str, Union[str, Dict[str, str]]]
    reviews: List[Dict[str, Union[str, int, datetime, bool]]]
    
    # Optional complex JSONB fields
    additional_info: Optional[Dict[str, Any]] = None
    compatibility: Optional[List[Dict[str, Union[str, bool]]]] = None
    
    # Marketing data with various types
    marketing_data: Dict[str, Any]


class ConfigurationModel(BaseModel):
    """Model for testing edge cases and various JSON field types.
    
    This model includes edge cases, empty collections, deeply nested
    structures, and various Union types to test the robustness of
    JSON field detection and handling.
    """
    id: UUID = Field(default_factory=uuid4)
    name: str
    version: str = "1.0"
    
    # Edge case fields
    empty_dict: Dict[str, Any] = Field(default_factory=dict)
    empty_list: List[Any] = Field(default_factory=list)
    nested_optional: Optional[Dict[str, Optional[List[str]]]] = None
    
    # Mixed type unions - should be auto-detected
    flexible_field: Union[str, Dict[str, Any], List[str]]
    multi_union: Union[int, List[str], Dict[str, Any]]
    
    # Custom serializable objects in JSONB
    timestamp_data: Dict[str, datetime]
    uuid_mapping: Dict[str, UUID]
    decimal_values: List[Decimal]
    
    # Deeply nested structures
    deep_nested: Dict[str, Dict[str, Dict[str, List[Union[str, int, Dict[str, Any]]]]]]
    
    # Collections of complex types
    complex_list: List[Dict[str, Union[str, List[str], Dict[str, Any]]]]
    
    # Configuration-specific fields
    feature_flags: Dict[str, bool]
    environment_vars: Dict[str, str]
    service_endpoints: List[Dict[str, Union[str, int, bool]]]


class SimpleModel(BaseModel):
    """Simple model without JSON fields for comparison testing.
    
    This model contains only basic types and is used as a control
    in performance tests and to verify that models without JSON
    fields are not affected by JSONB processing.
    """
    id: UUID = Field(default_factory=uuid4)
    name: str
    value: int
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    description: Optional[str] = None
    score: Optional[float] = None


class BlogPost(BaseModel):
    """Blog post model with rich content stored as JSONB.
    
    This model represents a blog post with rich content blocks,
    SEO metadata, and publishing information stored as JSON.
    Used to test real-world scenarios with content management.
    """
    id: UUID = Field(default_factory=uuid4)
    title: str
    slug: str
    author_id: UUID
    status: str = "draft"  # draft, published, archived
    created_at: datetime = Field(default_factory=datetime.now)
    published_at: Optional[datetime] = None
    
    # Rich content stored as JSONB
    content: Dict[str, Any]  # Content blocks, images, formatting
    metadata: Dict[str, Any]  # SEO, publishing info, analytics
    tags: List[str]
    
    # Optional JSONB fields
    settings: Optional[Dict[str, Any]] = None  # Visibility, comments, etc.
    custom_data: Optional[Dict[str, Any]] = None
    
    # Social and engagement data
    social_data: Dict[str, Union[str, int, List[str], Dict[str, Any]]]


class OrderRecord(BaseModel):
    """Order record model with complex transactional data.
    
    This model represents an e-commerce order with items, shipping,
    payment information, and audit trails stored as JSONB.
    Used to test transactional scenarios and data integrity.
    """
    id: UUID = Field(default_factory=uuid4)
    order_number: str
    customer_id: UUID
    status: str = "pending"  # pending, processing, shipped, delivered, cancelled
    total_amount: Decimal
    currency: str = "USD"
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Order details as JSONB
    items: List[Dict[str, Union[str, int, Decimal, Dict[str, Any]]]]
    shipping_info: Dict[str, Union[str, Dict[str, str], List[str]]]
    payment_info: Dict[str, Union[str, Decimal, bool, Dict[str, Any]]]
    
    # Audit and tracking information
    audit_trail: List[Dict[str, Union[str, datetime, Dict[str, Any]]]]
    tracking_data: Dict[str, Union[str, List[Dict[str, Union[str, datetime]]]]]
    
    # Optional business data
    promotions: Optional[List[Dict[str, Union[str, Decimal, datetime]]]] = None
    custom_attributes: Optional[Dict[str, Any]] = None
    
    # Integration data for external systems
    external_references: Dict[str, Union[str, Dict[str, str]]]
    
    # Calculated fields that might be stored as JSONB for performance
    summary_data: Dict[str, Any]