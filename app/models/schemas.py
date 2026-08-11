from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class Role(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageSchema(BaseModel):
    id: str = Field(..., description="Unique message ID")
    conversation_id: str = Field(..., description="ID of parent conversation")
    role: Role = Field(..., description="Role of message sender")
    content: str = Field(..., description="Message text content")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )


class ConversationSchema(BaseModel):
    id: str = Field(..., description="Unique conversation ID")
    title: str = Field(..., description="Conversation title")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    message_count: int = Field(default=0, description="Total messages in conversation")


class ConversationDetailSchema(ConversationSchema):
    messages: list[MessageSchema] = Field(
        default_factory=list, description="List of messages in conversation"
    )


class CreateConversationRequest(BaseModel):
    title: str | None = Field(None, description="Optional custom title for the conversation")
    initial_message: str | None = Field(
        None, description="Optional first user message to trigger assistant response"
    )


class SendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Message content to send to chatbot")


class ChatResponseSchema(BaseModel):
    user_message: MessageSchema = Field(..., description="Saved user message")
    assistant_message: MessageSchema = Field(..., description="Generated assistant message")
    conversation_id: str = Field(..., description="ID of current conversation")
    llm_provider: str = Field(..., description="Provider used ('openrouter' or 'mock')")
    model_used: str = Field(..., description="Name of LLM model used")


class SystemStatusSchema(BaseModel):
    status: str
    llm_provider: str
    model_configured: str
    has_api_key: bool
