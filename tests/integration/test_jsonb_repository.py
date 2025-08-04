"""Integration tests for JSONB repository operations."""

import asyncio
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Dict, List, Optional, Any, Union

import pytest
from pydantic import BaseModel, Field
from testcontainers.postgres import PostgresContainer
from psycopg.types.json import Json

from psycopg_toolkit import (
    Database,
    DatabaseSettings,
    BaseRepository,
    JSONSerializationError,
    JSONDeserializationError,
    RecordNotFoundError,
    OperationError
)


# Test Models with various JSONB field configurations
class UserProfile(BaseModel):
    """User profile with multiple JSONB field types."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    username: str
    email: str
    
    # JSONB fields
    metadata: Dict[str, Any]
    preferences: Dict[str, str]
    tags: List[str]
    profile_data: Optional[Dict[str, Any]] = None
    
    # Non-JSON fields
    created_at: datetime = Field(default_factory=datetime.now)
    is_active: bool = True
    age: Optional[int] = None


class ProductCatalog(BaseModel):
    """Product with complex nested JSONB structures."""
    id: int
    name: str
    price: Decimal
    
    # Complex JSONB fields
    specifications: Dict[str, Union[str, int, float, Dict[str, Any], List[Any]]]
    categories: List[str]
    inventory: Dict[str, Dict[str, Union[int, str]]]
    reviews: List[Dict[str, Any]]
    
    # Non-JSON fields
    sku: str
    in_stock: bool = True


class ConfigurationModel(BaseModel):
    """Configuration with edge case JSONB fields."""
    id: int
    name: str
    
    # Edge case JSONB fields
    settings: Dict[str, Any]  # Can contain deeply nested structures
    feature_flags: Dict[str, bool]
    allowed_values: List[Union[str, int, float, None]]
    metadata: Optional[Dict[str, Optional[str]]] = None
    
    # Test empty collections
    empty_dict: Dict[str, Any] = Field(default_factory=dict)
    empty_list: List[Any] = Field(default_factory=list)


# Repository implementations
class UserRepository(BaseRepository[UserProfile, uuid.UUID]):
    """Repository for UserProfile with psycopg JSON adapters."""
    
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="user_profiles",
            model_class=UserProfile,
            primary_key="id",
            # Disable custom JSON processing - let psycopg handle it
            auto_detect_json=False
        )


class ProductRepository(BaseRepository[ProductCatalog, int]):
    """Repository for ProductCatalog with psycopg JSON adapters."""
    
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="products",
            model_class=ProductCatalog,
            primary_key="id",
            # Disable custom JSON processing - let psycopg handle it
            auto_detect_json=False
        )


class ConfigRepository(BaseRepository[ConfigurationModel, int]):
    """Repository for ConfigurationModel with psycopg JSON adapters."""
    
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="configurations",
            model_class=ConfigurationModel,
            primary_key="id",
            # Disable custom JSON processing - let psycopg handle it
            auto_detect_json=False
        )


@pytest.fixture
async def test_db():
    """Create test database with JSONB tables."""
    with PostgresContainer("postgres:17") as container:
        settings = DatabaseSettings(
            host=container.get_container_host_ip(),
            port=container.get_exposed_port(5432),
            dbname=container.dbname,
            user=container.username,
            password=container.password,
            # Enable psycopg JSON adapters (recommended approach)
            enable_json_adapters=True
        )
        
        db = Database(settings)
        await db.init_db()
        
        # Create test schema
        async with db.connection() as conn:
            async with conn.cursor() as cur:
                # User profiles table
                await cur.execute("""
                    CREATE TABLE user_profiles (
                        id UUID PRIMARY KEY,
                        username VARCHAR(100) NOT NULL,
                        email VARCHAR(255) NOT NULL,
                        metadata JSONB NOT NULL,
                        preferences JSONB NOT NULL,
                        tags JSONB NOT NULL,
                        profile_data JSONB,
                        created_at TIMESTAMP NOT NULL,
                        is_active BOOLEAN NOT NULL,
                        age INTEGER
                    )
                """)
                
                # Products table
                await cur.execute("""
                    CREATE TABLE products (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        price DECIMAL(10,2) NOT NULL,
                        specifications JSONB NOT NULL,
                        categories JSONB NOT NULL,
                        inventory JSONB NOT NULL,
                        reviews JSONB NOT NULL,
                        sku VARCHAR(50) NOT NULL,
                        in_stock BOOLEAN NOT NULL
                    )
                """)
                
                # Configurations table
                await cur.execute("""
                    CREATE TABLE configurations (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        settings JSONB NOT NULL,
                        feature_flags JSONB NOT NULL,
                        allowed_values JSONB NOT NULL,
                        metadata JSONB,
                        empty_dict JSONB NOT NULL,
                        empty_list JSONB NOT NULL
                    )
                """)
                
                # Create indexes for better performance
                await cur.execute("CREATE INDEX idx_user_metadata ON user_profiles USING GIN (metadata)")
                await cur.execute("CREATE INDEX idx_user_tags ON user_profiles USING GIN (tags)")
                await cur.execute("CREATE INDEX idx_product_categories ON products USING GIN (categories)")
                await cur.execute("CREATE INDEX idx_config_settings ON configurations USING GIN (settings)")
        
        yield db
        
        await db.cleanup()


@pytest.fixture
async def test_db_with_adapters():
    """Create test database with psycopg JSON adapters enabled."""
    with PostgresContainer("postgres:17") as container:
        settings = DatabaseSettings(
            host=container.get_container_host_ip(),
            port=container.get_exposed_port(5432),
            dbname=container.dbname,
            user=container.username,
            password=container.password,
            # Enable psycopg JSON adapters
            enable_json_adapters=True
        )
        
        db = Database(settings)
        await db.init_db()
        
        # Create minimal schema for adapter testing
        async with db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE user_profiles (
                        id UUID PRIMARY KEY,
                        username VARCHAR(100) NOT NULL,
                        email VARCHAR(255) NOT NULL,
                        metadata JSONB NOT NULL,
                        preferences JSONB NOT NULL,
                        tags JSONB NOT NULL,
                        profile_data JSONB,
                        created_at TIMESTAMP NOT NULL,
                        is_active BOOLEAN NOT NULL,
                        age INTEGER
                    )
                """)
        
        yield db
        
        await db.cleanup()


