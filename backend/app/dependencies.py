from typing import Generator
from sqlalchemy.orm import Session
from app.db.database import SessionLocal
from app.config import settings


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_settings():
    return settings
