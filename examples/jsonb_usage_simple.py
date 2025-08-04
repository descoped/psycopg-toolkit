"""
Practical JSONB usage example for psycopg-toolkit.

This example demonstrates the most common and reliable JSONB usage patterns:
1. Using psycopg JSON adapters (recommended for production)
2. Working with JSONB data types in PostgreSQL
3. Performing CRUD operations with complex JSON structures
4. Best practices for JSONB field configuration
"""

import asyncio
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field
from testcontainers.postgres import PostgresContainer

from psycopg_toolkit import (
    Database, 
    DatabaseSettings, 
    BaseRepository
)


class UserProfile(BaseModel):
    """User profile with JSONB fields - using psycopg JSON adapters."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    username: str
    email: str
    
    # These fields will be stored as JSONB and handled automatically by psycopg
    metadata: Dict[str, Any]
    preferences: Dict[str, Any] 
    tags: List[str]
    profile_data: Optional[Dict[str, Any]] = None


class UserRepository(BaseRepository[UserProfile, uuid.UUID]):
    """Repository that works with psycopg JSON adapters."""
    
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="user_profiles", 
            model_class=UserProfile,
            primary_key="id",
            # Disable our custom JSON processing since psycopg handles it
            auto_detect_json=False
        )


class Product(BaseModel):
    """Product model with JSONB specifications."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    price: Decimal
    specifications: Dict[str, Any]
    categories: List[str]


class ProductRepository(BaseRepository[Product, uuid.UUID]):
    """Product repository."""
    
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="products",
            model_class=Product,
            primary_key="id",
            auto_detect_json=False  # Let psycopg handle JSON
        )


async def setup_database_schema(db: Database):
    """Set up the database schema."""
    async with db.connection() as conn:
        async with conn.cursor() as cur:
            # Create user_profiles table
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    id UUID PRIMARY KEY,
                    username VARCHAR(100) NOT NULL UNIQUE,
                    email VARCHAR(255) NOT NULL,
                    metadata JSONB NOT NULL,
                    preferences JSONB NOT NULL,
                    tags JSONB NOT NULL,
                    profile_data JSONB
                )
            """)
            
            # Create products table  
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS products (
                    id UUID PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    price DECIMAL(10,2) NOT NULL,
                    specifications JSONB NOT NULL,
                    categories JSONB NOT NULL
                )
            """)
            
            # Create indexes for better JSONB performance
            await cur.execute("CREATE INDEX IF NOT EXISTS idx_user_metadata ON user_profiles USING GIN (metadata)")
            await cur.execute("CREATE INDEX IF NOT EXISTS idx_user_tags ON user_profiles USING GIN (tags)")
            await cur.execute("CREATE INDEX IF NOT EXISTS idx_product_specs ON products USING GIN (specifications)")
            await cur.execute("CREATE INDEX IF NOT EXISTS idx_product_categories ON products USING GIN (categories)")


async def demo_user_operations(db: Database):
    """Demonstrate user profile operations with JSONB."""
    print("\n" + "="*50)
    print("USER PROFILE OPERATIONS")
    print("="*50)
    
    async with db.connection() as conn:
        user_repo = UserRepository(conn)
        
        # Create a user with complex metadata
        user = UserProfile(
            username="alice_dev",
            email="alice@example.com",
            metadata={
                "created_at": datetime.now().isoformat(),
                "registration_source": "web_app",
                "ip_address": "192.168.1.50",
                "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
                "utm_source": "google",
                "utm_campaign": "spring_2024",
                "device_info": {
                    "screen_resolution": "1920x1080",
                    "browser": "Chrome",
                    "version": "120.0",
                    "mobile": False
                }
            },
            preferences={
                "theme": "dark",
                "language": "en",
                "timezone": "America/New_York",
                "email_notifications": True,
                "push_notifications": False,
                "marketing_emails": True
            },
            tags=["developer", "premium", "early_adopter"],
            profile_data={
                "bio": "Full-stack developer passionate about databases",
                "skills": ["Python", "JavaScript", "PostgreSQL", "Docker"],
                "experience_years": 7,
                "github_username": "alice_codes",
                "linkedin_url": "https://linkedin.com/in/alice-dev"
            }
        )
        
        print(f"Creating user: {user.username}")
        created_user = await user_repo.create(user)
        print(f"✅ User created with ID: {created_user.id}")
        
        # Retrieve and display user
        retrieved = await user_repo.get_by_id(created_user.id)
        print(f"✅ Retrieved user: {retrieved.username}")
        print(f"   Theme: {retrieved.preferences['theme']}")
        print(f"   Skills: {', '.join(retrieved.profile_data['skills'])}")
        print(f"   Browser: {retrieved.metadata['device_info']['browser']}")
        
        # Update preferences
        updated_user = await user_repo.update(created_user.id, {
            "preferences": {
                **retrieved.preferences,
                "theme": "light",
                "new_feature_beta": True
            }
        })
        print(f"✅ Updated theme to: {updated_user.preferences['theme']}")
        
        return created_user.id