class TestUserProfileCRUD:
    """Test CRUD operations with UserProfile JSONB fields."""
    
    @pytest.mark.asyncio
    async def test_create_user_with_jsonb_fields(self, test_db):
        """Test creating user with various JSONB field types."""
        async with test_db.connection() as conn:
            repo = UserRepository(conn)
            
            # Create user with complex JSON data
            user_data = UserProfile(
                username="test_user",
                email="test@example.com",
                metadata={
                    "created_from": "integration_test",
                    "timestamp": datetime.now().isoformat(),
                    "nested": {
                        "level1": {
                            "level2": ["value1", "value2"],
                            "number": 42
                        }
                    },
                    "mixed_types": [1, "string", True, None, {"key": "value"}]
                },
                preferences={
                    "theme": "dark",
                    "language": "en",
                    "notifications": "enabled"
                },
                tags=["premium", "beta_tester", "verified"],
                profile_data={
                    "bio": "Test user bio",
                    "links": ["https://example.com", "https://github.com/test"],
                    "stats": {
                        "posts": 10,
                        "followers": 100,
                        "following": 50
                    }
                }
            )
            
            # Create and verify
            created_user = await repo.create(user_data)
            
            assert created_user.id is not None
            assert created_user.username == "test_user"
            assert created_user.metadata["created_from"] == "integration_test"
            assert created_user.metadata["nested"]["level1"]["number"] == 42
            assert created_user.preferences["theme"] == "dark"
            assert "premium" in created_user.tags
            assert created_user.profile_data["stats"]["followers"] == 100
    
    @pytest.mark.asyncio
    async def test_get_by_id_with_jsonb_deserialization(self, test_db):
        """Test retrieving user deserializes JSONB fields correctly."""
        async with test_db.connection() as conn:
            repo = UserRepository(conn)
            
            # Create user
            user = UserProfile(
                username="retrieve_test",
                email="retrieve@test.com",
                metadata={
                    "uuid_field": str(uuid.uuid4()),
                    "date_field": date.today().isoformat(),
                    "decimal_field": float(Decimal("123.45"))
                },
                preferences={"key1": "value1", "key2": "value2"},
                tags=["tag1", "tag2", "tag3"]
            )
            
            created = await repo.create(user)
            
            # Retrieve and verify
            retrieved = await repo.get_by_id(created.id)
            
            assert retrieved.id == created.id
            assert retrieved.metadata["uuid_field"] == user.metadata["uuid_field"]
            assert retrieved.metadata["decimal_field"] == 123.45
            assert len(retrieved.tags) == 3
            assert retrieved.preferences == user.preferences
    
    @pytest.mark.asyncio
    async def test_update_jsonb_fields(self, test_db):
        """Test updating JSONB fields."""
        async with test_db.connection() as conn:
            repo = UserRepository(conn)
            
            # Create initial user
            user = UserProfile(
                username="update_test",
                email="update@test.com",
                metadata={"version": 1, "data": "initial"},
                preferences={"theme": "light"},
                tags=["initial"]
            )
            
            created = await repo.create(user)
            
            # Update JSONB fields
            updates = {
                "metadata": {
                    "version": 2,
                    "data": "updated",
                    "new_field": "added"
                },
                "preferences": {
                    "theme": "dark",
                    "language": "es",
                    "new_pref": "value"
                },
                "tags": ["updated", "modified", "new"],
                "profile_data": {
                    "updated_at": datetime.now().isoformat()
                }
            }
            
            updated = await repo.update(created.id, updates)
            
            assert updated.metadata["version"] == 2
            assert updated.metadata["new_field"] == "added"
            assert updated.preferences["theme"] == "dark"
            assert "updated" in updated.tags
            assert updated.profile_data is not None
            assert "updated_at" in updated.profile_data
    
    @pytest.mark.asyncio
    async def test_get_all_with_multiple_jsonb_records(self, test_db):
        """Test retrieving multiple records with JSONB fields."""
        async with test_db.connection() as conn:
            repo = UserRepository(conn)
            
            # Create multiple users
            users = []
            for i in range(5):
                user = UserProfile(
                    username=f"user_{i}",
                    email=f"user_{i}@test.com",
                    metadata={"index": i, "type": "test"},
                    preferences={"pref": f"value_{i}"},
                    tags=[f"tag_{i}", "common"]
                )
                users.append(await repo.create(user))
            
            # Get all and verify
            all_users = await repo.get_all()
            
            assert len(all_users) >= 5
            
            # Verify JSONB fields are properly deserialized
            for user in all_users:
                if user.username.startswith("user_"):
                    assert isinstance(user.metadata, dict)
                    assert isinstance(user.preferences, dict)
                    assert isinstance(user.tags, list)
                    assert "common" in user.tags
    
    @pytest.mark.asyncio
    async def test_create_bulk_with_jsonb_fields(self, test_db):
        """Test bulk creation with JSONB fields."""
        async with test_db.connection() as conn:
            repo = UserRepository(conn)
            
            # Create multiple users with varying JSONB data
            users_data = []
            for i in range(10):
                user = UserProfile(
                    username=f"bulk_user_{i}",
                    email=f"bulk_{i}@test.com",
                    metadata={
                        "batch": "test_bulk",
                        "index": i,
                        "nested": {"value": i * 10}
                    },
                    preferences={
                        "setting1": f"value_{i}",
                        "setting2": str(i % 2 == 0)
                    },
                    tags=[f"bulk", f"batch_{i // 3}"],
                    profile_data={"score": i * 100} if i % 2 == 0 else None
                )
                users_data.append(user)
            
            # Bulk create
            created_users = await repo.create_bulk(users_data, batch_size=5)
            
            assert len(created_users) == 10
            
            # Verify JSONB fields
            for i, user in enumerate(created_users):
                assert user.metadata["index"] == i
                assert user.metadata["nested"]["value"] == i * 10
                assert f"batch_{i // 3}" in user.tags
                if i % 2 == 0:
                    assert user.profile_data["score"] == i * 100


