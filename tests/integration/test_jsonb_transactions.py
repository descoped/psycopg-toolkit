"""Integration tests for JSONB handling within transactions."""

import asyncio
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Any

import pytest
from pydantic import BaseModel, Field
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from psycopg.types.json import Json
from testcontainers.postgres import PostgresContainer

from psycopg_toolkit import (
    Database,
    DatabaseSettings,
    BaseRepository,
    TransactionManager,
    RecordNotFoundError,
    OperationError
)


class TransactionTestModel(BaseModel):
    """Model for testing JSONB in transactions."""
    id: int
    name: str
    status: str
    
    # JSONB fields
    data: Dict[str, Any]
    history: List[Dict[str, Any]]
    metadata: Optional[Dict[str, Any]] = None


class TransactionRepository(BaseRepository[TransactionTestModel, int]):
    """Repository for transaction tests."""
    
    def __init__(self, db_connection):
        super().__init__(
            db_connection=db_connection,
            table_name="transaction_test",
            model_class=TransactionTestModel,
            primary_key="id",
            # Let psycopg handle JSON
            auto_detect_json=False
        )


@pytest.fixture
async def test_db():
    """Create test database with transaction test schema."""
    with PostgresContainer("postgres:17") as container:
        settings = DatabaseSettings(
            host=container.get_container_host_ip(),
            port=container.get_exposed_port(5432),
            dbname=container.dbname,
            user=container.username,
            password=container.password,
            enable_json_adapters=True
        )
        
        db = Database(settings)
        await db.init_db()
        
        # Create test schema
        async with db.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE transaction_test (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR(100) NOT NULL,
                        status VARCHAR(50) NOT NULL,
                        data JSONB NOT NULL,
                        history JSONB NOT NULL,
                        metadata JSONB
                    )
                """)
                
                # Create index for better performance
                await cur.execute("CREATE INDEX idx_transaction_data ON transaction_test USING GIN (data)")
        
        yield db
        
        await db.cleanup()


class TestJSONBTransactions:
    """Test JSONB operations within transactions."""
    
    @pytest.mark.asyncio
    async def test_transaction_commit_with_jsonb(self, test_db):
        """Test successful transaction commit with JSONB data."""
        async with test_db.connection() as conn:
            repo = TransactionRepository(conn)
            
            # Start transaction
            async with conn.transaction():
                # Create multiple records with JSONB
                record1 = TransactionTestModel(
                    id=1,
                    name="transaction_test_1",
                    status="pending",
                    data={"type": "create", "value": 100},
                    history=[{"action": "created", "timestamp": datetime.now().isoformat()}]
                )
                
                record2 = TransactionTestModel(
                    id=2,
                    name="transaction_test_2",
                    status="pending",
                    data={"type": "create", "value": 200, "nested": {"key": "value"}},
                    history=[{"action": "created", "timestamp": datetime.now().isoformat()}],
                    metadata={"source": "test", "priority": "high"}
                )
                
                created1 = await repo.create(record1)
                created2 = await repo.create(record2)
                
                # Verify within transaction
                assert created1.data["value"] == 100
                assert created2.data["nested"]["key"] == "value"
                
                # Update one record
                await repo.update(created1.id, {
                    "status": "active",
                    "data": {"type": "update", "value": 150, "modified": True}
                })
            
            # After commit, verify data persisted
            retrieved1 = await repo.get_by_id(1)
            retrieved2 = await repo.get_by_id(2)
            
            assert retrieved1.status == "active"
            assert retrieved1.data["value"] == 150
            assert retrieved1.data["modified"] is True
            assert retrieved2.data["value"] == 200
    
    @pytest.mark.asyncio
    async def test_transaction_rollback_with_jsonb(self, test_db):
        """Test transaction rollback with JSONB data."""
        async with test_db.connection() as conn:
            repo = TransactionRepository(conn)
            
            # Create initial record
            initial = TransactionTestModel(
                id=1,
                name="rollback_test",
                status="initial",
                data={"value": 1000, "important": True},
                history=[{"action": "init", "timestamp": datetime.now().isoformat()}]
            )
            await repo.create(initial)
            
            try:
                async with conn.transaction():
                    # Update the record
                    await repo.update(1, {
                        "status": "modified",
                        "data": {"value": 2000, "important": False, "new_field": "added"},
                        "history": [
                            {"action": "init", "timestamp": datetime.now().isoformat()},
                            {"action": "modified", "timestamp": datetime.now().isoformat()}
                        ]
                    })
                    
                    # Verify update within transaction
                    updated = await repo.get_by_id(1)
                    assert updated.data["value"] == 2000
                    assert len(updated.history) == 2
                    
                    # Force rollback
                    raise Exception("Force rollback")
            except Exception:
                pass  # Expected
            
            # After rollback, data should be unchanged
            retrieved = await repo.get_by_id(1)
            assert retrieved.status == "initial"
            assert retrieved.data["value"] == 1000
            assert retrieved.data["important"] is True
            assert len(retrieved.history) == 1
    
    @pytest.mark.asyncio
    async def test_savepoint_with_jsonb(self, test_db):
        """Test savepoints with JSONB operations."""
        async with test_db.connection() as conn:
            repo = TransactionRepository(conn)
            
            async with conn.transaction():
                # Create first record
                record1 = TransactionTestModel(
                    id=1,
                    name="savepoint_test_1",
                    status="created",
                    data={"step": 1, "data": {"key1": "value1"}},
                    history=[{"action": "step1", "timestamp": datetime.now().isoformat()}]
                )
                await repo.create(record1)
                
                # Create savepoint
                try:
                    async with conn.transaction(savepoint_name="sp1"):
                        # Create second record
                        record2 = TransactionTestModel(
                            id=2,
                            name="savepoint_test_2",
                            status="created",
                            data={"step": 2, "data": {"key2": "value2"}},
                            history=[{"action": "step2", "timestamp": datetime.now().isoformat()}]
                        )
                        await repo.create(record2)
                        
                        # Update first record
                        await repo.update(1, {
                            "data": {"step": 1.5, "data": {"key1": "modified", "extra": "data"}}
                        })
                        
                        # Rollback to savepoint
                        raise Exception("Rollback to savepoint")
                except Exception:
                    pass  # Expected
            
            # After transaction, only first record should exist with original data
            records = await repo.get_all()
            assert len(records) == 1
            assert records[0].id == 1
            assert records[0].data["step"] == 1
            assert records[0].data["data"]["key1"] == "value1"
            assert "extra" not in records[0].data["data"]
    
    @pytest.mark.asyncio
    async def test_nested_transactions_with_jsonb(self, test_db):
        """Test nested transactions with JSONB data."""
        async with test_db.connection() as conn:
            repo = TransactionRepository(conn)
            
            async with conn.transaction():
                # Outer transaction - create base record
                base = TransactionTestModel(
                    id=1,
                    name="nested_test",
                    status="base",
                    data={"level": 0, "values": []},
                    history=[{"action": "base", "level": 0}]
                )
                await repo.create(base)
                
                try:
                    async with conn.transaction(savepoint_name="nested1"):
                        # First nested level
                        await repo.update(1, {
                            "data": {"level": 1, "values": [1, 2, 3]},
                            "history": [
                                {"action": "base", "level": 0},
                                {"action": "nested1", "level": 1}
                            ]
                        })
                        
                        try:
                            async with conn.transaction(savepoint_name="nested2"):
                                # Second nested level
                                await repo.update(1, {
                                    "data": {"level": 2, "values": [1, 2, 3, 4, 5], "nested": {"deep": True}},
                                    "history": [
                                        {"action": "base", "level": 0},
                                        {"action": "nested1", "level": 1},
                                        {"action": "nested2", "level": 2}
                                    ]
                                })
                                
                                # Force rollback of innermost transaction
                                raise Exception("Rollback nested2")
                        except Exception:
                            pass  # Expected
                        
                        # Should be at level 1
                        current = await repo.get_by_id(1)
                        assert current.data["level"] == 1
                        assert current.data["values"] == [1, 2, 3]
                        assert "nested" not in current.data
                
                except Exception:
                    pass  # If needed
            
            # After commit, should have level 1 data
            final = await repo.get_by_id(1)
            assert final.data["level"] == 1
            assert len(final.history) == 2
    
    @pytest.mark.asyncio
    async def test_transaction_manager_with_jsonb(self, test_db):
        """Test TransactionManager with JSONB operations."""
        tx_manager = TransactionManager(test_db)
        
        # Use transaction manager for complex operation
        async with tx_manager.transaction() as conn:
            repo = TransactionRepository(conn)
            
            # Create records with complex JSONB
            records = []
            for i in range(3):
                record = TransactionTestModel(
                    id=i+1,
                    name=f"tx_manager_test_{i}",
                    status="active",
                    data={
                        "index": i,
                        "config": {
                            "enabled": True,
                            "settings": {"key": f"value_{i}", "nested": {"level": i}}
                        },
                        "array": list(range(i+1))
                    },
                    history=[
                        {"action": "created", "index": i, "timestamp": datetime.now().isoformat()}
                    ],
                    metadata={"managed": True, "batch": "test"}
                )
                created = await repo.create(record)
                records.append(created)
            
            # Bulk update using transaction
            for record in records:
                new_data = record.data.copy()
                new_data["config"]["settings"]["updated"] = True
                new_data["array"].append(999)
                
                await repo.update(record.id, {
                    "data": new_data,
                    "history": record.history + [{"action": "bulk_update", "timestamp": datetime.now().isoformat()}]
                })
        
        # Verify after transaction
        async with test_db.connection() as conn:
            repo = TransactionRepository(conn)
            all_records = await repo.get_all()
            
            assert len(all_records) == 3
            for record in all_records:
                assert record.data["config"]["settings"]["updated"] is True
                assert 999 in record.data["array"]
                assert len(record.history) == 2
                assert record.history[-1]["action"] == "bulk_update"
    
    @pytest.mark.asyncio
    async def test_concurrent_jsonb_updates_in_transaction(self, test_db):
        """Test concurrent JSONB updates within a transaction."""
        async with test_db.connection() as conn:
            repo = TransactionRepository(conn)
            
            # Create initial record
            initial = TransactionTestModel(
                id=1,
                name="concurrent_test",
                status="initial",
                data={"counter": 0, "operations": []},
                history=[{"action": "init", "timestamp": datetime.now().isoformat()}]
            )
            await repo.create(initial)
            
            async with conn.transaction():
                # Simulate concurrent-like updates within transaction
                for i in range(5):
                    current = await repo.get_by_id(1)
                    
                    # Modify JSONB data
                    new_data = current.data.copy()
                    new_data["counter"] += 1
                    new_data["operations"].append({
                        "op": i,
                        "value": i * 10,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # Add to history
                    new_history = current.history.copy()
                    new_history.append({
                        "action": f"update_{i}",
                        "counter": new_data["counter"],
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    await repo.update(1, {
                        "data": new_data,
                        "history": new_history
                    })
            
            # Verify final state
            final = await repo.get_by_id(1)
            assert final.data["counter"] == 5
            assert len(final.data["operations"]) == 5
            assert len(final.history) == 6  # init + 5 updates
            
            # Verify operation values
            for i, op in enumerate(final.data["operations"]):
                assert op["op"] == i
                assert op["value"] == i * 10
    
    @pytest.mark.asyncio
    async def test_transaction_isolation_with_jsonb(self, test_db):
        """Test transaction isolation with JSONB data."""
        # Create initial data
        async with test_db.connection() as conn:
            repo = TransactionRepository(conn)
            initial = TransactionTestModel(
                id=1,
                name="isolation_test",
                status="initial",
                data={"shared": True, "value": 100},
                history=[{"action": "init"}]
            )
            await repo.create(initial)
        
        # Start two concurrent connections
        async with test_db.connection() as conn1, test_db.connection() as conn2:
            repo1 = TransactionRepository(conn1)
            repo2 = TransactionRepository(conn2)
            
            # Start transaction in conn1
            async with conn1.transaction():
                # Update in transaction 1
                await repo1.update(1, {
                    "data": {"shared": False, "value": 200, "tx": 1},
                    "history": [{"action": "init"}, {"action": "tx1_update"}]
                })
                
                # Try to read from conn2 (should see original data)
                record2 = await repo2.get_by_id(1)
                assert record2.data["shared"] is True
                assert record2.data["value"] == 100
                assert "tx" not in record2.data
                
                # Commit happens here
            
            # Now conn2 should see the updates
            record2_after = await repo2.get_by_id(1)
            assert record2_after.data["shared"] is False
            assert record2_after.data["value"] == 200
            assert record2_after.data["tx"] == 1
    
    @pytest.mark.asyncio
    async def test_transaction_with_jsonb_aggregation(self, test_db):
        """Test JSONB aggregation operations within transaction."""
        async with test_db.connection() as conn:
            repo = TransactionRepository(conn)
            
            async with conn.transaction():
                # Create multiple records
                for i in range(5):
                    record = TransactionTestModel(
                        id=i+1,
                        name=f"aggregate_test_{i}",
                        status="active",
                        data={
                            "category": "A" if i % 2 == 0 else "B",
                            "value": (i+1) * 100,
                            "metrics": {
                                "score": (i+1) * 10,
                                "weight": 1.0 / (i+1)
                            }
                        },
                        history=[{"action": "created", "index": i}],
                        metadata={"batch": "aggregation_test"}
                    )
                    await repo.create(record)
                
                # Perform aggregation query on JSONB data
                async with conn.cursor(row_factory=dict_row) as cur:
                    # Count by category
                    await cur.execute("""
                        SELECT 
                            data->>'category' as category,
                            COUNT(*) as count,
                            SUM((data->>'value')::int) as total_value,
                            AVG((data->'metrics'->>'score')::float) as avg_score
                        FROM transaction_test
                        WHERE metadata->>'batch' = 'aggregation_test'
                        GROUP BY data->>'category'
                    """)
                    
                    results = await cur.fetchall()
                    assert len(results) == 2
                    
                    for result in results:
                        if result['category'] == 'A':
                            assert result['count'] == 3  # 0, 2, 4
                            assert result['total_value'] == 100 + 300 + 500
                            assert result['avg_score'] == (10 + 30 + 50) / 3
                        else:  # category B
                            assert result['count'] == 2  # 1, 3
                            assert result['total_value'] == 200 + 400
                            assert result['avg_score'] == (20 + 40) / 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])