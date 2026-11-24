from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.config import settings
from app.schemas import HealthResponse

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)):
    """
    Health check endpoint:
    Verifies backend is running, database is reachable, and API key pool is configured.
    """
    # Verify DB connectivity
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection failure"
        )

    # Verify keys configured
    keys_count = len(settings.key_list)
    if keys_count < 2:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="At least 2 API keys must be configured in key pool"
        )

    return HealthResponse(
        status="ok",
        keys_configured=keys_count,
        cache_enabled=settings.LITELLM_CACHE_ENABLED
    )

