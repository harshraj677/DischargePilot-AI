from __future__ import annotations

import time
from abc import ABC, abstractmethod

from app.knowledge.repository import KnowledgeRepository
from app.safety.models import ValidationResult
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BaseValidator(ABC):
    """
    Abstract base for all safety validators.

    Validators run synchronously (no Claude calls) for speed and reliability.
    Claude-assisted validation is handled only in SafetyValidationEngine.
    """

    name: str = "base_validator"

    def run(self, kb: KnowledgeRepository) -> ValidationResult:
        """Entry point — wraps validate() with timing and error safety."""
        start = time.time()
        try:
            result = self.validate(kb)
            result.execution_time_ms = (time.time() - start) * 1000
            logger.debug(
                "Validator completed",
                validator=self.name,
                passed=result.passed,
                findings=len(result.findings),
                flags=len(result.review_flags),
                ms=round(result.execution_time_ms, 1),
            )
            return result
        except Exception as exc:
            duration = (time.time() - start) * 1000
            logger.error("Validator raised exception", validator=self.name, error=str(exc))
            from app.models.enums import SafetySeverity
            return ValidationResult(
                validator_name=self.name,
                passed=False,
                severity=SafetySeverity.HIGH,
                execution_time_ms=duration,
                error=f"Validator error: {exc}",
            )

    @abstractmethod
    def validate(self, kb: KnowledgeRepository) -> ValidationResult:
        ...
