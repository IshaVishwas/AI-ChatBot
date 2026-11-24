from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database import get_db
from app.models import Message
from app.schemas import (
    SessionMessagesResponse,
    SessionMessageItem,
    SessionSummary,
    SessionDeleteResponse
)

router = APIRouter(tags=["Sessions"])

@router.get("/sessions", response_model=List[SessionSummary])
def list_sessions(db: Session = Depends(get_db)):
    """
    GET /sessions:
    Returns all stored conversations ordered by most recent activity first.
    Generates human-readable titles from the first user message.
    """
    # Group messages by session_id
    grouped = (
        db.query(
            Message.session_id,
            func.count(Message.id).label("msg_count"),
            func.max(Message.created_at).label("last_active")
        )
        .group_by(Message.session_id)
        .order_by(func.max(Message.created_at).desc())
        .all()
    )

    summaries = []
    for item in grouped:
        sess_id = item.session_id
        # Get first user message for a readable title
        first_user_msg = (
            db.query(Message)
            .filter(Message.session_id == sess_id, Message.role == "user")
            .order_by(Message.id.asc())
            .first()
        )
        if first_user_msg and first_user_msg.content.strip():
            raw_title = first_user_msg.content.strip().split("\n")[0]
            title = (raw_title[:45] + "...") if len(raw_title) > 48 else raw_title
        else:
            title = f"Chat {sess_id[:12]}"

        updated_str = None
        if item.last_active:
            dt = item.last_active
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            updated_str = dt.isoformat().replace("+00:00", "Z")

        summaries.append(SessionSummary(
            session_id=sess_id,
            title=title,
            message_count=item.msg_count,
            updated_at=updated_str
        ))

    return summaries

@router.get("/sessions/{session_id}/messages", response_model=SessionMessagesResponse)
def get_session_messages(session_id: str, db: Session = Depends(get_db)):
    """
    GET /sessions/{session_id}/messages:
    Returns stored messages oldest first for given session_id.
    Excludes system prompts from history.
    Returns HTTP 404 if session is unknown / has no stored messages.
    """
    messages = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.id.asc())
        .all()
    )

    if not messages:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="session not found"
        )

    # Filter out system messages if any, format oldest first
    result_messages = []
    for msg in messages:
        if msg.role in ("user", "assistant"):
            result_messages.append(SessionMessageItem(
                role=msg.role,
                content=msg.content,
                metadata=msg.metadata_json if msg.role == "assistant" else None
            ))

    return SessionMessagesResponse(
        session_id=session_id,
        messages=result_messages
    )

@router.delete("/sessions/{session_id}", response_model=SessionDeleteResponse)
def delete_session(session_id: str, db: Session = Depends(get_db)):
    """
    DELETE /sessions/{session_id}:
    Deletes all messages for given session_id.
    """
    count = db.query(Message).filter(Message.session_id == session_id).delete()
    db.commit()
    return SessionDeleteResponse(
        status="deleted",
        session_id=session_id,
        deleted_count=count
    )