class TestProductCatalogCRUD:
    """Test CRUD operations with complex nested JSONB structures."""
    
    @pytest.mark.asyncio
    async def test_create_product_with_complex_jsonb(self, test_db):
        """Test creating product with complex nested JSONB."""
        async with test_db.connection() as conn:
            repo = ProductRepository(conn)
            
            # Create product with complex specifications
            product = ProductCatalog(
                id=1,
                name="Advanced Laptop",
                price=Decimal("1999.99"),
                specifications={
                    "processor": {
                        "brand": "Intel",
                        "model": "i9-12900K",
                        "cores": 16,
                        "frequency": 3.2,
                        "cache": {
                            "l1": "1.25MB",
                            "l2": "14MB", 
                            "l3": "30MB"
                        }
                    },
                    "memory": {
                        "size": 32,
                        "type": "DDR5",
                        "speed": 4800,
                        "modules": [
                            {"size": 16, "manufacturer": "Corsair"},
                            {"size": 16, "manufacturer": "Corsair"}
                        ]
                    },
                    "features": ["WiFi 6E", "Bluetooth 5.2", "Thunderbolt 4"],
                    "dimensions": {
                        "width": 35.5,
                        "depth": 25.0,
                        "height": 1.8,
                        "weight": 2.1
                    }
                },
                categories=["laptops", "gaming", "high-performance"],
                inventory={
                    "warehouse_a": {"stock": 50, "location": "A1-B2"},
                    "warehouse_b": {"stock": 30, "location": "C3-D4"},
                    "warehouse_c": {"stock": 0, "location": "E5-F6"}
                },
                reviews=[
                    {
                        "user": "john_doe",
                        "rating": 5,
                        "comment": "Excellent performance!",
                        "date": "2024-01-15",
                        "helpful": 25
                    },
                    {
                        "user": "jane_smith",
                        "rating": 4,
                        "comment": "Great but expensive",
                        "date": "2024-01-20",
                        "helpful": 15
                    }
                ],
                sku="LAP-ADV-001"
            )
            
            created = await repo.create(product)
            
            assert created.id == 1
            assert created.specifications["processor"]["cores"] == 16
            assert created.specifications["memory"]["modules"][0]["manufacturer"] == "Corsair"
            assert "gaming" in created.categories
            assert created.inventory["warehouse_a"]["stock"] == 50
            assert len(created.reviews) == 2
            assert created.reviews[0]["rating"] == 5
    
    @pytest.mark.asyncio
    async def test_update_nested_jsonb_structures(self, test_db):
        """Test updating deeply nested JSONB structures."""
        async with test_db.connection() as conn:
            repo = ProductRepository(conn)
            
            # Create initial product
            product = ProductCatalog(
                id=2,
                name="Basic Laptop",
                price=Decimal("999.99"),
                specifications={"cpu": "i5", "ram": 8},
                categories=["laptops"],
                inventory={"main": {"stock": 10, "location": "A1"}},
                reviews=[],
                sku="LAP-BAS-001"
            )
            
            created = await repo.create(product)
            
            # Update with more complex structure
            updates = {
                "specifications": {
                    "cpu": {
                        "brand": "Intel",
                        "model": "i7-12700K",
                        "details": {
                            "cores": 12,
                            "threads": 20,
                            "tdp": 125
                        }
                    },
                    "ram": {
                        "size": 16,
                        "type": "DDR4"
                    },
                    "storage": [
                        {"type": "SSD", "size": 512},
                        {"type": "HDD", "size": 1000}
                    ]
                },
                "reviews": [
                    {
                        "user": "reviewer1",
                        "rating": 4,
                        "pros": ["Fast", "Reliable"],
                        "cons": ["Loud fan"]
                    }
                ]
            }
            
            updated = await repo.update(created.id, updates)
            
            assert updated.specifications["cpu"]["details"]["cores"] == 12
            assert len(updated.specifications["storage"]) == 2
            assert updated.reviews[0]["pros"][0] == "Fast"


