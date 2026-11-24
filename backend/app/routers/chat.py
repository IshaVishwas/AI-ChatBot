from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Message
from app.schemas import ChatRequest, ChatResponse, ChatMetadata
from app.services.llm_service import llm_service

router = APIRouter(tags=["Chat"])

@router.post("/chat", response_model=ChatResponse)
def post_chat(
    request: ChatRequest,
    x_simulate_failure: Optional[str] = Header(None, alias="X-Simulate-Failure"),
    db: Session = Depends(get_db)
):
    """
    POST /chat endpoint:
    - Validates request body
    - Retrieves multi-turn conversation history for session_id
    - Constructs model message sequence with optional system prompt
    - Executes LLM inference with LiteLLM caching & key failover
    - Persists user and assistant messages in SQLite on success
    - Failed requests are NOT persisted
    """
    # 1. Fetch conversation history for this session (oldest first)
    stored_messages = (
        db.query(Message)
        .filter(Message.session_id == request.session_id)
        .order_by(Message.id.asc())
        .all()
    )

    # 2. Build model messages payload
    model_messages = []
    if request.system_prompt and request.system_prompt.strip():
        model_messages.append({"role": "system", "content": request.system_prompt.strip()})

    for msg in stored_messages:
        model_messages.append({"role": msg.role, "content": msg.content})

    model_messages.append({"role": "user", "content": request.message})

    # 3. Call LLM Service (handles cache check, key rotation, failure simulation)
    reply, metadata_dict = llm_service.execute_chat(
        messages=model_messages,
        simulation_header=x_simulate_failure,
        session_id=request.session_id,
    )

    # 4. Only on success, persist user message and assistant message
    try:
        user_msg = Message(
            session_id=request.session_id,
            role="user",
            content=request.message,
            metadata_json=None
        )
        assistant_msg = Message(
            session_id=request.session_id,
            role="assistant",
            content=reply,
            metadata_json=metadata_dict
        )
        db.add(user_msg)
        db.add(assistant_msg)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist conversation history"
        )

    metadata = ChatMetadata(**metadata_dict)
    return ChatResponse(
        session_id=request.session_id,
        reply=reply,
        metadata=metadata
    )

