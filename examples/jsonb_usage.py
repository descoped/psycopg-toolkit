"""
Basic JSONB usage example demonstrating JSON field handling in psycopg-toolkit.

This example shows how to:
1. Define Pydantic models with JSON fields
2. Set up repositories with automatic JSON field detection
3. Perform CRUD operations with JSONB data
4. Handle different JSON data types (dict, list, nested objects)
5. Configure JSON processing options
6. Handle JSON-related exceptions
"""

import asyncio
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from testcontainers.postgres import PostgresContainer

from psycopg_toolkit import BaseRepository, Database, DatabaseSettings, JSONSerializationError


# Example 1: User Profile with JSON fields
class UserProfile(BaseModel):
    """User profile model with JSONB fields."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    username: str
    email: str

    # JSON fields (automatically detected by TypeInspector)
    metadata: dict[str, Any]  # Will be stored as JSONB
    preferences: dict[str, Any]  # Will be stored as JSONB (changed from Dict[str, str] to allow mixed types)
    tags: list[str]  # Will be stored as JSONB
    profile_data: dict[str, Any] | None = None  # Optional JSONB field


class UserRepository(BaseRepository[UserProfile, uuid.UUID]):
    """Repository for UserProfile with automatic JSON field detection."""

    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="user_profiles",
            model_class=UserProfile,
            primary_key="id",
            # auto_detect_json=True by default - detects metadata, preferences, tags, profile_data
        )


# Example 2: Product with explicit JSON field configuration
class Product(BaseModel):
    """Product model with explicitly configured JSON fields."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    price: Decimal

    # These would normally be detected as JSON fields
    specifications: dict[str, Any]
    categories: list[str]

    # This is a regular field that contains JSON-like data but shouldn't be processed
    description_json: str  # Raw JSON string, not a dict


class ProductRepository(BaseRepository[Product, uuid.UUID]):
    """Repository with explicit JSON field configuration."""

    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="products",
            model_class=Product,
            primary_key="id",
            # Explicitly specify which fields to treat as JSON
            json_fields={"specifications", "categories"},
            auto_detect_json=False,  # Disable auto-detection
        )


# Example 3: Document with strict JSON processing
class Document(BaseModel):
    """Document model with strict JSON error handling."""

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    title: str
    content: dict[str, Any]
    attachments: list[dict[str, str]]


class DocumentRepository(BaseRepository[Document, uuid.UUID]):
    """Repository with strict JSON processing enabled."""

    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="documents",
            model_class=Document,
            primary_key="id",
            strict_json_processing=True,  # Raise exceptions on JSON errors
        )


async def setup_database_schema(db: Database):
    """Set up the database schema for our examples."""
    async with db.connection() as conn, conn.cursor() as cur:
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
                    categories JSONB NOT NULL,
                    description_json TEXT
                )
            """)

        # Create documents table
        await cur.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id UUID PRIMARY KEY,
                    title VARCHAR(255) NOT NULL,
                    content JSONB NOT NULL,
                    attachments JSONB NOT NULL
                )
            """)

        # Create GIN indexes for better JSONB performance
        await cur.execute("CREATE INDEX IF NOT EXISTS idx_user_metadata ON user_profiles USING GIN (metadata)")
        await cur.execute("CREATE INDEX IF NOT EXISTS idx_product_specs ON products USING GIN (specifications)")
        await cur.execute("CREATE INDEX IF NOT EXISTS idx_document_content ON documents USING GIN (content)")


async def example_1_basic_jsonb_operations(db: Database):
    """Example 1: Basic JSONB operations with automatic field detection."""
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Basic JSONB Operations")
    print("=" * 60)

    async with db.connection() as conn:
        user_repo = UserRepository(conn)

        # Create a user with complex JSON data
        user_data = UserProfile(
            username="john_doe",
            email="john@example.com",
            metadata={
                "created_at": datetime.now().isoformat(),
                "source": "registration_form",
                "ip_address": "192.168.1.100",
                "browser": {"name": "Chrome", "version": "120.0", "os": "macOS"},
            },
            preferences={"theme": "dark", "language": "en", "timezone": "UTC", "notifications": "email"},
            tags=["premium", "early_adopter", "newsletter"],
            profile_data={
                "bio": "Software engineer passionate about databases",
                "skills": ["Python", "PostgreSQL", "Docker"],
                "experience_years": 5,
                "salary_range": {"min": 80000, "max": 120000, "currency": "USD"},
            },
        )

        print(f"Creating user: {user_data.username}")
        created_user = await user_repo.create(user_data)
        print(f"✅ Created user with ID: {created_user.id}")

        # Retrieve the user
        print(f"\nRetrieving user by ID: {created_user.id}")
        retrieved_user = await user_repo.get_by_id(created_user.id)
        print(f"✅ Retrieved user: {retrieved_user.username}")
        print(f"   Metadata keys: {list(retrieved_user.metadata.keys())}")
        print(f"   Browser: {retrieved_user.metadata['browser']['name']}")
        print(f"   Tags: {retrieved_user.tags}")

        # Update JSON fields
        print("\nUpdating user preferences...")
        updated_user = await user_repo.update(
            created_user.id,
            {
                "preferences": {**retrieved_user.preferences, "theme": "light", "new_feature_enabled": True},
                "tags": [*retrieved_user.tags, "updated"],
            },
        )
        print(f"✅ Updated preferences theme: {updated_user.preferences['theme']}")
        print(f"✅ Updated tags: {updated_user.tags}")

        # Query all users
        all_users = await user_repo.get_all()
        print(f"\n✅ Found {len(all_users)} users in database")


