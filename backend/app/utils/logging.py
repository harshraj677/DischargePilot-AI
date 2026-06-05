import sys
import os
import json
from loguru import logger
from pathlib import Path
from app.config import settings

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return

    logger.remove()

    log_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    )

    logger.add(sys.stdout, format=log_format, level=settings.LOG_LEVEL, colorize=True)

    log_file = Path(settings.LOG_DIR) / "dischargepilot.log"
    logger.add(
        str(log_file),
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{line} | {message} | {extra}",
        level=settings.LOG_LEVEL,
        rotation="50 MB",
        retention="30 days",
        compression="zip",
        serialize=False,
    )

    audit_file = Path(settings.LOG_DIR) / "audit.log"
    logger.add(
        str(audit_file),
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {message} | {extra}",
        level="INFO",
        filter=lambda record: record["extra"].get("audit", False),
        rotation="100 MB",
        retention="90 days",
    )

    _configured = True


def get_logger(name: str):
    return logger.bind(module=name)


class AuditLogger:
    def __init__(self, module: str):
        self._logger = logger.bind(module=module, audit=True)

    def log_upload(self, patient_id: str, filename: str, doc_type: str, file_size: int) -> None:
        self._logger.info(
            "DOCUMENT_UPLOADED",
            event="DOCUMENT_UPLOADED",
            patient_id=patient_id,
            filename=filename,
            document_type=doc_type,
            file_size_bytes=file_size,
        )

    def log_extraction_start(self, document_id: str, filename: str) -> None:
        self._logger.info(
            "EXTRACTION_STARTED",
            event="EXTRACTION_STARTED",
            document_id=document_id,
            filename=filename,
        )

    def log_extraction_complete(
        self, document_id: str, filename: str, pages: int, duration_ms: float
    ) -> None:
        self._logger.info(
            "EXTRACTION_COMPLETED",
            event="EXTRACTION_COMPLETED",
            document_id=document_id,
            filename=filename,
            pages_extracted=pages,
            duration_ms=round(duration_ms, 2),
        )

    def log_extraction_failure(self, document_id: str, filename: str, error: str) -> None:
        self._logger.error(
            "EXTRACTION_FAILED",
            event="EXTRACTION_FAILED",
            document_id=document_id,
            filename=filename,
            error=error,
        )

    def log_classification(
        self, document_id: str, doc_type: str, confidence: float, method: str
    ) -> None:
        self._logger.info(
            "DOCUMENT_CLASSIFIED",
            event="DOCUMENT_CLASSIFIED",
            document_id=document_id,
            classified_type=doc_type,
            confidence=round(confidence, 3),
            method=method,
        )

    def log_patient_created(self, patient_id: str, mrn: str) -> None:
        self._logger.info(
            "PATIENT_CREATED",
            event="PATIENT_CREATED",
            patient_id=patient_id,
            mrn=mrn,
        )
