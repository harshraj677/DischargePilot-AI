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

    # File Storage
    UPLOAD_DIR: Path = BASE_DIR / "uploads"
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".jpg", ".jpeg", ".png", ".webp"]

    # Google Gemini API
    GEMINI_API_KEY: str = ""
    GEMINI_VISION_MODEL: str = "gemini-2.5-pro"
    GEMINI_TEXT_MODEL: str = "gemini-2.5-pro"
    GEMINI_CLASSIFICATION_THRESHOLD: float = 0.60

    # Anthropic Claude API (primary Vision OCR provider)
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_VISION_MODEL: str = "claude-opus-4-8"

    # Processing
    MAX_EXTRACTION_RETRIES: int = 3
    EXTRACTION_TIMEOUT_SECONDS: int = 60
    MIN_PAGE_TEXT_LENGTH: int = 10

    # OCR (Claude Vision is the primary provider for scanned/image-only PDFs,
    # with Gemini/EasyOCR/Tesseract as fallbacks)
    OCR_ENABLED: bool = True
    OCR_PRIMARY_PROVIDER: str = "claude"

    # Agent
    AGENT_MAX_ITERATIONS: int = 15
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