async def example_2_explicit_json_configuration(db: Database):
    """Example 2: Explicit JSON field configuration."""
    print("\n" + "=" * 60)
    print("EXAMPLE 2: Explicit JSON Field Configuration")
    print("=" * 60)

    async with db.connection() as conn:
        product_repo = ProductRepository(conn)

        # Create a product with complex specifications
        product_data = Product(
            name="Gaming Laptop",
            price=Decimal("1299.99"),
            specifications={
                "cpu": {
                    "brand": "Intel",
                    "model": "i7-12700H",
                    "cores": 14,
                    "base_clock": "2.3 GHz",
                    "boost_clock": "4.7 GHz",
                },
                "gpu": {"brand": "NVIDIA", "model": "RTX 3070", "memory": "8GB GDDR6"},
                "memory": {"size": "32GB", "type": "DDR4", "speed": "3200MHz"},
                "storage": [{"type": "SSD", "size": "1TB", "interface": "NVMe"}],
            },
            categories=["gaming", "laptops", "high-performance", "portable"],
            description_json='{"short": "Powerful gaming laptop", "long": "High-performance gaming laptop with RTX graphics"}',  # Raw JSON string
        )

        print(f"Creating product: {product_data.name}")
        created_product = await product_repo.create(product_data)
        print(f"✅ Created product with ID: {created_product.id}")

        # The specifications and categories are automatically serialized/deserialized
        # The description_json remains as a string (not processed as JSON)
        retrieved_product = await product_repo.get_by_id(created_product.id)
        print(f"✅ Retrieved product: {retrieved_product.name}")
        print(f"   CPU: {retrieved_product.specifications['cpu']['model']}")
        print(f"   Categories: {retrieved_product.categories}")
        print(f"   Description (raw JSON): {retrieved_product.description_json}")

        # Update specifications
        updated_specs = retrieved_product.specifications.copy()
        updated_specs["warranty"] = {
            "duration": "2 years",
            "type": "comprehensive",
            "coverage": ["hardware", "software", "accidental"],
        }

        updated_product = await product_repo.update(created_product.id, {"specifications": updated_specs})
        print(f"✅ Added warranty info: {updated_product.specifications['warranty']['duration']}")


async def example_3_strict_json_processing(db: Database):
    """Example 3: Strict JSON processing with error handling."""
    print("\n" + "=" * 60)
    print("EXAMPLE 3: Strict JSON Processing & Error Handling")
    print("=" * 60)

    async with db.connection() as conn:
        doc_repo = DocumentRepository(conn)

        # Create a document with complex content
        document_data = Document(
            title="Project Specification",
            content={
                "version": "1.0",
                "status": "draft",
                "sections": [
                    {
                        "title": "Introduction",
                        "content": "This document outlines the project requirements...",
                        "last_modified": datetime.now().isoformat(),
                    },
                    {
                        "title": "Technical Requirements",
                        "content": "The system must support...",
                        "requirements": [
                            {"id": "REQ-001", "priority": "high", "description": "User authentication"},
                            {"id": "REQ-002", "priority": "medium", "description": "Data backup"},
                        ],
                    },
                ],
                "metadata": {"author": "John Doe", "department": "Engineering", "classification": "internal"},
            },
            attachments=[
                {
                    "filename": "architecture_diagram.png",
                    "size": "2.3MB",
                    "type": "image/png",
                    "url": "https://example.com/files/arch.png",
                },
                {
                    "filename": "requirements.xlsx",
                    "size": "456KB",
                    "type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    "url": "https://example.com/files/req.xlsx",
                },
            ],
        )

        print(f"Creating document: {document_data.title}")
        created_doc = await doc_repo.create(document_data)
        print(f"✅ Created document with ID: {created_doc.id}")

        retrieved_doc = await doc_repo.get_by_id(created_doc.id)
        print(f"✅ Retrieved document: {retrieved_doc.title}")
        print(f"   Sections: {len(retrieved_doc.content['sections'])}")
        print(f"   Attachments: {len(retrieved_doc.attachments)}")
        print(f"   Author: {retrieved_doc.content['metadata']['author']}")

        # Demonstrate error handling with invalid JSON data
        print("\n--- Testing JSON Error Handling ---")
        try:
            # This would cause a JSON serialization error if we tried to store a non-serializable object
            class NonSerializable:
                pass

            # This will raise JSONSerializationError due to strict processing
            await doc_repo.update(
                created_doc.id,
                {
                    "content": {
                        "bad_data": NonSerializable()  # Cannot be serialized to JSON
                    }
                },
            )
        except JSONSerializationError as e:
            print(f"✅ Caught JSONSerializationError: {e}")
            print(f"   Field: {e.field_name}")
            print(f"   Original error: {type(e.original_error).__name__}")


