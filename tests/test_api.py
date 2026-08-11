import pytest


@pytest.mark.asyncio
async def test_get_system_status(async_client):
    response = await async_client.get("/api/v1/system/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "llm_provider" in data
    assert "has_api_key" in data


@pytest.mark.asyncio
async def test_invalid_conversation_id_returns_400(async_client):
    response = await async_client.get("/api/v1/conversations/invalid-id-format")
    assert response.status_code == 400
    assert "Invalid conversation ID format" in response.json()["detail"]
