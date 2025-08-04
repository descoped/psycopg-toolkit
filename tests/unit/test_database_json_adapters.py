"""Unit tests for Database JSON adapter configuration."""

import pytest
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from psycopg import AsyncConnection
from psycopg_pool import AsyncConnectionPool

from psycopg_toolkit.core.database import Database
from psycopg_toolkit.core.config import DatabaseSettings
from psycopg_toolkit.core.transaction import TransactionManager


class TestDatabaseJSONAdapters:
    """Test JSON adapter configuration in Database class."""
    
    @pytest.fixture
    def database_settings_with_json(self):
        """Database settings with JSON adapters enabled."""
        return DatabaseSettings(
            host="localhost",
            port=5432,
            dbname="test_db",
            user="test_user",
            password="test_password",
            enable_json_adapters=True
        )
    
    @pytest.fixture
    def database_settings_without_json(self):
        """Database settings with JSON adapters disabled."""
        return DatabaseSettings(
            host="localhost",
            port=5432,
            dbname="test_db",
            user="test_user",
            password="test_password",
            enable_json_adapters=False
        )
    
    @pytest.fixture
    def mock_connection(self):
        """Mock database connection."""
        return AsyncMock(spec=AsyncConnection)
    
    @pytest.fixture
    def mock_pool(self, mock_connection):
        """Mock connection pool."""
        pool = AsyncMock(spec=AsyncConnectionPool)
        pool.connection.return_value.__aenter__.return_value = mock_connection
        pool.connection.return_value.__aexit__ = AsyncMock(return_value=None)
        pool.closed = False
        return pool
    
    def test_json_adapters_enabled_by_default(self, database_settings_with_json):
        """Test that JSON adapters are enabled by default in settings."""
        settings = DatabaseSettings(
            host="localhost",
            port=5432,
            dbname="test_db",
            user="test_user",
            password="test_password"
        )
        assert settings.enable_json_adapters is True
    
    def test_json_adapters_can_be_disabled(self, database_settings_without_json):
        """Test that JSON adapters can be disabled in settings."""
        assert database_settings_without_json.enable_json_adapters is False
    
    def test_json_adapters_in_settings_dict(self, database_settings_with_json):
        """Test that JSON adapter setting is included in settings dict."""
        settings_dict = database_settings_with_json.to_dict(connection_only=False)
        assert 'enable_json_adapters' in settings_dict
        assert settings_dict['enable_json_adapters'] is True
    
    @patch('psycopg_toolkit.core.database.json')
    def test_configure_json_adapters_enabled(self, mock_json, database_settings_with_json, mock_connection):
        """Test JSON adapter configuration when enabled."""
        database = Database(database_settings_with_json)
        
        # Configure adapters
        database._configure_json_adapters(mock_connection)
        
        # Verify JSON adapters were configured
        mock_json.set_json_loads.assert_called_once_with(
            loads=mock_json.json.loads, 
            context=mock_connection
        )
        mock_json.set_json_dumps.assert_called_once_with(
            dumps=mock_json.json.dumps, 
            context=mock_connection
        )
    
    @patch('psycopg_toolkit.core.database.json')
    def test_configure_json_adapters_disabled(self, mock_json, database_settings_without_json, mock_connection):
        """Test JSON adapter configuration when disabled."""
        database = Database(database_settings_without_json)
        
        # Configure adapters
        database._configure_json_adapters(mock_connection)
        
        # Verify JSON adapters were NOT configured
        mock_json.set_json_loads.assert_not_called()
        mock_json.set_json_dumps.assert_not_called()
    
    @patch('psycopg_toolkit.core.database.Database.get_pool')
    @patch('psycopg_toolkit.core.database.json')
    async def test_connection_context_configures_json_adapters(self, mock_json, mock_get_pool, database_settings_with_json, mock_pool, mock_connection):
        """Test that connection context manager configures JSON adapters."""
        mock_get_pool.return_value = mock_pool
        database = Database(database_settings_with_json)
        
        async with database.connection() as conn:
            assert conn == mock_connection
        
        # Verify JSON adapters were configured
        mock_json.set_json_loads.assert_called_once()
        mock_json.set_json_dumps.assert_called_once()
    
    @patch('psycopg_toolkit.core.database.Database.get_pool')
    @patch('psycopg_toolkit.core.database.json')
    async def test_transaction_context_configures_json_adapters(self, mock_json, mock_get_pool, database_settings_with_json, mock_pool, mock_connection):
        """Test that transaction context manager configures JSON adapters."""
        mock_get_pool.return_value = mock_pool
        mock_connection.transaction.return_value.__aenter__ = AsyncMock(return_value=None)
        mock_connection.transaction.return_value.__aexit__ = AsyncMock(return_value=None)
        database = Database(database_settings_with_json)
        
        async with database.transaction() as conn:
            assert conn == mock_connection
        
        # Verify JSON adapters were configured
        mock_json.set_json_loads.assert_called_once()
        mock_json.set_json_dumps.assert_called_once()
    
    @patch('psycopg_toolkit.core.database.Database.get_pool')
    @patch('psycopg_toolkit.core.database.json')
    async def test_connection_without_json_adapters(self, mock_json, mock_get_pool, database_settings_without_json, mock_pool, mock_connection):
        """Test connection context when JSON adapters are disabled."""
        mock_get_pool.return_value = mock_pool
        database = Database(database_settings_without_json)
        
        async with database.connection() as conn:
            assert conn == mock_connection
        
        # Verify JSON adapters were NOT configured
        mock_json.set_json_loads.assert_not_called()
        mock_json.set_json_dumps.assert_not_called()
    
    @patch('psycopg_toolkit.core.database.Database.get_pool')
    @patch('psycopg_toolkit.core.database.json')
    @patch('psycopg_toolkit.core.database.logger')
    async def test_json_adapter_logging_enabled(self, mock_logger, mock_json, mock_get_pool, database_settings_with_json, mock_pool, mock_connection):
        """Test that JSON adapter configuration is logged when enabled."""
        mock_get_pool.return_value = mock_pool
        database = Database(database_settings_with_json)
        
        async with database.connection():
            pass
        
        # Check debug logging calls
        mock_logger.debug.assert_called()
        debug_calls = [call.args[0] for call in mock_logger.debug.call_args_list]
        assert any("Configuring JSON adapters" in call for call in debug_calls)
        assert any("JSON adapters configured successfully" in call for call in debug_calls)
    
    @patch('psycopg_toolkit.core.database.Database.get_pool')
    @patch('psycopg_toolkit.core.database.logger')
    async def test_json_adapter_logging_disabled(self, mock_logger, mock_get_pool, database_settings_without_json, mock_pool, mock_connection):
        """Test that JSON adapter disabling is logged when disabled."""
        mock_get_pool.return_value = mock_pool
        database = Database(database_settings_without_json)
        
        async with database.connection():
            pass
        
        # Check debug logging
        debug_calls = [call.args[0] for call in mock_logger.debug.call_args_list]
        assert any("JSON adapters disabled in settings" in call for call in debug_calls)
    
    @patch('psycopg_toolkit.core.database.Database.get_pool')
    async def test_transaction_manager_gets_json_configurator(self, mock_get_pool, database_settings_with_json, mock_pool):
        """Test that TransactionManager receives JSON adapter configurator."""
        mock_get_pool.return_value = mock_pool
        database = Database(database_settings_with_json)
        
        with patch('psycopg_toolkit.core.transaction.TransactionManager') as mock_tm_class:
            tm = await database.get_transaction_manager()
            
            # Verify TransactionManager was called with JSON configurator
            mock_tm_class.assert_called_once_with(mock_pool, database._configure_json_adapters)
    
    @patch('psycopg_toolkit.core.database.json')
    async def test_transaction_manager_configures_json_adapters(self, mock_json, mock_connection):
        """Test that TransactionManager configures JSON adapters in transactions.""" 
        mock_pool = AsyncMock(spec=AsyncConnectionPool)
        
        # Set up proper async context manager for pool.connection()
        mock_conn_context = AsyncMock()
        mock_conn_context.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_conn_context.__aexit__ = AsyncMock(return_value=None)
        mock_pool.connection.return_value = mock_conn_context
        
        # Set up proper async context manager for conn.transaction()
        mock_transaction_context = AsyncMock()
        mock_transaction_context.__aenter__ = AsyncMock(return_value=None)
        mock_transaction_context.__aexit__ = AsyncMock(return_value=None)
        mock_connection.transaction.return_value = mock_transaction_context
        
        # Create a real configurator function
        settings = DatabaseSettings(
            host="localhost",
            port=5432,
            dbname="test_db",
            user="test_user",
            password="test_password",
            enable_json_adapters=True
        )
        database = Database(settings)
        
        # Create TransactionManager with JSON configurator
        tm = TransactionManager(mock_pool, database._configure_json_adapters)
        
        async with tm.transaction() as conn:
            assert conn == mock_connection
        
        # Verify JSON adapters were configured
        mock_json.set_json_loads.assert_called_once()
        mock_json.set_json_dumps.assert_called_once()
    
    @patch('psycopg_toolkit.core.database.json')
    async def test_transaction_manager_without_json_configurator(self, mock_json, mock_connection):
        """Test TransactionManager without JSON configurator."""
        mock_pool = AsyncMock(spec=AsyncConnectionPool)
        
        # Set up proper async context manager for pool.connection()
        mock_conn_context = AsyncMock()
        mock_conn_context.__aenter__ = AsyncMock(return_value=mock_connection)
        mock_conn_context.__aexit__ = AsyncMock(return_value=None)
        mock_pool.connection.return_value = mock_conn_context
        
        # Set up proper async context manager for conn.transaction()
        mock_transaction_context = AsyncMock()
        mock_transaction_context.__aenter__ = AsyncMock(return_value=None)
        mock_transaction_context.__aexit__ = AsyncMock(return_value=None)
        mock_connection.transaction.return_value = mock_transaction_context
        
        # Create TransactionManager without JSON configurator
        tm = TransactionManager(mock_pool)
        
        async with tm.transaction() as conn:
            assert conn == mock_connection
        
        # Verify JSON adapters were NOT configured
        mock_json.set_json_loads.assert_not_called()
        mock_json.set_json_dumps.assert_not_called()
    
    def test_database_settings_backwards_compatibility(self):
        """Test that existing code works without specifying enable_json_adapters."""
        # This should work without specifying enable_json_adapters
        settings = DatabaseSettings(
            host="localhost",
            port=5432,
            dbname="test_db",
            user="test_user",
            password="test_password"
        )
        
        database = Database(settings)
        
        # Should have JSON adapters enabled by default
        assert database._settings.enable_json_adapters is True
    
    @patch('psycopg_toolkit.core.database.json')
    def test_json_adapter_exception_handling(self, mock_json, database_settings_with_json, mock_connection):
        """Test that JSON adapter configuration errors are handled gracefully."""
        # Make JSON configuration raise an exception
        mock_json.set_json_loads.side_effect = Exception("JSON config error")
        
        database = Database(database_settings_with_json)
        
        # This should not raise an exception - errors should be logged but not propagated
        # for now, but we may want to change this behavior in the future
        with pytest.raises(Exception, match="JSON config error"):
            database._configure_json_adapters(mock_connection)