async def example_4_json_querying_tips(db: Database):
    """Example 4: Tips for querying JSONB data."""
    print("\n" + "=" * 60)
    print("EXAMPLE 4: JSONB Querying Tips")
    print("=" * 60)

    async with db.connection() as conn, conn.cursor() as cur:
        # Raw SQL queries on JSONB data
        print("Querying JSONB data with SQL:")

        # Find users with specific browser
        await cur.execute("""
            SELECT username, metadata->>'source' as source
            FROM user_profiles
            WHERE metadata->'browser'->>'name' = 'Chrome'
        """)
        chrome_users = await cur.fetchall()
        print(f"✅ Users with Chrome browser: {len(chrome_users)}")

        # Find products in specific category
        await cur.execute("""
            SELECT name, categories
            FROM products
            WHERE categories ? 'gaming'
        """)
        gaming_products = await cur.fetchall()
        print(f"✅ Gaming products: {len(gaming_products)}")

        # Find products with CPU core count > 10
        await cur.execute("""
            SELECT name, specifications->'cpu'->>'model' as cpu_model
            FROM products
            WHERE (specifications->'cpu'->>'cores')::int > 10
        """)
        high_core_products = await cur.fetchall()
        print(f"✅ Products with >10 CPU cores: {len(high_core_products)}")

        # Full-text search in document content
        await cur.execute("""
            SELECT title, content->>'status' as status
            FROM documents
            WHERE content @> '{"status": "draft"}'
        """)
        draft_docs = await cur.fetchall()
        print(f"✅ Draft documents: {len(draft_docs)}")


async def main():
    """Main function demonstrating JSONB usage patterns."""
    print("🚀 JSONB Usage Example - psycopg-toolkit")
    print("This example demonstrates comprehensive JSONB functionality")

    # Initialize postgres container
    with PostgresContainer("postgres:17") as container:
        settings = DatabaseSettings(
            host=container.get_container_host_ip(),
            port=container.get_exposed_port(5432),
            dbname=container.dbname,
            user=container.username,
            password=container.password,
            # Disable psycopg JSON adapters to demonstrate our custom JSON processing
            # In production, you'd typically enable this for better performance
            enable_json_adapters=False,
        )

        # Create database instance
        db = Database(settings)

        try:
            # Initialize the database pool
            await db.init_db()
            print("✅ Database initialized")

            # Set up schema
            await setup_database_schema(db)
            print("✅ Database schema created")

            # Run examples
            await example_1_basic_jsonb_operations(db)
            await example_2_explicit_json_configuration(db)
            await example_3_strict_json_processing(db)
            await example_4_json_querying_tips(db)

            print("\n" + "=" * 60)
            print("🎉 All JSONB examples completed successfully!")
            print("=" * 60)
            print("\nKey takeaways:")
            print("• JSON fields are automatically detected from Pydantic type hints")
            print("• Use explicit json_fields for fine-grained control")
            print("• Enable strict_json_processing for better error handling")
            print("• JSONB supports complex nested data structures")
            print("• Use GIN indexes for better JSONB query performance")
            print("• PostgreSQL provides powerful JSONB operators for querying")

        finally:
            # Clean up resources
            await db.cleanup()
            print("\n✅ Database cleanup completed")


if __name__ == "__main__":
    asyncio.run(main())
