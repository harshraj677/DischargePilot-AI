"""
Unit tests for the Document Chunker (Phase 2).

Tests cover:
1. Basic text chunking with overlap
2. Sentence boundary preservation
3. Empty/short text edge cases
4. Chunk metadata (page numbers, indices)
"""
from __future__ import annotations

import pytest

from app.processing.chunker import DocumentChunker


class TestDocumentChunker:
    def setup_method(self):
        self.chunker = DocumentChunker(chunk_size=200, overlap=50)

    def test_short_text_returns_single_chunk(self):
        text = "Patient admitted with chest pain."
        chunks = self.chunker.chunk_text(text, page_number=1)
        assert len(chunks) >= 1
        assert text in chunks[0].content or chunks[0].content.strip() == text.strip()

    def test_empty_text_returns_no_chunks(self):
        chunks = self.chunker.chunk_text("", page_number=1)
        assert chunks == []

    def test_whitespace_only_returns_no_chunks(self):
        chunks = self.chunker.chunk_text("   \n\t  ", page_number=1)
        assert chunks == []

    def test_long_text_produces_multiple_chunks(self):
        text = "Patient has diabetes. " * 50
        chunks = self.chunker.chunk_text(text, page_number=2)
        assert len(chunks) > 1

    def test_page_number_preserved(self):
        text = "Admission note content. Patient stable."
        chunks = self.chunker.chunk_text(text, page_number=5)
        for chunk in chunks:
            assert chunk.page_number == 5

    def test_chunk_index_sequential(self):
        text = "Sentence one. Sentence two. Sentence three. " * 20
        chunks = self.chunker.chunk_text(text, page_number=1)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i

    def test_overlap_ensures_continuity(self):
        """Consecutive chunks should share some content via overlap."""
        text = "Word " * 200
        chunks = self.chunker.chunk_text(text, page_number=1)
        if len(chunks) > 1:
            # The end of chunk[0] and start of chunk[1] should have shared words
            chunk0_words = set(chunks[0].content.split()[-10:])
            chunk1_words = set(chunks[1].content.split()[:10])
            assert len(chunk0_words & chunk1_words) > 0

    def test_chunks_cover_all_content(self):
        """All content words should appear in at least one chunk."""
        words = [f"word{i}" for i in range(100)]
        text = " ".join(words)
        chunks = self.chunker.chunk_text(text, page_number=1)
        combined = " ".join(c.content for c in chunks)
        for word in words:
            assert word in combined

    def test_chunk_document_multi_page(self):
        pages = {
            1: "Page one content about admission diagnosis and treatment.",
            2: "Page two content with lab results and medications.",
            3: "Page three with discharge instructions and follow-up.",
        }
        all_chunks = self.chunker.chunk_document(pages)
        page_numbers = {c.page_number for c in all_chunks}
        assert 1 in page_numbers
        assert 2 in page_numbers
        assert 3 in page_numbers

    def test_document_id_attached(self):
        pages = {1: "Some clinical text here."}
        chunks = self.chunker.chunk_document(pages, document_id="doc-abc-123")
        for chunk in chunks:
            assert chunk.document_id == "doc-abc-123"

    def test_chunk_size_respected(self):
        """No chunk should exceed chunk_size + overlap by a large margin."""
        chunker = DocumentChunker(chunk_size=100, overlap=20)
        text = "a" * 1000
        chunks = chunker.chunk_text(text, page_number=1)
        for chunk in chunks:
            # Allow some flexibility for sentence boundary preservation
            assert len(chunk.content) <= 200

    def test_newlines_normalized(self):
        text = "Line one.\n\nLine two.\r\nLine three."
        chunks = self.chunker.chunk_text(text, page_number=1)
        combined = " ".join(c.content for c in chunks)
        assert "Line one" in combined
        assert "Line two" in combined
        assert "Line three" in combined
