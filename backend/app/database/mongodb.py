"""
MongoDB connection management for Phase 1 permanent storage + analytics.

This is an additive persistence layer alongside the existing SQLite/SQLAlchemy
stack (app/db/). MongoDB is never required for the application to function —
every caller must treat a disconnected/unavailable Mongo as a soft failure
(log + skip) rather than letting it propagate and break the SQLite-backed
request flow.
"""
from __future__ import annotations

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import PyMongoError

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MongoDBManager:
    """Singleton wrapper around a Motor client. Connection failures are logged, never raised."""

    _instance: Optional["MongoDBManager"] = None

    def __new__(cls) -> "MongoDBManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._client = None
            cls._instance._db = None
        return cls._instance

    def __init__(self) -> None:
        self._client: Optional[AsyncIOMotorClient] = getattr(self, "_client", None)
        self._db: Optional[AsyncIOMotorDatabase] = getattr(self, "_db", None)

    @property
    def is_connected(self) -> bool:
        return self._db is not None

    async def connect(self) -> bool:
        """
        Establish the Mongo connection and verify it with a ping.

        Returns True on success, False otherwise. Never raises — a missing
        or unreachable MONGODB_URI must not prevent the rest of the
        application from starting.
        """
        if not settings.MONGODB_URI:
            logger.warning("MONGODB_URI not configured — MongoDB persistence disabled")
            return False

        try:
            self._client = AsyncIOMotorClient(
                settings.MONGODB_URI,
                connectTimeoutMS=settings.MONGODB_CONNECT_TIMEOUT_MS,
                serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
            )
            await self._client.admin.command("ping")
            self._db = self._client[settings.MONGODB_DATABASE]
            logger.info("MongoDB connected", database=settings.MONGODB_DATABASE)
            return True
        except Exception as exc:
            logger.error("MongoDB connection failed", error=str(exc))
            self._client = None
            self._db = None
            return False

    async def disconnect(self) -> None:
        if self._client is not None:
            self._client.close()
            logger.info("MongoDB connection closed")
        self._client = None
        self._db = None

    def get_database(self) -> Optional[AsyncIOMotorDatabase]:
        """Returns None when Mongo is unavailable — callers must handle that gracefully."""
        return self._db

    async def create_indexes(self) -> None:
        """Create all indexes described in the Phase 1 spec. Safe to call repeatedly."""
        db = self._db
        if db is None:
            logger.warning("Skipping MongoDB index creation — not connected")
            return

        try:
            await db.patients.create_index("patient_id", unique=True)
            await db.patients.create_index("created_at")

            await db.documents.create_index("patient_id")
            await db.documents.create_index("created_at")

            await db.summaries.create_index("patient_id")
            await db.summaries.create_index("created_at")

            await db.findings.create_index("summary_id")
            await db.findings.create_index("severity")
            await db.findings.create_index("category")
            await db.findings.create_index("created_at")

            await db.review_actions.create_index("finding_id")
            await db.review_actions.create_index("timestamp")

            logger.info("MongoDB indexes created / verified")
        except PyMongoError as exc:
            logger.error("MongoDB index creation failed", error=str(exc))


mongodb_manager = MongoDBManager()
