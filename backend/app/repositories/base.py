from __future__ import annotations

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorDatabase


class MongoRepository:
    """
    Shared base for Mongo-backed repositories.

    `collection` is None whenever Mongo is unavailable (no MONGODB_URI, or the
    connection failed at startup) — every repository method must check for
    that and degrade gracefully instead of raising, so a Mongo outage never
    takes down the SQLite-backed request flow.
    """

    collection_name: str = ""

    def __init__(self, db: Optional[AsyncIOMotorDatabase]):
        self._db = db
        self.collection: Optional[AsyncIOMotorCollection] = (
            db[self.collection_name] if db is not None else None
        )
