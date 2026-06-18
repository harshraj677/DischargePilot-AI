from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from sqlalchemy.engine import Engine
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=settings.DATABASE_ECHO,
)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def create_tables() -> None:
    from app.db import models as _  # noqa: F401 — ensure models are registered
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created / verified")

    # Migration check for new columns in agent_runs table
    from sqlalchemy import inspect, text
    try:
        inspector = inspect(engine)
        columns = [col["name"] for col in inspector.get_columns("agent_runs")]
        with engine.begin() as conn:
            if "stack_trace" not in columns:
                conn.execute(text("ALTER TABLE agent_runs ADD COLUMN stack_trace TEXT"))
                logger.info("Added stack_trace column to agent_runs table")
            if "failed_component" not in columns:
                conn.execute(text("ALTER TABLE agent_runs ADD COLUMN failed_component VARCHAR(100)"))
                logger.info("Added failed_component column to agent_runs table")
    except Exception as exc:
        logger.error(f"Migration check failed: {exc}")



def drop_tables() -> None:
    Base.metadata.drop_all(bind=engine)
    logger.warning("All database tables dropped")
