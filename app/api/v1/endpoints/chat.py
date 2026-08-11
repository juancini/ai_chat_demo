from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.db.mongodb import get_database
from app.models.schemas import ChatResponseSchema, SendMessageRequest, SystemStatusSchema
from app.services.chat_service import ChatService

router = APIRouter(tags=["Chat & System"])


@router.post(
    "/conversations/{conv_id}/messages",
    response_model=ChatResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def send_message(
    conv_id: str,
    payload: SendMessageRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Send a message to an existing conversation thread and generate LLM response."""
    service = ChatService(db)
    return await service.send_message(conv_id=conv_id, user_content=payload.content)


@router.post("/conversations/{conv_id}/messages/stream")
async def send_message_stream(
    conv_id: str,
    payload: SendMessageRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Stream LLM response tokens in real-time using Server-Sent Events (SSE)."""
    service = ChatService(db)
    return StreamingResponse(
        service.send_message_stream(conv_id=conv_id, user_content=payload.content),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/system/status", response_model=SystemStatusSchema)
async def get_system_status():
    """Check application system status, LLM mode, and API key configuration."""
    has_key = bool(settings.OPENROUTER_API_KEY and settings.OPENROUTER_API_KEY.strip())
    provider = "openrouter" if has_key else "mock"
    return SystemStatusSchema(
        status="healthy",
        llm_provider=provider,
        model_configured=settings.OPENROUTER_MODEL if has_key else "mock-demo-v1",
        has_api_key=has_key,
    )
