from contextlib import AbstractAsyncContextManager
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest
from psycopg import AsyncConnection, Cursor
from psycopg_pool import AsyncConnectionPool
from pydantic import BaseModel

from psycopg_toolkit.exceptions import RecordNotFoundError, OperationError
from psycopg_toolkit.repositories.base import BaseRepository


# Test Model
class User(BaseModel):
    id: UUID
    username: str
    fullname: str


# Repository Implementation
class UserRepository(BaseRepository[User, UUID]):
    def __init__(self, db_connection: AsyncConnection):
        super().__init__(
            db_connection=db_connection,
            table_name="users",
            model_class=User,
            primary_key="id"
        )


class AsyncCursorContextManager:
    """Helper class to make cursor work as async context manager"""

    def __init__(self, cursor):
        self.cursor = cursor

    async def __aenter__(self):
        return self.cursor

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class MockCursor(AsyncMock):
    """Mock cursor with proper async support for all methods"""

    def __init__(self, *args, **kwargs):
        super().__init__(spec=Cursor)
        # Make execute return a coroutine that returns self
        self.execute = AsyncMock(return_value=self)
        self.fetchone = AsyncMock(return_value=None)
        self.fetchall = AsyncMock(return_value=[])
        self.rowcount = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class MockTransaction(AbstractAsyncContextManager):
    """Mock for psycopg Transaction that properly implements async context manager"""

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class MockConnection(AsyncMock):
    """Mock for psycopg Connection with proper transaction and cursor support"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._transaction = MockTransaction()
        self._cursor = MockCursor()

        # Override the cursor method to return a context manager instead of coroutine
        self.cursor = self._cursor_factory

    def _cursor_factory(self, *args, **kwargs):
        """Returns async cursor context manager directly"""
        return AsyncCursorContextManager(self._cursor)

    def transaction(self):
        return self._transaction


# Fixtures
@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def user_data(user_id):
    return {
        "id": user_id,
        "username": "johndoe",
        "fullname": "John Doe"
    }


@pytest.fixture
def user(user_data):
    return User(**user_data)


@pytest.fixture
async def mock_pool():
    pool = AsyncMock(spec=AsyncConnectionPool)
    conn = MockConnection()

    # Setup connection context manager
    cm = AsyncMock()
    cm.__aenter__.return_value = conn
    cm.__aexit__.return_value = None
    pool.connection.return_value = cm

    return pool


@pytest.fixture
async def mock_connection(mock_pool):
    return mock_pool.connection.return_value.__aenter__.return_value


@pytest.fixture
def mock_cursor(mock_connection):
    """Get the cursor from the mock connection"""
    return mock_connection._cursor


@pytest.fixture
def repository(mock_connection):
    """Create repository with properly mocked connection"""
    return UserRepository(mock_connection)


# Tests
@pytest.mark.asyncio
async def test_create_user(repository, user, mock_cursor):
    """Test creating a user"""
    # Setup mock
    mock_cursor.fetchone.return_value = user.model_dump()

    # Execute
    result = await repository.create(user)

    # Verify
    assert isinstance(result, User)
    assert result.id == user.id
    assert result.username == user.username
    assert result.fullname == user.fullname
    assert mock_cursor.execute.called


@pytest.mark.asyncio
async def test_create_user_failure(repository, user, mock_cursor):
    """Test create user failure when no result returned"""
    # Setup mock
    mock_cursor.fetchone.return_value = None

    # Execute and verify
    with pytest.raises(OperationError):
        await repository.create(user)


@pytest.mark.asyncio
async def test_get_user_by_id(repository, user_id, user_data, mock_cursor):
    """Test getting a user by ID"""
    # Setup mock
    mock_cursor.fetchone.return_value = user_data

    # Execute
    result = await repository.get_by_id(user_id)

    # Verify
    assert isinstance(result, User)
    assert result.id == user_id
    assert result.username == user_data["username"]
    assert result.fullname == user_data["fullname"]
    assert mock_cursor.execute.called


@pytest.mark.asyncio
async def test_get_user_by_id_not_found(repository, user_id, mock_cursor):
    """Test getting a non-existent user by ID"""
    # Setup mock
    mock_cursor.fetchone.return_value = None

    # Execute and verify
    with pytest.raises(RecordNotFoundError):
        await repository.get_by_id(user_id)


@pytest.mark.asyncio
async def test_get_all_users(repository, user_data, mock_cursor):
    """Test getting all users"""
    # Setup mock
    mock_cursor.fetchall.return_value = [user_data, user_data]  # Return two users

    # Execute
    results = await repository.get_all()

    # Verify
    assert len(results) == 2
    assert all(isinstance(result, User) for result in results)
    assert mock_cursor.execute.called


@pytest.mark.asyncio
async def test_update_user(repository, user_id, user_data, mock_cursor):
    """Test updating a user"""
    # Setup
    update_data = {"username": "janedoe", "fullname": "Jane Doe"}
    updated_data = {**user_data, **update_data}
    mock_cursor.fetchone.return_value = updated_data

    # Execute
    result = await repository.update(user_id, update_data)

    # Verify
    assert isinstance(result, User)
    assert result.id == user_id
    assert result.username == update_data["username"]
    assert result.fullname == update_data["fullname"]
    assert mock_cursor.execute.called


@pytest.mark.asyncio
async def test_update_user_not_found(repository, user_id, mock_cursor):
    """Test updating a non-existent user"""
    # Setup mock
    mock_cursor.fetchone.return_value = None

    # Execute and verify
    with pytest.raises(RecordNotFoundError):
        await repository.update(user_id, {"username": "new_username"})


@pytest.mark.asyncio
async def test_delete_user(repository, user_id, mock_cursor):
    """Test deleting a user"""
    # Setup mock to simulate successful deletion
    mock_cursor.rowcount = 1

    # Execute
    await repository.delete(user_id)

    # Verify
    assert mock_cursor.execute.called


@pytest.mark.asyncio
async def test_delete_user_not_found(repository, user_id, mock_cursor):
    """Test deleting a non-existent user"""
    # Setup mock to simulate record not found
    mock_cursor.rowcount = 0

    # Execute and verify
    with pytest.raises(RecordNotFoundError):
        await repository.delete(user_id)


@pytest.mark.asyncio
async def test_user_exists(repository, user_id, mock_cursor):
    """Test checking if a user exists"""
    # Setup mock
    mock_cursor.fetchone.return_value = (1,)

    # Execute
    result = await repository.exists(user_id)

    # Verify
    assert result is True
    assert mock_cursor.execute.called


@pytest.mark.asyncio
async def test_user_does_not_exist(repository, user_id, mock_cursor):
    """Test checking if a non-existent user exists"""
    # Setup mock
    mock_cursor.fetchone.return_value = None

    # Execute
    result = await repository.exists(user_id)

    # Verify
    assert result is False
    assert mock_cursor.execute.called
