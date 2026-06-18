"""
Tests for the Clinical Knowledge Extraction Engine on Groq.

A single Groq call extracts every clinical category in one pass, and the
structured result is cached by SHA256(document_text) so repeated extraction
tools/agent runs over the same documents never call Groq again — this is
what prevents 429 quota exhaustion from N separate extractor calls.
"""
import json
from unittest.mock import AsyncMock

import pytest

from app.groq_provider.cache import GroqResponseCache
from app.knowledge.extraction_engine import ClinicalKnowledgeExtractionEngine


SAMPLE_TEXT = "ADMISSION NOTE\nPatient: John Doe\nDiagnosis: Type 2 Diabetes Mellitus"

SAMPLE_EXTRACTION = {
    "diagnoses": [
        {
            "name": "Type 2 Diabetes Mellitus",
            "icd_code": "",
            "is_principal": True,
            "confidence": 0.95,
            "page_number": 1,
            "evidence": "Diagnosis: Type 2 Diabetes Mellitus",
        }
    ],
    "hospital_course": "",
    "hospital_course_page": 0,
    "discharge_condition": "",
    "discharge_condition_page": 0,
    "admission_medications": [],
    "discharge_medications": [],
    "allergies": [],
    "nkda": False,
    "nkda_page": 0,
    "nkda_evidence": "",
    "procedures": [],
    "lab_results": [],
    "pending_results": [],
    "followups": [],
}


@pytest.fixture
def engine(tmp_path):
    engine = ClinicalKnowledgeExtractionEngine()
    engine._cache = GroqResponseCache(cache_dir=tmp_path / "groq_responses")
    return engine


@pytest.fixture
def mock_groq_client():
    client = AsyncMock()
    client.generate_content = AsyncMock(return_value=json.dumps(SAMPLE_EXTRACTION))
    return client


class TestSingleCallExtraction:
    @pytest.mark.asyncio
    async def test_extract_calls_groq_once(self, engine, mock_groq_client):
        result = await engine.extract(SAMPLE_TEXT, mock_groq_client)

        mock_groq_client.generate_content.assert_awaited_once()
        assert result.from_cache is False
        assert result.data["diagnoses"][0]["name"] == "Type 2 Diabetes Mellitus"

    @pytest.mark.asyncio
    async def test_result_contains_all_required_categories(self, engine, mock_groq_client):
        result = await engine.extract(SAMPLE_TEXT, mock_groq_client)

        for key in (
            "diagnoses",
            "admission_medications",
            "discharge_medications",
            "allergies",
            "procedures",
            "lab_results",
            "pending_results",
            "followups",
        ):
            assert key in result.data

    @pytest.mark.asyncio
    async def test_prompt_requests_json_schema(self, engine, mock_groq_client):
        await engine.extract(SAMPLE_TEXT, mock_groq_client)

        prompt = mock_groq_client.generate_content.call_args.kwargs["prompt"]
        assert "diagnoses" in prompt
        assert "medications" in prompt or "admission_medications" in prompt


class TestCaching:
    @pytest.mark.asyncio
    async def test_second_call_uses_cache_not_groq(self, engine, mock_groq_client):
        first = await engine.extract(SAMPLE_TEXT, mock_groq_client)
        assert first.from_cache is False
        assert mock_groq_client.generate_content.await_count == 1

        second = await engine.extract(SAMPLE_TEXT, mock_groq_client)

        assert second.from_cache is True
        assert second.data == first.data
        # Groq must not be called again for identical document content —
        # this is what avoids 429 quota exhaustion across repeated runs.
        assert mock_groq_client.generate_content.await_count == 1

    @pytest.mark.asyncio
    async def test_different_document_text_is_not_cached_together(self, engine, mock_groq_client):
        await engine.extract(SAMPLE_TEXT, mock_groq_client)
        await engine.extract(SAMPLE_TEXT + "\nExtra page content", mock_groq_client)

        assert mock_groq_client.generate_content.await_count == 2


class TestMalformedResponse:
    @pytest.mark.asyncio
    async def test_unparseable_response_returns_empty_data(self, engine):
        client = AsyncMock()
        client.generate_content = AsyncMock(return_value="not valid json at all")

        result = await engine.extract(SAMPLE_TEXT, client)

        assert result.data == {}
        assert result.from_cache is False
