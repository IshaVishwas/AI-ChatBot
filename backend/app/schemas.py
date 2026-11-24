from typing import Optional, List, Literal, Any, Dict
from pydantic import BaseModel, Field, field_validator

class HealthResponse(BaseModel):
    status: str = "ok"
    keys_configured: int
    cache_enabled: bool

class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Unique conversation session id between 1 and 128 chars")
    message: str = Field(..., description="User message content between 1 and 4000 chars after trimming")
    system_prompt: Optional[str] = Field(None, description="Optional custom system prompt")

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        s = v.strip()
        if not (1 <= len(s) <= 128):
            raise ValueError("session_id must be between 1 and 128 characters")
        return s

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        s = v.strip()
        if len(s) == 0:
            raise ValueError("message cannot be empty")
        if len(s) > 4000:
            raise ValueError("message must be at most 4000 characters")
        return s

class ChatMetadata(BaseModel):
    resolution_source: Literal["LIVE_INFERENCE", "LLM_CACHE"]
    source: Optional[Literal["LIVE_INFERENCE", "LLM_CACHE"]] = None
    provider: Optional[str] = None
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    key_id: Optional[str] = None
    fallback_attempts: int
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    session_id: str
    reply: str
    metadata: ChatMetadata

class SessionMessageItem(BaseModel):
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None

class SessionMessagesResponse(BaseModel):
    session_id: str
    messages: List[SessionMessageItem]

class SessionSummary(BaseModel):
    session_id: str
    title: str
    message_count: int
    updated_at: Optional[str] = None

class SessionDeleteResponse(BaseModel):
    status: str
    session_id: str
    deleted_count: int
