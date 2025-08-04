"""Integration tests for JSONB with psycopg JSON adapters (recommended approach)."""

import asyncio
import json
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any

import pytest
from pydantic import BaseModel, Field
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Json, Jsonb
from testcontainers.postgres import PostgresContainer

from psycopg_toolkit import Database, DatabaseSettings


# Test model
class Product(BaseModel):
    """Product model with JSONB fields."""
    id: int
    name: str
    price: Decimal
    specifications: Dict[str, Any]
    categories: List[str]
    metadata: Optional[Dict[str, Any]] = None


@pytest.fixture
async def test_db():
    """Create test database with psycopg JSON adapters enabled."""
    with PostgresContainer("postgres:17") as container:
        settings = DatabaseSettings(
            host=container.get_container_host_ip(),
            port=container.get_exposed_port(5432),
            dbname=container.dbname,
            user=container.username,
            password=container.password,
            enable_json_adapters=True  # Enable psycopg JSON adapters
        )
        
        db = Database(settings)
        await db.init_db()
        
        # Create test schema
        async with db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE products (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        price DECIMAL(10,2) NOT NULL,
                        specifications JSONB NOT NULL,
                        categories JSONB NOT NULL,
                        metadata JSONB
                    )
                """)
                
                # Create indexes
                await cur.execute("CREATE INDEX idx_product_specs ON products USING GIN (specifications)")
                await cur.execute("CREATE INDEX idx_product_categories ON products USING GIN (categories)")
        
        yield db
        
        await db.cleanup()


class TestPsycopgJSONAdapters:
    """Test JSONB operations using psycopg's native JSON adapters."""
    
    @pytest.mark.asyncio
    async def test_jsonb_insert_and_retrieve(self, test_db):
        """Test inserting and retrieving JSONB data with psycopg adapters."""
        async with test_db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                # Insert product with JSONB data
                # psycopg JSON adapters automatically handle dict -> JSONB conversion
                await cur.execute("""
                    INSERT INTO products (name, price, specifications, categories, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING *
                """, [
                    "Laptop",
                    Decimal("1299.99"),
                    Json({  # Use Json wrapper for JSONB columns
                        "cpu": "Intel i7",
                        "ram": 16,
                        "storage": {"ssd": 512, "type": "NVMe"}
                    }),
                    Json(["electronics", "computers", "laptops"]),  # Use Json wrapper
                    Json({"warranty": "2 years", "color": "silver"})
                ])
                
                result = await cur.fetchone()
                
                # psycopg JSON adapters automatically convert JSONB -> dict/list
                assert result["specifications"]["cpu"] == "Intel i7"
                assert result["specifications"]["storage"]["ssd"] == 512
                assert "laptops" in result["categories"]
                assert result["metadata"]["warranty"] == "2 years"
    
    @pytest.mark.asyncio
    async def test_jsonb_complex_structures(self, test_db):
        """Test complex nested JSONB structures."""
        async with test_db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                # Complex nested structure
                complex_specs = {
                    "display": {
                        "size": 15.6,
                        "resolution": {"width": 1920, "height": 1080},
                        "features": ["IPS", "Anti-glare", "Touch"],
                        "color_accuracy": {
                            "srgb": 99.5,
                            "adobe_rgb": 75.2
                        }
                    },
                    "connectivity": {
                        "ports": [
                            {"type": "USB-C", "count": 2, "version": "3.2"},
                            {"type": "USB-A", "count": 3, "version": "3.0"},
                            {"type": "HDMI", "count": 1, "version": "2.1"}
                        ],
                        "wireless": {
                            "wifi": ["802.11ax", "802.11ac", "802.11n"],
                            "bluetooth": "5.2"
                        }
                    },
                    "performance_metrics": {
                        "benchmarks": {
                            "cpu_score": 8500,
                            "gpu_score": 12000,
                            "storage_speed": {"read": 3500, "write": 3000}
                        }
                    }
                }
                
                await cur.execute("""
                    INSERT INTO products (name, price, specifications, categories)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, [
                    "High-End Laptop",
                    Decimal("2499.99"),
                    Json(complex_specs),
                    Json(["premium", "gaming", "workstation"])
                ])
                
                product_id = (await cur.fetchone())["id"]
                
                # Retrieve and verify complex structure
                await cur.execute("SELECT specifications FROM products WHERE id = %s", [product_id])
                result = await cur.fetchone()
                
                specs = result["specifications"]
                assert specs["display"]["resolution"]["width"] == 1920
                assert "Touch" in specs["display"]["features"]
                assert specs["connectivity"]["ports"][0]["type"] == "USB-C"
                assert specs["performance_metrics"]["benchmarks"]["cpu_score"] == 8500
    
    @pytest.mark.asyncio
    async def test_jsonb_querying(self, test_db):
        """Test querying JSONB data using PostgreSQL operators."""
        async with test_db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                # Insert test data
                products = [
                    ("Phone A", 699.99, {"brand": "Apple", "os": "iOS", "ram": 6}, ["phones", "apple"]),
                    ("Phone B", 899.99, {"brand": "Samsung", "os": "Android", "ram": 8}, ["phones", "android"]),
                    ("Phone C", 599.99, {"brand": "Google", "os": "Android", "ram": 8}, ["phones", "android"]),
                ]
                
                for name, price, specs, cats in products:
                    await cur.execute("""
                        INSERT INTO products (name, price, specifications, categories)
                        VALUES (%s, %s, %s, %s)
                    """, [name, price, Json(specs), Json(cats)])
                
                # Query using JSONB operators
                # Find Android phones
                await cur.execute("""
                    SELECT name, specifications
                    FROM products
                    WHERE specifications->>'os' = 'Android'
                """)
                android_phones = await cur.fetchall()
                assert len(android_phones) == 2
                
                # Find phones with 8GB RAM
                await cur.execute("""
                    SELECT name, specifications
                    FROM products
                    WHERE (specifications->>'ram')::int = 8
                """)
                high_ram_phones = await cur.fetchall()
                assert len(high_ram_phones) == 2
                
                # Find products in 'android' category
                await cur.execute("""
                    SELECT name, categories
                    FROM products
                    WHERE categories ? 'android'
                """)
                android_category = await cur.fetchall()
                assert len(android_category) == 2
                
                # Complex query with @> operator
                await cur.execute("""
                    SELECT name
                    FROM products
                    WHERE specifications @> %s::jsonb
                """, [Json({"brand": "Apple"})])  # Use Json wrapper with explicit cast
                apple_products = await cur.fetchall()
                assert len(apple_products) == 1
                assert apple_products[0]["name"] == "Phone A"
    
    @pytest.mark.asyncio
    async def test_jsonb_updates(self, test_db):
        """Test updating JSONB fields."""
        async with test_db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                # Insert initial data
                await cur.execute("""
                    INSERT INTO products (name, price, specifications, categories)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, [
                    "Tablet",
                    Decimal("499.99"),
                    Json({"brand": "Apple", "model": "iPad", "storage": 128}),
                    Json(["tablets", "apple"])
                ])
                
                product_id = (await cur.fetchone())["id"]
                
                # Update JSONB field - add new key
                await cur.execute("""
                    UPDATE products
                    SET specifications = specifications || %s::jsonb
                    WHERE id = %s
                    RETURNING specifications
                """, [
                    Json({"color": "Space Gray", "year": 2024}),
                    product_id
                ])
                
                updated = await cur.fetchone()
                assert updated["specifications"]["color"] == "Space Gray"
                assert updated["specifications"]["year"] == 2024
                assert updated["specifications"]["storage"] == 128  # Original data preserved
                
                # Update nested value using jsonb_set
                await cur.execute("""
                    UPDATE products
                    SET specifications = jsonb_set(
                        specifications,
                        '{storage}',
                        '256'
                    )
                    WHERE id = %s
                    RETURNING specifications
                """, [product_id])
                
                updated = await cur.fetchone()
                assert updated["specifications"]["storage"] == 256
                
                # Add to array in JSONB
                await cur.execute("""
                    UPDATE products
                    SET categories = categories || %s::jsonb
                    WHERE id = %s
                    RETURNING categories
                """, [
                    json.dumps(["premium"]),  # Need to serialize list to JSON string
                    product_id
                ])
                
                updated = await cur.fetchone()
                assert "premium" in updated["categories"]
    
    @pytest.mark.asyncio
    async def test_jsonb_null_handling(self, test_db):
        """Test handling of NULL values in JSONB."""
        async with test_db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                # Insert with NULL metadata
                await cur.execute("""
                    INSERT INTO products (name, price, specifications, categories, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING *
                """, [
                    "Basic Product",
                    Decimal("99.99"),
                    Json({"basic": True}),
                    Json(["simple"]),
                    None  # NULL JSONB field
                ])
                
                result = await cur.fetchone()
                assert result["metadata"] is None
                
                # Insert with JSONB containing null values
                await cur.execute("""
                    INSERT INTO products (name, price, specifications, categories)
                    VALUES (%s, %s, %s, %s)
                    RETURNING specifications
                """, [
                    "Product with nulls",
                    Decimal("199.99"),
                    Json({"feature1": None, "feature2": "value", "nested": {"inner": None}}),
                    Json([])
                ])
                
                result = await cur.fetchone()
                assert result["specifications"]["feature1"] is None
                assert result["specifications"]["nested"]["inner"] is None
    
    @pytest.mark.asyncio
    async def test_jsonb_special_types(self, test_db):
        """Test JSONB with special Python types using custom encoder."""
        async with test_db.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:
                # Test with datetime, UUID, Decimal in JSONB
                test_uuid = uuid.uuid4()
                test_datetime = datetime.now()
                
                # Note: When using psycopg JSON adapters, we need to ensure
                # special types are JSON-serializable
                metadata = {
                    "uuid": str(test_uuid),  # Convert UUID to string
                    "created_at": test_datetime.isoformat(),  # Convert datetime to ISO format
                    "price_history": [
                        {"date": "2024-01-01", "price": float(Decimal("99.99"))},
                        {"date": "2024-02-01", "price": float(Decimal("89.99"))}
                    ]
                }
                
                await cur.execute("""
                    INSERT INTO products (name, price, specifications, categories, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING metadata
                """, [
                    "Special Types Product",
                    Decimal("99.99"),
                    Json({}),
                    Json([]),
                    Json(metadata)
                ])
                
                result = await cur.fetchone()
                assert result["metadata"]["uuid"] == str(test_uuid)
                assert result["metadata"]["created_at"] == test_datetime.isoformat()
                assert result["metadata"]["price_history"][0]["price"] == 99.99


if __name__ == "__main__":
    pytest.main([__file__, "-v"])