async def demo_product_operations(db: Database):
    """Demonstrate product operations with JSONB specifications."""
    print("\n" + "="*50)
    print("PRODUCT OPERATIONS") 
    print("="*50)
    
    async with db.connection() as conn:
        product_repo = ProductRepository(conn)
        
        # Create a laptop product
        laptop = Product(
            name="MacBook Pro 16-inch",
            price=Decimal("2499.00"),
            specifications={
                "processor": {
                    "brand": "Apple",
                    "model": "M3 Pro",
                    "cores": 12,
                    "architecture": "ARM64"
                },
                "memory": {
                    "size_gb": 32,
                    "type": "Unified Memory",
                    "bandwidth": "400 GB/s"
                },
                "storage": {
                    "size_gb": 1000,
                    "type": "SSD",
                    "interface": "NVMe"
                },
                "display": {
                    "size_inches": 16.2,
                    "resolution": "3456x2234",
                    "technology": "Liquid Retina XDR",
                    "brightness_nits": 1000,
                    "color_gamut": "P3"
                },
                "connectivity": {
                    "thunderbolt_ports": 3,
                    "hdmi": "2.1",
                    "wifi": "WiFi 6E",
                    "bluetooth": "5.3"
                },
                "dimensions": {
                    "width_mm": 355.7,
                    "depth_mm": 248.1,
                    "height_mm": 16.8,
                    "weight_kg": 2.16
                }
            },
            categories=["laptops", "apple", "professional", "creative", "development"]
        )
        
        print(f"Creating product: {laptop.name}")
        created_product = await product_repo.create(laptop)
        print(f"✅ Product created with ID: {created_product.id}")
        
        # Retrieve and display
        retrieved = await product_repo.get_by_id(created_product.id)
        print(f"✅ Retrieved product: {retrieved.name}")
        print(f"   Price: ${retrieved.price}")
        print(f"   Processor: {retrieved.specifications['processor']['brand']} {retrieved.specifications['processor']['model']}")
        print(f"   Memory: {retrieved.specifications['memory']['size_gb']}GB")
        print(f"   Categories: {', '.join(retrieved.categories)}")
        
        return created_product.id


async def demo_jsonb_queries(db: Database, user_id: uuid.UUID, product_id: uuid.UUID):
    """Demonstrate JSONB querying capabilities."""
    print("\n" + "="*50)
    print("JSONB QUERY EXAMPLES")
    print("="*50)
    
    async with db.connection() as conn:
        async with conn.cursor() as cur:
            
            # Query 1: Find users by preference
            print("1. Finding users with dark theme preference:")
            await cur.execute("""
                SELECT username, preferences->>'theme' as theme
                FROM user_profiles 
                WHERE preferences->>'theme' = 'light'
            """)
            results = await cur.fetchall()
            for username, theme in results:
                print(f"   {username}: {theme}")
            
            # Query 2: Find users with specific skills
            print("\n2. Finding users with PostgreSQL skills:")
            await cur.execute("""
                SELECT username, profile_data->'skills' as skills
                FROM user_profiles 
                WHERE profile_data->'skills' ? 'PostgreSQL'
            """)
            results = await cur.fetchall()
            for username, skills in results:
                print(f"   {username}: {skills}")
            
            # Query 3: Find products by processor brand
            print("\n3. Finding Apple products:")
            await cur.execute("""
                SELECT name, specifications->'processor'->>'brand' as processor_brand
                FROM products 
                WHERE specifications->'processor'->>'brand' = 'Apple'
            """)
            results = await cur.fetchall()
            for name, brand in results:
                print(f"   {name}: {brand}")
            
            # Query 4: Find products with memory > 16GB
            print("\n4. Finding products with >16GB memory:")
            await cur.execute("""
                SELECT name, (specifications->'memory'->>'size_gb')::int as memory_gb
                FROM products 
                WHERE (specifications->'memory'->>'size_gb')::int > 16
            """)
            results = await cur.fetchall()
            for name, memory in results:
                print(f"   {name}: {memory}GB")
            
            # Query 5: Complex query with multiple JSONB conditions
            print("\n5. Complex JSONB query (users with premium tags and email notifications):")
            await cur.execute("""
                SELECT username, tags, preferences->>'email_notifications' as email_prefs
                FROM user_profiles 
                WHERE tags ? 'premium' 
                  AND preferences->>'email_notifications' = 'true'
            """)
            results = await cur.fetchall()
            for username, tags, email_prefs in results:
                print(f"   {username}: tags={tags}, email_notifications={email_prefs}")


