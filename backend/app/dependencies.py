from typing import Generator, Optional
from sqlalchemy.orm import Session
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.db.database import SessionLocal
from app.config import settings
from app.database.mongodb import mongodb_manager


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_settings():
    return settings


def get_mongo_database() -> Optional[AsyncIOMotorDatabase]:
    """Returns None when MongoDB is unavailable — callers must handle that gracefully."""
    return mongodb_manager.get_database()
