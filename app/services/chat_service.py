import json
import logging
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.models.schemas import (
    ChatResponseSchema,
    ConversationDetailSchema,
    ConversationSchema,
    MessageSchema,
    Role,
)
from app.services.llm_service import BaseLLMService, get_llm_service

logger = logging.getLogger(__name__)


class ChatService:
    @staticmethod
    def _is_default_title(title: str | None) -> bool:
        if not title:
            return True
        normalized = title.strip().lower()
        return normalized in {"", "new conversation", "untitled conversation"}

    async def _maybe_update_conversation_title(
        self, conv_id: str, user_content: str, conv_doc: dict[str, Any]
    ) -> dict[str, Any]:
        update_fields: dict[str, Any] = {}
        if self._is_default_title(conv_doc.get("title")):
            try:
                auto_title = await self.llm_service.generate_title(user_content)
            except Exception as exc:
                logger.warning("Failed to generate AI title for conversation %s: %s", conv_id, exc)
                auto_title = user_content[:40].strip() + ("..." if len(user_content) > 40 else "")

            if auto_title and auto_title.strip():
                update_fields["title"] = auto_title.strip()

        return update_fields

    def __init__(self, db: AsyncIOMotorDatabase, llm_service: BaseLLMService | None = None):
        self.db = db
        self.conversations_col = db.get_collection("conversations")
        self.messages_col = db.get_collection("messages")
        self.llm_service = llm_service or get_llm_service()

    async def list_conversations(self, limit: int = 50, skip: int = 0) -> list[ConversationSchema]:
        """List all conversations ordered by updated_at descending."""
        cursor = self.conversations_col.find().sort("updated_at", -1).skip(skip).limit(limit)
        conversations = []
        async for doc in cursor:
            conv_id = str(doc["_id"])
            msg_count = await self.messages_col.count_documents({"conversation_id": conv_id})
            conversations.append(
                ConversationSchema(
                    id=conv_id,
                    title=doc.get("title", "Untitled Conversation"),
                    created_at=doc.get("created_at", datetime.now(UTC)),
                    updated_at=doc.get("updated_at", datetime.now(UTC)),
                    message_count=msg_count,
                )
            )
        return conversations

    async def create_conversation(
        self, title: str | None = None, initial_message: str | None = None
    ) -> tuple[ConversationDetailSchema, ChatResponseSchema | None]:
        """Create a new conversation thread."""
        now = datetime.now(UTC)
        default_title = title.strip() if title and title.strip() else "New Conversation"

        conv_doc = {
            "title": default_title,
            "created_at": now,
            "updated_at": now,
        }
        result = await self.conversations_col.insert_one(conv_doc)
        conv_id = str(result.inserted_id)

        chat_response = None
        messages = []

        if initial_message and initial_message.strip():
            chat_response = await self.send_message(conv_id=conv_id, user_content=initial_message)
            if not title:
                updated_conv = await self.conversations_col.find_one({"_id": ObjectId(conv_id)})
                if updated_conv:
                    default_title = updated_conv.get("title", default_title)

            messages = [chat_response.user_message, chat_response.assistant_message]

        conv_detail = ConversationDetailSchema(
            id=conv_id,
            title=default_title,
            created_at=now,
            updated_at=now,
            message_count=len(messages),
            messages=messages,
        )
        return conv_detail, chat_response

    async def get_conversation_detail(self, conv_id: str) -> ConversationDetailSchema:
        """Fetch conversation details along with all messages in chronological order."""
        if not ObjectId.is_valid(conv_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid conversation ID format: '{conv_id}'",
            )

        conv_doc = await self.conversations_col.find_one({"_id": ObjectId(conv_id)})
        if not conv_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation '{conv_id}' not found.",
            )

        cursor = self.messages_col.find({"conversation_id": conv_id}).sort("timestamp", 1)
        messages = []
        async for msg_doc in cursor:
            messages.append(
                MessageSchema(
                    id=str(msg_doc["_id"]),
                    conversation_id=conv_id,
                    role=Role(msg_doc["role"]),
                    content=msg_doc["content"],
                    timestamp=msg_doc["timestamp"],
                )
            )

        return ConversationDetailSchema(
            id=conv_id,
            title=conv_doc.get("title", "Untitled Conversation"),
            created_at=conv_doc.get("created_at", datetime.now(UTC)),
            updated_at=conv_doc.get("updated_at", datetime.now(UTC)),
            message_count=len(messages),
            messages=messages,
        )

    async def send_message(self, conv_id: str, user_content: str) -> ChatResponseSchema:
        """Send user message, retrieve context history, query LLM, and persist response."""
        if not ObjectId.is_valid(conv_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid conversation ID format: '{conv_id}'",
            )

        conv_doc = await self.conversations_col.find_one({"_id": ObjectId(conv_id)})
        if not conv_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation '{conv_id}' not found.",
            )

        now = datetime.now(UTC)

        user_msg_doc = {
            "conversation_id": conv_id,
            "role": Role.USER.value,
            "content": user_content.strip(),
            "timestamp": now,
        }
        user_msg_res = await self.messages_col.insert_one(user_msg_doc)
        user_msg_id = str(user_msg_res.inserted_id)

        user_message_schema = MessageSchema(
            id=user_msg_id,
            conversation_id=conv_id,
            role=Role.USER,
            content=user_content.strip(),
            timestamp=now,
        )

        cursor = self.messages_col.find({"conversation_id": conv_id}).sort("timestamp", 1)
        history_docs = await cursor.to_list(length=100)

        llm_messages = [{"role": doc["role"], "content": doc["content"]} for doc in history_docs]

        title_update_fields = await self._maybe_update_conversation_title(
            conv_id, user_content, conv_doc
        )

        try:
            assistant_content, provider, model_used = await self.llm_service.generate_response(
                llm_messages
            )
        except Exception as e:
            logger.error("LLM generation failed for conversation %s: %s", conv_id, e)
            if title_update_fields:
                await self.conversations_col.update_one(
                    {"_id": ObjectId(conv_id)}, {"$set": {"updated_at": now, **title_update_fields}}
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"LLM Service Error: {str(e)}",
            )

        asst_now = datetime.now(UTC)
        asst_msg_doc = {
            "conversation_id": conv_id,
            "role": Role.ASSISTANT.value,
            "content": assistant_content,
            "timestamp": asst_now,
        }
        asst_msg_res = await self.messages_col.insert_one(asst_msg_doc)
        asst_msg_id = str(asst_msg_res.inserted_id)

        assistant_message_schema = MessageSchema(
            id=asst_msg_id,
            conversation_id=conv_id,
            role=Role.ASSISTANT,
            content=assistant_content,
            timestamp=asst_now,
        )

        update_fields: dict[str, Any] = {"updated_at": asst_now, **title_update_fields}
        if update_fields:
            await self.conversations_col.update_one(
                {"_id": ObjectId(conv_id)}, {"$set": update_fields}
            )

        return ChatResponseSchema(
            user_message=user_message_schema,
            assistant_message=assistant_message_schema,
            conversation_id=conv_id,
            llm_provider=provider,
            model_used=model_used,
        )

    async def send_message_stream(
        self, conv_id: str, user_content: str
    ) -> AsyncGenerator[str, None]:
        """Stream LLM tokens using Server-Sent Events (SSE) while saving response to DB."""
        if not ObjectId.is_valid(conv_id):
            yield f"data: {json.dumps({'error': f'Invalid ID format: {conv_id}'})}\n\n"
            return

        conv_doc = await self.conversations_col.find_one({"_id": ObjectId(conv_id)})
        if not conv_doc:
            yield f"data: {json.dumps({'error': f'Conversation {conv_id} not found'})}\n\n"
            return

        now = datetime.now(UTC)

        user_msg_doc = {
            "conversation_id": conv_id,
            "role": Role.USER.value,
            "content": user_content.strip(),
            "timestamp": now,
        }
        await self.messages_col.insert_one(user_msg_doc)

        cursor = self.messages_col.find({"conversation_id": conv_id}).sort("timestamp", 1)
        history_docs = await cursor.to_list(length=100)
        llm_messages = [{"role": doc["role"], "content": doc["content"]} for doc in history_docs]

        accumulated_content = []
        title_update_fields = await self._maybe_update_conversation_title(
            conv_id, user_content, conv_doc
        )
        try:
            async for chunk in self.llm_service.generate_response_stream(llm_messages):
                accumulated_content.append(chunk)
                yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"
        except Exception as e:
            logger.error("LLM streaming failed for conv %s: %s", conv_id, e)
            if title_update_fields:
                await self.conversations_col.update_one(
                    {"_id": ObjectId(conv_id)}, {"$set": {"updated_at": now, **title_update_fields}}
                )
            yield f"data: {json.dumps({'error': str(e), 'done': True})}\n\n"
            return

        full_response = "".join(accumulated_content)

        asst_now = datetime.now(UTC)
        asst_msg_doc = {
            "conversation_id": conv_id,
            "role": Role.ASSISTANT.value,
            "content": full_response,
            "timestamp": asst_now,
        }
        asst_res = await self.messages_col.insert_one(asst_msg_doc)
        asst_id = str(asst_res.inserted_id)

        update_fields: dict[str, Any] = {"updated_at": asst_now, **title_update_fields}
        if update_fields:
            await self.conversations_col.update_one(
                {"_id": ObjectId(conv_id)}, {"$set": update_fields}
            )

        done_payload = {
            "content": "",
            "done": True,
            "message_id": asst_id,
            "conversation_id": conv_id,
            "title": update_fields.get("title"),
        }
        yield f"data: {json.dumps(done_payload)}\n\n"

    async def delete_conversation(self, conv_id: str) -> bool:
        """Delete conversation and all its messages."""
        if not ObjectId.is_valid(conv_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid conversation ID format: '{conv_id}'",
            )

        result = await self.conversations_col.delete_one({"_id": ObjectId(conv_id)})
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation '{conv_id}' not found.",
            )

        await self.messages_col.delete_many({"conversation_id": conv_id})
        return True