async def demo_jsonb_updates(db: Database, user_id: uuid.UUID):
    """Demonstrate JSONB update operations."""
    print("\n" + "="*50)
    print("JSONB UPDATE EXAMPLES")
    print("="*50)
    
    async with db.connection() as conn:
        async with conn.cursor() as cur:
            
            # Update 1: Add new preference
            print("1. Adding new preference:")
            await cur.execute("""
                UPDATE user_profiles 
                SET preferences = preferences || '{"sidebar_collapsed": true}'::jsonb
                WHERE id = %s
                RETURNING preferences->>'sidebar_collapsed' as new_pref
            """, [user_id])
            result = await cur.fetchone()
            print(f"   ✅ Added sidebar_collapsed: {result[0]}")
            
            # Update 2: Add skill to array
            print("\n2. Adding new skill:")
            await cur.execute("""
                UPDATE user_profiles 
                SET profile_data = jsonb_set(
                    profile_data, 
                    '{skills}', 
                    profile_data->'skills' || '["Kubernetes"]'::jsonb
                )
                WHERE id = %s
                RETURNING profile_data->'skills' as updated_skills
            """, [user_id])
            result = await cur.fetchone()
            print(f"   ✅ Updated skills: {result[0]}")
            
            # Update 3: Update nested object
            print("\n3. Updating nested metadata:")
            await cur.execute("""
                UPDATE user_profiles 
                SET metadata = jsonb_set(
                    metadata,
                    '{device_info,last_login}',
                    %s::jsonb
                )
                WHERE id = %s
                RETURNING metadata->'device_info'->>'last_login' as last_login
            """, [f'"{datetime.now().isoformat()}"', user_id])
            result = await cur.fetchone()
            print(f"   ✅ Updated last_login: {result[0]}")


async def main():
    """Main function demonstrating practical JSONB usage."""
    print("🚀 Practical JSONB Usage - psycopg-toolkit")
    print("Demonstrating JSONB with psycopg JSON adapters (recommended approach)")
    
    with PostgresContainer("postgres:17") as container:
        settings = DatabaseSettings(
            host=container.get_container_host_ip(),
            port=container.get_exposed_port(5432),
            dbname=container.dbname,
            user=container.username,
            password=container.password,
            # Enable JSON adapters for automatic JSONB handling (recommended)
            enable_json_adapters=True
        )
        
        db = Database(settings)
        
        try:
            await db.init_db()
            print("✅ Database initialized with JSON adapters")
            
            await setup_database_schema(db)
            print("✅ Database schema created with JSONB fields and GIN indexes")
            
            # Run demonstrations
            user_id = await demo_user_operations(db)
            product_id = await demo_product_operations(db)
            await demo_jsonb_queries(db, user_id, product_id)
            await demo_jsonb_updates(db, user_id)
            
            print("\n" + "="*60)
            print("🎉 JSONB Demo Completed Successfully!")
            print("="*60)
            print("\nKey Points:")
            print("• JSONB fields are automatically handled by psycopg JSON adapters")
            print("• PostgreSQL JSONB provides rich querying capabilities")
            print("• GIN indexes improve JSONB query performance")
            print("• JSONB supports complex nested data structures")
            print("• Use JSONB operators: ->, ->>, ?, @>, <@, ||, etc.")
            print("• JSONB is ideal for semi-structured data and flexible schemas")
            
        finally:
            await db.cleanup()
            print("\n✅ Database cleanup completed")


if __name__ == "__main__":
    asyncio.run(main())