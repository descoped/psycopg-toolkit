"""Integration tests for JSONB with custom JSON processing (non-adapter mode)."""

import asyncio
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any

import pytest
from pydantic import BaseModel, Field
from testcontainers.postgres import PostgresContainer

from psycopg_toolkit import (
    Database,
    DatabaseSettings,
    BaseRepository,
    JSONSerializationError,
    JSONDeserializationError
)


class JSONTestModel(BaseModel):
    """Simple model for testing custom JSON processing."""
    id: int
    name: str
    data: Dict[str, Any]
    tags: List[str]
    metadata: Optional[Dict[str, Any]] = None


class JSONTestRepository(BaseRepository[JSONTestModel, int]):
    """Repository with custom JSON processing enabled."""
    
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="test_table",
            model_class=JSONTestModel,
            primary_key="id",
            # Enable custom JSON processing
            auto_detect_json=True,
            strict_json_processing=True
        )


@pytest.fixture
async def test_db_custom():
    """Create test database with custom JSON processing disabled at DB level."""
    with PostgresContainer("postgres:17") as container:
        settings = DatabaseSettings(
            host=container.get_container_host_ip(),
            port=container.get_exposed_port(5432),
            dbname=container.dbname,
            user=container.username,
            password=container.password,
            # Disable psycopg JSON adapters to test custom processing
            enable_json_adapters=False
        )
        
        db = Database(settings)
        await db.init_db()
        
        # Create test table
        async with db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE test_table (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        data TEXT NOT NULL,  -- Store as TEXT for custom processing
                        tags TEXT NOT NULL,  -- Store as TEXT for custom processing
                        metadata TEXT        -- Store as TEXT for custom processing
                    )
                """)
        
        yield db
        
        await db.cleanup()


class TestCustomJSONProcessing:
    """Test custom JSON processing without psycopg adapters."""
    
    @pytest.mark.asyncio
    async def test_custom_json_serialization(self, test_db_custom):
        """Test that custom JSON processing serializes data correctly."""
        async with test_db_custom.connection() as conn:
            repo = JSONTestRepository(conn)
            
            # Create test data
            test_data = JSONTestModel(
                id=1,
                name="test",
                data={
                    "key": "value",
                    "number": 42,
                    "nested": {"inner": "data"}
                },
                tags=["tag1", "tag2", "tag3"],
                metadata={"created": datetime.now().isoformat()}
            )
            
            # Create record
            created = await repo.create(test_data)
            
            # Verify data was serialized to TEXT columns
            async with conn.cursor() as cur:
                await cur.execute("""
                    SELECT data, tags, metadata 
                    FROM test_table 
                    WHERE id = %s
                """, [created.id])
                
                row = await cur.fetchone()
                data_col, tags_col, metadata_col = row
                
                # Should be JSON strings
                assert isinstance(data_col, str)
                assert isinstance(tags_col, str)
                assert isinstance(metadata_col, str)
                
                # Should be valid JSON
                import json
                parsed_data = json.loads(data_col)
                parsed_tags = json.loads(tags_col)
                parsed_metadata = json.loads(metadata_col)
                
                assert parsed_data["key"] == "value"
                assert parsed_tags == ["tag1", "tag2", "tag3"]
                assert "created" in parsed_metadata
    
    @pytest.mark.asyncio
    async def test_custom_json_deserialization(self, test_db_custom):
        """Test that custom JSON processing deserializes data correctly."""
        async with test_db_custom.connection() as conn:
            # Insert JSON data directly
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO test_table (name, data, tags, metadata)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """, [
                    "test",
                    '{"key": "value", "list": [1, 2, 3]}',
                    '["a", "b", "c"]',
                    '{"info": "test"}'
                ])
                
                test_id = (await cur.fetchone())[0]
            
            # Retrieve using repository
            repo = JSONTestRepository(conn)
            retrieved = await repo.get_by_id(test_id)
            
            assert retrieved.data["key"] == "value"
            assert retrieved.data["list"] == [1, 2, 3]
            assert retrieved.tags == ["a", "b", "c"]
            assert retrieved.metadata["info"] == "test"
    
    @pytest.mark.asyncio
    async def test_custom_json_error_handling(self, test_db_custom):
        """Test JSON error handling with strict processing."""
        async with test_db_custom.connection() as conn:
            repo = JSONTestRepository(conn)
            
            # Insert invalid JSON
            async with conn.cursor() as cur:
                await cur.execute("""
                    INSERT INTO test_table (id, name, data, tags)
                    VALUES (%s, %s, %s, %s)
                """, [
                    2,
                    "invalid",
                    '{"invalid": json}',  # Invalid JSON
                    '["valid"]'
                ])
            
            # Should raise JSONDeserializationError with strict processing
            with pytest.raises(JSONDeserializationError) as exc_info:
                await repo.get_by_id(2)
            
            assert exc_info.value.field_name == "data"
            assert "Cannot deserialize JSON" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_non_serializable_data(self, test_db_custom):
        """Test handling of non-serializable data."""
        async with test_db_custom.connection() as conn:
            repo = JSONTestRepository(conn)
            
            # Create object that can't be serialized
            class NonSerializable:
                pass
            
            test_data = JSONTestModel(
                id=3,
                name="test",
                data={"bad": NonSerializable()},  # This will fail
                tags=[]
            )
            
            # Should raise JSONSerializationError
            with pytest.raises(JSONSerializationError) as exc_info:
                await repo.create(test_data)
            
            assert exc_info.value.field_name == "data"
            assert "Cannot serialize to JSON" in str(exc_info.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])