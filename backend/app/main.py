import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import init_db
from app.routers import health_router, chat_router, sessions_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize database schema
    logger.info("Initializing SQLite database schema...")
    init_db()
    logger.info(f"Backend started with {len(settings.key_list)} configured keys.")
    yield
    # Shutdown
    logger.info("Backend shutting down.")

app = FastAPI(
    title="Lyftr AI Chatbot Gateway API",
    version="1.0.0",
    description="Full-stack AI Chatbot with LiteLLM Gateway, Failover, Caching, and SQLite persistence",
    lifespan=lifespan
)

# CORS Configuration
# Allowed origins for Vite dev server (5173), Docker/preview (3000), and environment overrides
allowed_origins = settings.allowed_origins_list
if not allowed_origins:
    cors_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ]
else:
    cors_origins = allowed_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "X-Simulate-Failure",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With"
    ],
)

# Custom Exception Handlers to guarantee clean JSON errors without leaking stack traces
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first_error = errors[0]["msg"] if errors else "Validation error"
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": first_error}
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )

# Include Routers
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(sessions_router)

