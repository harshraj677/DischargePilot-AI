from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import List
import json

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    APP_NAME: str = "DischargePilot AI"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/dischargepilot.db"
    DATABASE_ECHO: bool = False

    # File Storage
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = [".pdf"]

    # Claude API
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    CLAUDE_CLASSIFICATION_THRESHOLD: float = 0.60

    # Processing
    MAX_EXTRACTION_RETRIES: int = 3
    EXTRACTION_TIMEOUT_SECONDS: int = 60
    MIN_PAGE_TEXT_LENGTH: int = 10

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_DIR: Path = BASE_DIR / "logs"

    # API
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    @property
    def max_file_size_bytes(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024

    @property
    def upload_dir_str(self) -> str:
        return str(self.UPLOAD_DIR)


settings = Settings()
