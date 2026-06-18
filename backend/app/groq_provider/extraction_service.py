"""
GroqExtractionService

Alias over ClinicalKnowledgeExtractionEngine (app/knowledge/extraction_engine.py),
which already implements the single-consolidated-call strategy this name
refers to: ONE Groq call per document set extracts diagnoses, medications,
allergies, procedures, labs, pending_results, followups, and discharge
condition together, with the structured result cached by SHA256(document
text) via GroqResponseCache so repeated tool/agent runs never re-call Groq
for the same documents.
"""

from app.knowledge.extraction_engine import ClinicalKnowledgeExtractionEngine, get_extraction_engine

GroqExtractionService = ClinicalKnowledgeExtractionEngine
get_groq_extraction_service = get_extraction_engine