class TestConfigurationEdgeCases:
    """Test edge cases with JSONB fields."""
    
    @pytest.mark.asyncio
    async def test_empty_jsonb_collections(self, test_db):
        """Test handling empty JSONB collections."""
        async with test_db.connection() as conn:
            repo = ConfigRepository(conn)
            
            config = ConfigurationModel(
                id=1,
                name="empty_test",
                settings={},
                feature_flags={},
                allowed_values=[],
                metadata=None,
                empty_dict={},
                empty_list=[]
            )
            
            created = await repo.create(config)
            retrieved = await repo.get_by_id(1)
            
            assert retrieved.settings == {}
            assert retrieved.feature_flags == {}
            assert retrieved.allowed_values == []
            assert retrieved.metadata is None
            assert retrieved.empty_dict == {}
            assert retrieved.empty_list == []
    
    @pytest.mark.asyncio
    async def test_deeply_nested_jsonb_structures(self, test_db):
        """Test very deeply nested JSONB structures."""
        async with test_db.connection() as conn:
            repo = ConfigRepository(conn)
            
            # Create deeply nested structure
            deep_nested = {"level1": {}}
            current = deep_nested["level1"]
            for i in range(2, 11):  # 10 levels deep
                current[f"level{i}"] = {}
                current = current[f"level{i}"]
            current["value"] = "deep_value"
            
            config = ConfigurationModel(
                id=2,
                name="deep_nested",
                settings=deep_nested,
                feature_flags={"deep_test": True},
                allowed_values=[1, 2, 3]
            )
            
            created = await repo.create(config)
            retrieved = await repo.get_by_id(2)
            
            # Navigate to deepest level
            current = retrieved.settings["level1"]
            for i in range(2, 11):
                current = current[f"level{i}"]
            
            assert current["value"] == "deep_value"
    
    @pytest.mark.asyncio
    async def test_null_values_in_jsonb(self, test_db):
        """Test handling null values within JSONB."""
        async with test_db.connection() as conn:
            repo = ConfigRepository(conn)
            
            config = ConfigurationModel(
                id=3,
                name="null_test",
                settings={
                    "key1": None,
                    "key2": "value",
                    "nested": {
                        "null_field": None,
                        "array_with_nulls": [1, None, 3, None, 5]
                    }
                },
                feature_flags={"flag1": True, "flag2": False},
                allowed_values=[None, "string", 123, None],
                metadata={"field1": None, "field2": "value"}
            )
            
            created = await repo.create(config)
            retrieved = await repo.get_by_id(3)
            
            assert retrieved.settings["key1"] is None
            assert retrieved.settings["nested"]["null_field"] is None
            assert retrieved.settings["nested"]["array_with_nulls"][1] is None
            assert retrieved.allowed_values[0] is None
            assert retrieved.metadata["field1"] is None
    
    @pytest.mark.asyncio
    async def test_special_characters_in_jsonb(self, test_db):
        """Test JSONB with special characters and unicode."""
        async with test_db.connection() as conn:
            repo = ConfigRepository(conn)
            
            config = ConfigurationModel(
                id=4,
                name="special_chars",
                settings={
                    "unicode": "Hello 世界 🌍",
                    "quotes": 'He said "Hello"',
                    "backslash": "path\\to\\file",
                    "newline": "line1\nline2",
                    "tab": "col1\tcol2",
                    "emoji": "😀🎉🚀"
                },
                feature_flags={"unicode_test": True},
                allowed_values=["café", "naïve", "résumé"]
            )
            
            created = await repo.create(config)
            retrieved = await repo.get_by_id(4)
            
            assert retrieved.settings["unicode"] == "Hello 世界 🌍"
            assert retrieved.settings["quotes"] == 'He said "Hello"'
            assert retrieved.settings["emoji"] == "😀🎉🚀"
            assert "café" in retrieved.allowed_values


