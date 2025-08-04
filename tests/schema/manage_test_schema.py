#!/usr/bin/env python3
"""Utility script to manage JSONB test schema.

This script provides commands to setup, teardown, and reset the JSONB test schema
used by integration tests.

Usage:
    python manage_test_schema.py setup    - Create schema and insert test data
    python manage_test_schema.py teardown - Remove test data (keep schema)
    python manage_test_schema.py reset    - Teardown and setup
    python manage_test_schema.py drop     - Complete removal of schema
    python manage_test_schema.py status   - Show current schema status
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path to import psycopg_toolkit
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import asyncpg
from psycopg_toolkit import Database, DatabaseSettings


class TestSchemaManager:
    """Manages JSONB test schema lifecycle."""
    
    def __init__(self, db_settings: DatabaseSettings):
        self.db = Database(db_settings)
        self.schema_dir = Path(__file__).parent
        
    async def execute_sql_file(self, filename: str) -> None:
        """Execute SQL commands from a file."""
        sql_file = self.schema_dir / filename
        if not sql_file.exists():
            raise FileNotFoundError(f"SQL file not found: {sql_file}")
            
        async with self.db.connection() as conn:
            # Read and execute the SQL file
            sql_content = sql_file.read_text()
            
            # Split by semicolons but handle functions/procedures correctly
            statements = []
            current_statement = []
            in_function = False
            
            for line in sql_content.split('\n'):
                # Check for function/procedure start
                if 'CREATE OR REPLACE FUNCTION' in line or 'CREATE FUNCTION' in line:
                    in_function = True
                    
                current_statement.append(line)
                
                # Check for statement end
                if line.strip().endswith(';'):
                    if in_function and '$$ LANGUAGE' in line:
                        in_function = False
                        statements.append('\n'.join(current_statement))
                        current_statement = []
                    elif not in_function:
                        statements.append('\n'.join(current_statement))
                        current_statement = []
            
            # Execute each statement
            async with conn.cursor() as cur:
                for statement in statements:
                    statement = statement.strip()
                    if statement and not statement.startswith('--') and not statement.startswith('/*'):
                        # Skip \i includes and SELECT display statements
                        if not statement.startswith('\\i') and 'jsonb_test_schema.sql' not in statement:
                            try:
                                await cur.execute(statement)
                                print(f"✓ Executed: {statement[:50]}..." if len(statement) > 50 else f"✓ Executed: {statement}")
                            except Exception as e:
                                print(f"✗ Error executing statement: {e}")
                                print(f"  Statement: {statement[:100]}...")
    
    async def setup(self) -> None:
        """Create schema and insert test data."""
        print("Setting up JSONB test schema...")
        
        # First create the schema
        await self.execute_sql_file("jsonb_test_schema.sql")
        
        # Then insert test data (from setup script, excluding the \i command)
        setup_file = self.schema_dir / "setup_jsonb_tests.sql"
        sql_content = setup_file.read_text()
        
        # Remove the \i command line
        lines = [line for line in sql_content.split('\n') if not line.strip().startswith('\\i')]
        modified_sql = '\n'.join(lines)
        
        # Write temporary file and execute
        temp_file = self.schema_dir / "temp_setup.sql"
        temp_file.write_text(modified_sql)
        try:
            await self.execute_sql_file("temp_setup.sql")
        finally:
            temp_file.unlink()
        
        print("✅ JSONB test schema setup complete!")
        await self.status()
    
    async def teardown(self, complete: bool = False) -> None:
        """Remove test data or completely drop schema."""
        if complete:
            print("Performing complete schema teardown...")
            sql = """
            DROP TABLE IF EXISTS transaction_test CASCADE;
            DROP TABLE IF EXISTS product_catalog CASCADE;
            DROP TABLE IF EXISTS user_profiles CASCADE;
            DROP TABLE IF EXISTS configuration CASCADE;
            DROP TABLE IF EXISTS jsonb_performance_test CASCADE;
            DROP TABLE IF EXISTS jsonb_edge_cases CASCADE;
            DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;
            DROP FUNCTION IF EXISTS generate_json_data(INTEGER) CASCADE;
            DROP VIEW IF EXISTS jsonb_table_stats CASCADE;
            """
        else:
            print("Cleaning test data (preserving schema)...")
            sql = """
            TRUNCATE TABLE user_profiles CASCADE;
            TRUNCATE TABLE product_catalog CASCADE;
            TRUNCATE TABLE configuration CASCADE;
            TRUNCATE TABLE transaction_test CASCADE;
            TRUNCATE TABLE jsonb_performance_test CASCADE;
            TRUNCATE TABLE jsonb_edge_cases CASCADE;
            
            ALTER SEQUENCE product_catalog_id_seq RESTART WITH 1;
            ALTER SEQUENCE transaction_test_id_seq RESTART WITH 1;
            ALTER SEQUENCE jsonb_performance_test_id_seq RESTART WITH 1;
            ALTER SEQUENCE jsonb_edge_cases_id_seq RESTART WITH 1;
            """
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                for statement in sql.strip().split(';'):
                    if statement.strip():
                        await cur.execute(statement)
        
        print("✅ Teardown complete!")
    
    async def reset(self) -> None:
        """Reset schema (teardown and setup)."""
        print("Resetting JSONB test schema...")
        await self.teardown(complete=True)
        await self.setup()
    
    async def status(self) -> None:
        """Show current schema status."""
        print("\nJSONB Test Schema Status:")
        print("-" * 50)
        
        async with self.db.connection() as conn:
            async with conn.cursor() as cur:
                # Check if tables exist
                await cur.execute("""
                    SELECT tablename, 
                           pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
                    FROM pg_tables 
                    WHERE tablename IN (
                        'user_profiles', 'product_catalog', 'configuration', 
                        'transaction_test', 'jsonb_performance_test', 'jsonb_edge_cases'
                    )
                    ORDER BY tablename;
                """)
                
                tables = await cur.fetchall()
                if not tables:
                    print("❌ No JSONB test tables found!")
                    return
                
                print("Tables:")
                for table, size in tables:
                    # Get row count
                    await cur.execute(f"SELECT COUNT(*) FROM {table}")
                    count = (await cur.fetchone())[0]
                    print(f"  - {table}: {count} rows, {size}")
                
                # Check indexes
                await cur.execute("""
                    SELECT indexname, tablename
                    FROM pg_indexes
                    WHERE tablename IN (
                        'user_profiles', 'product_catalog', 'configuration', 
                        'transaction_test', 'jsonb_performance_test', 'jsonb_edge_cases'
                    )
                    AND indexname LIKE 'idx_%'
                    ORDER BY tablename, indexname;
                """)
                
                indexes = await cur.fetchall()
                print(f"\nGIN Indexes: {len(indexes)} total")
                
                # Check functions
                await cur.execute("""
                    SELECT proname
                    FROM pg_proc
                    WHERE proname IN ('update_updated_at_column', 'generate_json_data');
                """)
                
                functions = await cur.fetchall()
                print(f"Helper Functions: {len(functions)} found")
    
    async def cleanup(self) -> None:
        """Clean up database connection."""
        await self.db.cleanup()


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    # Get database settings from environment or use defaults
    db_settings = DatabaseSettings(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        dbname=os.getenv("POSTGRES_DB", "psycopg_test"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        enable_json_adapters=True
    )
    
    manager = TestSchemaManager(db_settings)
    
    try:
        await manager.db.init_db()
        
        if command == "setup":
            await manager.setup()
        elif command == "teardown":
            await manager.teardown()
        elif command == "drop":
            await manager.teardown(complete=True)
        elif command == "reset":
            await manager.reset()
        elif command == "status":
            await manager.status()
        else:
            print(f"Unknown command: {command}")
            print(__doc__)
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        await manager.cleanup()


if __name__ == "__main__":
    asyncio.run(main())