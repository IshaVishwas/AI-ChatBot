import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

# Parse SQLite DB directory and ensure it exists
db_url = settings.DATABASE_URL

# Normalize relative SQLite paths so database location is deterministic
if (
    db_url.startswith("sqlite:///")
    and not db_url.startswith("sqlite:////")
    and not db_url.startswith("sqlite:///:memory:")
):
    raw_path = db_url.replace("sqlite:///", "")
    backend_dir = Path(__file__).resolve().parent.parent
    target_path = (backend_dir / raw_path).resolve()
    db_url = f"sqlite:///{target_path.as_posix()}"

if db_url.startswith("sqlite:///"):
    db_path = db_url.replace("sqlite:///", "")
    # If absolute or relative path, ensure parent directory exists
    dir_name = os.path.dirname(db_path)
    if dir_name:
        try:
            os.makedirs(dir_name, exist_ok=True)
        except OSError:
            pass

engine = create_engine(
    db_url,
    connect_args={"check_same_thread": False} if "sqlite" in db_url else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from app import models  # Ensure models are loaded
    Base.metadata.create_all(bind=engine)

