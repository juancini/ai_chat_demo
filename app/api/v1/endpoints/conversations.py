from fastapi import APIRouter, Depends, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongodb import get_database
from app.models.schemas import (
    ConversationDetailSchema,
    ConversationSchema,
    CreateConversationRequest,
)
from app.services.chat_service import ChatService

router = APIRouter(prefix="/conversations", tags=["Conversations"])


@router.get("", response_model=list[ConversationSchema])
async def list_conversations(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """List all chat conversations sorted by recent activity."""
    service = ChatService(db)
    return await service.list_conversations(limit=limit, skip=skip)


@router.post("", response_model=ConversationDetailSchema, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: CreateConversationRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Create a new chat conversation thread."""
    service = ChatService(db)
    conv_detail, _ = await service.create_conversation(
        title=payload.title, initial_message=payload.initial_message
    )
    return conv_detail


@router.get("/{conv_id}", response_model=ConversationDetailSchema)
async def get_conversation(
    conv_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Retrieve details and complete message history for a conversation."""
    service = ChatService(db)
    return await service.get_conversation_detail(conv_id)


@router.delete("/{conv_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conv_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Delete a conversation thread and all associated message history."""
    service = ChatService(db)
    await service.delete_conversation(conv_id)
    return None
