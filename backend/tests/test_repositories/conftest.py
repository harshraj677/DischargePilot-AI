import pytest
from mongomock_motor import AsyncMongoMockClient


@pytest.fixture()
def mongo_db():
    """An in-memory Mongo-compatible database for repository unit tests."""
    client = AsyncMongoMockClient()
    return client["test_dischargepilot"]