class TestJSONBWithPsycopgAdapters:
    """Test JSONB operations with psycopg JSON adapters enabled."""
    
    @pytest.mark.asyncio
    async def test_jsonb_with_adapters_enabled(self, test_db_with_adapters):
        """Test that psycopg adapters work correctly."""
        async with test_db_with_adapters.connection() as conn:
            # Use repository without custom JSON processing
            repo = BaseRepository[UserProfile, uuid.UUID](
                db_connection=conn,
                table_name="user_profiles",
                model_class=UserProfile,
                primary_key="id",
                auto_detect_json=False  # Let psycopg handle JSON
            )
            
            # Create user
            user = UserProfile(
                username="adapter_test",
                email="adapter@test.com",
                metadata={"test": "psycopg_adapters"},
                preferences={"adapter": "enabled"},
                tags=["psycopg", "adapter"]
            )
            
            created = await repo.create(user)
            retrieved = await repo.get_by_id(created.id)
            
            assert retrieved.metadata["test"] == "psycopg_adapters"
            assert retrieved.preferences["adapter"] == "enabled"
            assert "psycopg" in retrieved.tags


class TestJSONBErrorHandling:
    """Test JSON-specific error handling."""
    
    @pytest.mark.asyncio
    async def test_invalid_json_handling(self, test_db):
        """Test handling of invalid JSON data - type mismatch."""
        async with test_db.connection() as conn:
            repo = UserRepository(conn)
            
            # Create a user first
            user = UserProfile(
                username="error_test",
                email="error@test.com",
                metadata={"valid": "data"},
                preferences={"valid": "pref"},
                tags=["valid"]
            )
            created = await repo.create(user)
            
            # PostgreSQL validates JSONB, so we can't insert truly invalid JSON
            # Instead, test with type mismatch - valid JSON but wrong type
            async with conn.cursor() as cur:
                await cur.execute("""
                    UPDATE user_profiles 
                    SET tags = '"not_an_array"'::jsonb 
                    WHERE id = %s
                """, [created.id])
            
            # This should cause an error when trying to construct the model
            # because tags expects a list but gets a string
            with pytest.raises(OperationError):
                await repo.get_by_id(created.id)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])