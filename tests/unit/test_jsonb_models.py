"""Unit tests for JSONB test models."""

import pytest
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import sys
import os

# Add the tests directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from models.jsonb_models import (
    UserProfile,
    ProductCatalog, 
    ConfigurationModel,
    SimpleModel,
    BlogPost,
    OrderRecord
)
from psycopg_toolkit.utils.type_inspector import TypeInspector


class TestJSONBModels:
    """Test that JSONB test models are properly configured."""
    
    def test_user_profile_json_detection(self):
        """Test UserProfile JSON field detection."""
        json_fields = TypeInspector.detect_json_fields(UserProfile)
        expected_fields = {
            "metadata", "preferences", "tags", 
            "settings", "custom_fields", "profile_data"
        }
        assert json_fields == expected_fields
    
    def test_product_catalog_json_detection(self):
        """Test ProductCatalog JSON field detection.""" 
        json_fields = TypeInspector.detect_json_fields(ProductCatalog)
        expected_fields = {
            "specifications", "variants", "pricing",
            "manufacturer", "reviews", "additional_info",
            "compatibility", "marketing_data"
        }
        assert json_fields == expected_fields
    
    def test_configuration_model_json_detection(self):
        """Test ConfigurationModel JSON field detection."""
        json_fields = TypeInspector.detect_json_fields(ConfigurationModel)
        expected_fields = {
            "empty_dict", "empty_list", "nested_optional",
            "flexible_field", "multi_union", "timestamp_data",
            "uuid_mapping", "decimal_values", "deep_nested",
            "complex_list", "feature_flags", "environment_vars",
            "service_endpoints"
        }
        assert json_fields == expected_fields
    
    def test_simple_model_no_json_detection(self):
        """Test SimpleModel has no JSON fields detected."""
        json_fields = TypeInspector.detect_json_fields(SimpleModel)
        assert json_fields == set()
    
    def test_blog_post_json_detection(self):
        """Test BlogPost JSON field detection."""
        json_fields = TypeInspector.detect_json_fields(BlogPost)
        expected_fields = {
            "content", "metadata", "tags", 
            "settings", "custom_data", "social_data"
        }
        assert json_fields == expected_fields
    
    def test_order_record_json_detection(self):
        """Test OrderRecord JSON field detection."""
        json_fields = TypeInspector.detect_json_fields(OrderRecord)
        expected_fields = {
            "items", "shipping_info", "payment_info",
            "audit_trail", "tracking_data", "promotions",
            "custom_attributes", "external_references", "summary_data"
        }
        assert json_fields == expected_fields
    
    def test_user_profile_creation(self):
        """Test UserProfile model creation with JSON data."""
        user = UserProfile(
            username="testuser",
            email="test@example.com",
            metadata={"role": "admin", "department": "IT"},
            preferences={"theme": "dark", "language": "en"},
            tags=["developer", "senior"],
            profile_data={
                "bio": "Software developer",
                "skills": ["Python", "PostgreSQL"],
                "experience": 5,
                "certifications": {
                    "aws": "certified",
                    "kubernetes": "learning"
                }
            }
        )
        
        assert user.username == "testuser"
        assert user.metadata["role"] == "admin"
        assert "developer" in user.tags
        assert user.profile_data["experience"] == 5
        assert isinstance(user.id, type(uuid4()))
    
    def test_product_catalog_creation(self):
        """Test ProductCatalog model creation with complex JSON data."""
        product = ProductCatalog(
            id=1,
            name="Gaming Laptop",
            category="Electronics", 
            sku="GL-001",
            specifications={
                "processor": {
                    "brand": "Intel",
                    "model": "i7-12700H",
                    "cores": 14
                },
                "memory": {"size": "32 GB", "type": "DDR5"},
                "storage": [
                    {"type": "SSD", "capacity": "1 TB"},
                    {"type": "HDD", "capacity": "2 TB"}
                ]
            },
            variants=[
                {
                    "name": "Standard",
                    "price": Decimal("1599.99"),
                    "availability": "in_stock"
                }
            ],
            pricing={
                "base_price": Decimal("1599.99"),
                "currency": "USD",
                "discounts": ["student_10", "bulk_5"]
            },
            manufacturer={
                "name": "TechCorp",
                "contact": {"email": "support@techcorp.com"}
            },
            reviews=[
                {
                    "user": "tech_reviewer",
                    "rating": 4,
                    "comment": "Great performance",
                    "date": datetime.now(),
                    "verified": True
                }
            ],
            marketing_data={
                "keywords": ["gaming", "laptop", "performance"],
                "campaigns": {"summer_sale": {"active": True, "discount": 10}}
            }
        )
        
        assert product.name == "Gaming Laptop"
        assert product.specifications["processor"]["cores"] == 14
        assert len(product.variants) == 1
        assert product.pricing["base_price"] == Decimal("1599.99")
        assert product.manufacturer["name"] == "TechCorp"
        assert len(product.reviews) == 1
    
    def test_configuration_model_edge_cases(self):
        """Test ConfigurationModel with edge case data."""
        config = ConfigurationModel(
            name="test_config",
            flexible_field={"key": "dict_value"},
            multi_union={"numbers": [1, 2, 3]},
            timestamp_data={"created": datetime.now()},
            uuid_mapping={"primary": uuid4()},
            decimal_values=[Decimal("1.23"), Decimal("4.56")],
            deep_nested={
                "level1": {
                    "level2": {
                        "level3": [
                            "string_value",
                            42,
                            {"nested": "dict"}
                        ]
                    }
                }
            },
            complex_list=[
                {"type": "config", "values": ["a", "b"]},
                {"type": "settings", "data": {"enabled": True}}
            ],
            feature_flags={"new_ui": True, "beta_features": False},
            environment_vars={"API_URL": "https://api.example.com"},
            service_endpoints=[
                {"name": "auth", "url": "https://auth.service", "enabled": True}
            ]
        )
        
        assert config.name == "test_config"
        assert isinstance(config.flexible_field, dict)
        assert config.flexible_field["key"] == "dict_value"
        assert len(config.decimal_values) == 2
        assert config.feature_flags["new_ui"] is True
        assert len(config.service_endpoints) == 1
    
    def test_simple_model_creation(self):
        """Test SimpleModel creation (no JSON fields)."""
        simple = SimpleModel(
            name="simple_test",
            value=42
        )
        
        assert simple.name == "simple_test"
        assert simple.value == 42
        assert simple.is_active is True
        assert isinstance(simple.id, type(uuid4()))
    
    def test_blog_post_creation(self):
        """Test BlogPost model creation with rich content."""
        post = BlogPost(
            title="Test Blog Post",
            slug="test-blog-post",
            author_id=uuid4(),
            content={
                "blocks": [
                    {"type": "heading", "text": "Introduction"},
                    {"type": "paragraph", "text": "This is test content"},
                    {"type": "image", "src": "/images/test.jpg"}
                ],
                "word_count": 150,
                "reading_time": 2
            },
            metadata={
                "seo": {
                    "title": "Test Blog Post - My Blog",
                    "description": "A test blog post",
                    "keywords": ["test", "blog", "content"]
                },
                "publishing": {
                    "featured": True,
                    "category": "Technology"
                }
            },
            tags=["test", "technology", "blog"],
            social_data={
                "shares": {"twitter": 5, "facebook": 2},
                "engagement": {"likes": 10, "comments": 3}
            }
        )
        
        assert post.title == "Test Blog Post"
        assert len(post.content["blocks"]) == 3
        assert post.metadata["seo"]["title"] == "Test Blog Post - My Blog"
        assert "test" in post.tags
        assert post.social_data["shares"]["twitter"] == 5
    
    def test_order_record_creation(self):
        """Test OrderRecord model creation with complex transactional data."""
        order = OrderRecord(
            order_number="ORD-2024-001",
            customer_id=uuid4(),
            total_amount=Decimal("299.99"),
            items=[
                {
                    "product_id": "PROD-001",
                    "name": "Test Product",
                    "quantity": 2,
                    "price": Decimal("149.99"),
                    "attributes": {"color": "blue", "size": "large"}
                }
            ],
            shipping_info={
                "method": "standard",
                "address": {
                    "street": "123 Test St",
                    "city": "Test City",
                    "country": "US"
                },
                "tracking": ["TRACK123"]
            },
            payment_info={
                "method": "credit_card",
                "last_four": "1234",
                "authorized": True,
                "transaction_id": "TXN-456"
            },
            audit_trail=[
                {
                    "action": "created",
                    "timestamp": datetime.now(),
                    "user": "system",
                    "details": {"source": "web"}
                }
            ],
            tracking_data={
                "events": [
                    {"status": "created", "timestamp": datetime.now()}
                ]
            },
            external_references={
                "payment_gateway": "stripe_pi_123",
                "shipping_carrier": {"carrier": "ups", "tracking": "1Z123"}
            },
            summary_data={
                "item_count": 2,
                "total_weight": Decimal("2.5"),
                "categories": ["electronics"],
                "taxes": {"total": Decimal("24.00"), "rate": 0.08}
            }
        )
        
        assert order.order_number == "ORD-2024-001"
        assert order.total_amount == Decimal("299.99")
        assert len(order.items) == 1
        assert order.items[0]["quantity"] == 2
        assert order.shipping_info["method"] == "standard"
        assert order.payment_info["authorized"] is True
        assert len(order.audit_trail) == 1
        assert order.summary_data["item_count"] == 2