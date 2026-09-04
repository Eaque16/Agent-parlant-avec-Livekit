"""Corps des requêtes HTTP liées aux conversations."""

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    channel: str = Field(default="web", pattern="^(web|phone)$")
    caller_ref: str | None = Field(default=None, max_length=80)


class MessageCreate(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class RealtimeTokenRequest(BaseModel):
    conversation_id: str


class AgentEventCreate(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(min_length=1, max_length=8000)
    event_type: str = Field(pattern="^(transcript|agent_reply|error)$")
