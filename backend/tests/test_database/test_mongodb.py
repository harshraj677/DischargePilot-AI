import pytest

from app.config import settings
from app.database.mongodb import MongoDBManager


@pytest.fixture()
def manager():
    """Fresh MongoDBManager instance, bypassing the process-wide singleton."""
    mgr = MongoDBManager.__new__(MongoDBManager)
    mgr._client = None
    mgr._db = None
    return mgr


class TestMongoDBManager:
    def test_singleton_returns_same_instance(self):
        assert MongoDBManager() is MongoDBManager()

    def test_get_database_is_none_before_connect(self, manager):
        assert manager.get_database() is None
        assert manager.is_connected is False

    @pytest.mark.asyncio
    async def test_connect_without_uri_returns_false(self, manager, monkeypatch):
        monkeypatch.setattr(settings, "MONGODB_URI", "")
        ok = await manager.connect()
        assert ok is False
        assert manager.get_database() is None

    @pytest.mark.asyncio
    async def test_connect_unreachable_host_returns_false_and_does_not_raise(self, manager, monkeypatch):
        monkeypatch.setattr(settings, "MONGODB_URI", "mongodb://localhost:1")
        monkeypatch.setattr(settings, "MONGODB_SERVER_SELECTION_TIMEOUT_MS", 200)
        monkeypatch.setattr(settings, "MONGODB_CONNECT_TIMEOUT_MS", 200)
        ok = await manager.connect()
        assert ok is False
        assert manager.get_database() is None
        assert manager.is_connected is False

    @pytest.mark.asyncio
    async def test_create_indexes_skips_safely_when_not_connected(self, manager):
        # Must not raise even though there's no database to index.
        await manager.create_indexes()

    @pytest.mark.asyncio
    async def test_disconnect_when_never_connected_is_safe(self, manager):
        await manager.disconnect()
        assert manager.get_database() is None
