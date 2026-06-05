"""
CorrectionMemory — SQLite-backed storage for correction patterns.
Learns which abbreviations, vague phrases, and formatting issues
appear most frequently across doctor reviews, then injects them
as prompt hints in future generations.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.db.models import CorrectionMemoryEntry as CorrectionMemoryEntryORM
from app.learning.models import CorrectionMemoryEntry
from app.utils.logging import get_logger

logger = get_logger(__name__)


class CorrectionMemory:
    """
    Manages a persistent store of correction patterns.
    Entries are stored in SQLite via the existing ORM infrastructure.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def store_correction(
        self,
        pattern: str,
        correction: str,
        section: str,
        frequency_increment: int = 1,
    ) -> CorrectionMemoryEntry:
        """
        Store a correction pattern or increment its frequency if it already exists.

        Args:
            pattern: The problematic phrase/abbreviation (e.g. "HTN").
            correction: The corrected form (e.g. "Hypertension").
            section: The section name where this pattern occurs.
            frequency_increment: How much to increment the frequency counter.

        Returns:
            The updated or newly created CorrectionMemoryEntry.
        """
        existing = (
            self._db.query(CorrectionMemoryEntryORM)
            .filter(
                CorrectionMemoryEntryORM.pattern == pattern,
                CorrectionMemoryEntryORM.section_name == section,
            )
            .first()
        )

        if existing:
            existing.frequency += frequency_increment
            existing.correction = correction  # Update in case it improved
            existing.last_seen = datetime.utcnow()
            self._db.commit()
            self._db.refresh(existing)
            return _orm_to_model(existing)

        new_entry = CorrectionMemoryEntryORM(
            pattern=pattern[:500],
            correction=correction[:1000],
            section_name=section[:100],
            frequency=frequency_increment,
            last_seen=datetime.utcnow(),
        )
        self._db.add(new_entry)
        self._db.commit()
        self._db.refresh(new_entry)
        logger.debug("Stored correction", pattern=pattern[:50], section=section)
        return _orm_to_model(new_entry)

    def get_top_corrections(
        self,
        section: Optional[str] = None,
        limit: int = 10,
    ) -> List[CorrectionMemoryEntry]:
        """
        Get the top correction patterns by frequency.

        Args:
            section: Filter by section name (optional).
            limit: Maximum number of results.

        Returns:
            List of CorrectionMemoryEntry ordered by frequency descending.
        """
        query = self._db.query(CorrectionMemoryEntryORM)
        if section:
            query = query.filter(CorrectionMemoryEntryORM.section_name == section)
        rows = query.order_by(CorrectionMemoryEntryORM.frequency.desc()).limit(limit).all()
        return [_orm_to_model(row) for row in rows]

    def get_prompt_hints(self, section: str) -> str:
        """
        Format top corrections for a section into a concise prompt hint string.

        Args:
            section: The section name to get hints for.

        Returns:
            A formatted string of correction hints, or empty string if none.
        """
        corrections = self.get_top_corrections(section=section, limit=5)
        if not corrections:
            corrections = self.get_top_corrections(limit=5)

        if not corrections:
            return ""

        lines = [f"Common corrections seen in this section:"]
        for c in corrections:
            lines.append(f"  - '{c.pattern}' should be '{c.correction}' (seen {c.frequency}x)")

        return "\n".join(lines)


def _orm_to_model(row: CorrectionMemoryEntryORM) -> CorrectionMemoryEntry:
    return CorrectionMemoryEntry(
        id=row.id,
        pattern=row.pattern,
        correction=row.correction,
        section_name=row.section_name,
        frequency=row.frequency,
        last_seen=row.last_seen,
    )
