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
        extra="ignore",
    )

    # Application
    APP_NAME: str = "DischargePilot AI"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = f"sqlite:///{BASE_DIR}/dischargepilot.db"
    DATABASE_ECHO: bool = False

    # MongoDB (Phase 1 permanent storage + analytics — additive to SQLite)
    MONGODB_URI: str = ""
    MONGODB_DATABASE: str = "dischargepilot"
    MONGODB_CONNECT_TIMEOUT_MS: int = 5000
    MONGODB_SERVER_SELECTION_TIMEOUT_MS: int = 5000

    # File Storage
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".jpg", ".jpeg", ".png", ".webp"]

    # Groq API (primary AI provider for the whole platform)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_VISION_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
    GROQ_MAX_RETRIES: int = 3
    GROQ_RETRY_BASE_DELAY: float = 2.0
    GROQ_CACHE_ENABLED: bool = True

    # Anthropic Claude API (secondary OCR fallback provider)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_VISION_MODEL: str = "claude-opus-4-8"
    ANTHROPIC_TEXT_MODEL: str = "claude-sonnet-4-6"
    CLAUDE_MODEL: str = "claude-sonnet-4-6"
    CLAUDE_MAX_RETRIES: int = 3
    CLAUDE_RETRY_BASE_DELAY: float = 2.0
    CLAUDE_RESPONSE_CACHE_ENABLED: bool = True
    CLASSIFICATION_CONFIDENCE_THRESHOLD: float = 0.60

    # Processing
    MAX_EXTRACTION_RETRIES: int = 3
    EXTRACTION_TIMEOUT_SECONDS: int = 60
    MIN_PAGE_TEXT_LENGTH: int = 10

    # OCR (Groq Vision is the primary provider for scanned/image-only PDFs,
    # with Claude Vision, EasyOCR, and Tesseract as fallbacks)
    OCR_ENABLED: bool = True
    OCR_PRIMARY_PROVIDER: str = "groq"

    # Agent
    AGENT_MAX_ITERATIONS: int = 20
    AGENT_TOOL_TIMEOUT_SECONDS: int = 120

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
