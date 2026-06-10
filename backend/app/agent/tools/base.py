from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

from app.claude.agent_client import ClaudeAgentClient
from sqlalchemy.orm import Session

from app.agent.models import AgentState, AgentTask, ToolResult
from app.config import Settings
from app.db.repositories.document_repo import DocumentRepository
from app.knowledge.extraction_engine import ExtractionResult, get_extraction_engine
from app.knowledge.models import EvidencedFact
from app.knowledge.repository import KnowledgeRepository
from app.models.document import PageChunk
from app.utils.json_parsing import parse_json_response
from app.utils.logging import get_logger

logger = get_logger(__name__)


class BaseTool(ABC):
    """
    Abstract base for all clinical extraction and analysis tools.

    Every tool:
    - Receives the current AgentState and KnowledgeRepository
    - May read from the DB to get document page chunks
    - Updates the KnowledgeRepository with its findings
    - Returns a ToolResult describing what it did
    - NEVER raises — all failures return success=False
    """

    name: str = "base_tool"
    description: str = "Base tool"

    def __init__(self, client: ClaudeAgentClient, settings: Settings) -> None:
        self.client = client
        self.settings = settings

    @abstractmethod
    async def execute(
        self,
        task: AgentTask,
        state: AgentState,
        kb: KnowledgeRepository,
        db: Session,
    ) -> ToolResult:
        ...

    # ── Shared helpers ───────────────────────────────────────────────────────────

    def _get_document_text(
        self,
        doc_id: str,
        db: Session,
        max_chars: int = 15_000,
    ) -> Tuple[str, str, str]:
        """
        Return (formatted_text, document_name, document_type) for one document.
        Formats each page with a [Page N] header for Claude's reference.
        """
        repo = DocumentRepository(db)
        chunks: List[PageChunk] = repo.get_page_chunks(doc_id)

        if not chunks:
            return "", "unknown", "unknown"

        doc_name = chunks[0].document_name or "unknown"
        doc_type = chunks[0].document_type.value if hasattr(chunks[0].document_type, "value") else str(chunks[0].document_type)

        pages = []
        total = 0
        for chunk in chunks:
            if chunk.is_empty:
                continue
            snippet = chunk.text[:3000]
            pages.append(f"[Page {chunk.page_number}]\n{snippet}")
            total += len(snippet)
            if total >= max_chars:
                break

        return "\n\n".join(pages), doc_name, doc_type

    def _build_combined_text(
        self,
        document_ids: List[str],
        db: Session,
        max_docs: int = 4,
        max_chars_per_doc: int = 10_000,
    ) -> List[Tuple[str, str, str, str]]:
        """
        Return list of (doc_id, doc_name, doc_type, formatted_text) for all documents.
        Limits total context to prevent token overflow.
        """
        results = []
        for doc_id in document_ids[:max_docs]:
            text, name, dtype = self._get_document_text(doc_id, db, max_chars=max_chars_per_doc)
            if text:
                results.append((doc_id, name, dtype, text))
        return results

    def _combined_text_block(self, doc_list: List[Tuple[str, str, str, str]]) -> str:
        """Join (doc_id, doc_name, doc_type, text) tuples into one labeled text block."""
        sections = [f"=== Document: {name} (type: {dtype}) ===\n{text}" for _, name, dtype, text in doc_list]
        return "\n\n".join(sections)

    async def _get_consolidated_extraction(
        self,
        doc_list: List[Tuple[str, str, str, str]],
    ) -> ExtractionResult:
        """
        Run (or reuse the cached result of) the single Clinical Knowledge
        Extraction Engine call for this document set (STEP 3 / STEP 5).

        May raise ClaudeUnavailableError — callers should catch it the same
        way they handle their own direct generate_content() calls.
        """
        engine = get_extraction_engine()
        combined = self._combined_text_block(doc_list)
        return await engine.extract(combined, self.client)

    def _make_evidenced_fact(
        self,
        value: str,
        confidence: float,
        source_doc_id: str,
        source_doc_name: str,
        page_number: int,
        evidence: str,
    ) -> EvidencedFact:
        return EvidencedFact(
            value=value,
            confidence=min(1.0, max(0.0, confidence)),
            source_document=source_doc_name,
            source_document_id=source_doc_id,
            page_number=max(1, page_number),
            evidence=evidence[:500],
        )

    def _parse_json_response(self, text: str) -> Optional[Dict[str, Any]]:
        return parse_json_response(text)

    def _count_tokens(self, text: str) -> int:
        return len(text) // 4  # Rough estimate

    def _claude_unavailable_result(self, task: AgentTask, state: AgentState, exc: Exception) -> ToolResult:
        """
        Claude was unavailable after all retries. Flag the run for manual
        review (so a human catches the gap) without crashing or stopping
        the agent loop.
        """
        reason = f"{self.name}: Claude unavailable, manual review required ({exc})"
        if reason not in state.escalation_reasons:
            state.escalation_reasons.append(reason)
        return self._empty_result(task, f"Claude unavailable: {exc}")

    def _empty_result(self, task: AgentTask, reason: str) -> ToolResult:
        return ToolResult(
            task_id=task.task_id,
            tool_name=self.name,
            success=False,
            error=reason,
            trace_notes=f"{self.name} skipped: {reason}",
        )

    def _ok_result(
        self,
        task: AgentTask,
        facts: int,
        findings: Dict[str, Any],
        tokens: int,
        duration_ms: float,
        notes: str,
    ) -> ToolResult:
        return ToolResult(
            task_id=task.task_id,
            tool_name=self.name,
            success=True,
            facts_extracted=facts,
            findings=findings,
            tokens_used=tokens,
            duration_ms=duration_ms,
            trace_notes=notes,
        )
