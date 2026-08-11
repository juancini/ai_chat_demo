"""Pytest fixtures for unit and integration testing."""
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.mongodb import get_database
from app.main import app


@pytest.fixture
def mock_mongo_db():
    """Mock Motor database for unit tests."""
    mock_db = MagicMock()
    mock_conversations = MagicMock()
    mock_messages = MagicMock()

    mock_db.get_collection.side_effect = lambda name: (
        mock_conversations if name == "conversations" else mock_messages
    )

    return mock_db, mock_conversations, mock_messages


@pytest.fixture
async def async_client(mock_mongo_db):
    """Async HTTP Client for testing FastAPI routes."""
    mock_db, _, _ = mock_mongo_db
    app.dependency_overrides[get_database] = lambda: mock_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
