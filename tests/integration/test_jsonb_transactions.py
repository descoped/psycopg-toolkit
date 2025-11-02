"""JSONB transaction tests."""

import pytest
from conftest import SimpleJSON
from repositories.jsonb_repositories import SimpleJSONRepository


@pytest.mark.asyncio
class TestJSONBTransactions:
    """Test JSONB operations within transactions."""

    async def test_transaction_commit(self, jsonb_tables):
        """Test committing JSONB data in transaction."""
        repo = SimpleJSONRepository(jsonb_tables)

        # Create in transaction
        async with jsonb_tables.transaction():
            data = SimpleJSON(data={"transaction": "commit"})
            created = await repo.create(data)
            record_id = created.id

        # Verify outside transaction
        retrieved = await repo.get_by_id(record_id)
        assert retrieved is not None
        assert retrieved.data["transaction"] == "commit"

    async def test_transaction_rollback(self, jsonb_tables):
        """Test rolling back JSONB data in transaction."""
        repo = SimpleJSONRepository(jsonb_tables)

        # Get initial count
        initial_count = len(await repo.get_all())

        try:
            async with jsonb_tables.transaction():
                # Create record
                data = SimpleJSON(data={"transaction": "rollback"})
                await repo.create(data)

                # Force rollback
                raise Exception("Rollback test")
        except Exception:
            pass

        # Verify rollback
        final_count = len(await repo.get_all())
        assert final_count == initial_count

    async def test_nested_transactions(self, jsonb_tables):
        """Test nested transactions with JSONB data."""
        repo = SimpleJSONRepository(jsonb_tables)

        async with jsonb_tables.transaction():
            # Outer transaction
            outer = await repo.create(SimpleJSON(data={"level": "outer"}))

            try:
                async with jsonb_tables.transaction():
                    # Inner transaction
                    await repo.create(SimpleJSON(data={"level": "inner"}))

                    # Force inner rollback
                    raise Exception("Inner rollback")
            except Exception:
                pass

            # Outer should still exist
            retrieved = await repo.get_by_id(outer.id)
            assert retrieved is not None
            assert retrieved.data["level"] == "outer"

    async def test_transaction_isolation(self, jsonb_tables, db_pool):
        """Test transaction isolation with JSONB updates."""
        # First, create a record in a separate committed transaction
        async with db_pool.connection() as setup_conn:
            setup_repo = SimpleJSONRepository(setup_conn)
            async with setup_conn.transaction():
                initial = await setup_repo.create(SimpleJSON(data={"counter": 0}))
                record_id = initial.id

        # Now test isolation with two concurrent connections
        async with db_pool.connection() as conn1, db_pool.connection() as conn2:
            repo1 = SimpleJSONRepository(conn1)
            repo2 = SimpleJSONRepository(conn2)

            # Start first transaction and update
            async with conn1.transaction():
                # Update in first transaction
                record1 = await repo1.get_by_id(record_id)
                record1.data["counter"] = 1
                await repo1.update(record_id, {"data": record1.data})

                # Second connection (outside first transaction) should still see original value
                record2 = await repo2.get_by_id(record_id)
                assert record2.data["counter"] == 0

    async def test_savepoint_with_jsonb(self, jsonb_tables):
        """Test savepoints with JSONB operations."""
        repo = SimpleJSONRepository(jsonb_tables)

        async with jsonb_tables.transaction():
            # Create first record
            first = await repo.create(SimpleJSON(data={"order": 1}))

            # Create savepoint using cursor
            async with jsonb_tables.cursor() as cur:
                await cur.execute("SAVEPOINT sp1")

            # Create second record
            second = await repo.create(SimpleJSON(data={"order": 2}))
            second_id = second.id

            # Rollback to savepoint
            async with jsonb_tables.cursor() as cur:
                await cur.execute("ROLLBACK TO SAVEPOINT sp1")

            # First should exist
            retrieved_first = await repo.get_by_id(first.id)
            assert retrieved_first is not None

            # Second shouldn't exist after rollback to savepoint
            from psycopg_toolkit.exceptions import RecordNotFoundError

            with pytest.raises(RecordNotFoundError):
                await repo.get_by_id(second_id)

    async def test_transaction_manager(self, transaction_manager, jsonb_tables):
        """Test TransactionManager with JSONB operations."""
        async with transaction_manager.transaction() as conn:
            # Ensure tables exist
            async with conn.cursor() as cur:
                await cur.execute("""
                    CREATE TABLE IF NOT EXISTS jsonb_simple (
                        id SERIAL PRIMARY KEY,
                        data JSONB NOT NULL
                    )
                """)

            repo = SimpleJSONRepository(conn)

            # Create multiple records in transaction
            for i in range(3):
                await repo.create(SimpleJSON(data={"index": i}))

            # All should be visible within transaction
            all_records = await repo.get_all()
            assert len(all_records) >= 3

    async def test_concurrent_jsonb_updates(self, jsonb_tables):
        """Test concurrent updates to JSONB fields."""
        repo = SimpleJSONRepository(jsonb_tables)

        # Create record with nested data
        record = await repo.create(SimpleJSON(data={"stats": {"views": 0, "likes": 0}}))

        # Simulate concurrent updates
        async with jsonb_tables.transaction():
            # Increment views
            current = await repo.get_by_id(record.id)
            current.data["stats"]["views"] += 1
            await repo.update(record.id, {"data": current.data})

        async with jsonb_tables.transaction():
            # Increment likes
            current = await repo.get_by_id(record.id)
            current.data["stats"]["likes"] += 1
            await repo.update(record.id, {"data": current.data})

        # Verify both updates
        final = await repo.get_by_id(record.id)
        assert final.data["stats"]["views"] == 1
        assert final.data["stats"]["likes"] == 1
