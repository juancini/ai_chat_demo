from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.chat_service import ChatService


@pytest.mark.asyncio
async def test_get_system_status(async_client, mock_mongo_db):
    mock_db, _, _ = mock_mongo_db
    mock_db.command = AsyncMock(return_value={"ok": 1})

    response = await async_client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "llm_provider" in data
    assert "has_api_key" in data


@pytest.mark.asyncio
async def test_get_system_status_returns_503_when_db_ping_fails(async_client, mock_mongo_db):
    mock_db, _, _ = mock_mongo_db
    mock_db.command = AsyncMock(side_effect=Exception("connection refused"))

    response = await async_client.get("/api/v1/system/status")
    assert response.status_code == 503
    assert "Database health check failed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_invalid_conversation_id_returns_400(async_client):
    response = await async_client.get("/api/v1/conversations/invalid-id-format")
    assert response.status_code == 400
    assert "Invalid conversation ID format" in response.json()["detail"]


@pytest.mark.asyncio
async def test_send_message_updates_title_for_default_or_blank_titles(mock_mongo_db):
    db, conv_col, msg_col = mock_mongo_db

    conv_col.find_one = AsyncMock(return_value={"_id": "507f1f77bcf86cd799439011", "title": "   "})
    conv_col.update_one = AsyncMock(return_value=MagicMock())

    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=[])
    msg_col.find.return_value.sort.return_value = cursor
    msg_col.insert_one = AsyncMock(return_value=MagicMock(inserted_id="message-id"))

    llm_service = MagicMock()
    llm_service.generate_response = AsyncMock(return_value=("Hello!", "mock", "mock-demo-v1"))
    llm_service.generate_title = AsyncMock(return_value="Helpful Summary")

    service = ChatService(db, llm_service=llm_service)

    await service.send_message("507f1f77bcf86cd799439011", "Hello there")

    llm_service.generate_title.assert_awaited_once_with("Hello there")
    update_payload = conv_col.update_one.await_args.args[1]["$set"]
    assert update_payload["title"] == "Helpful Summary"
