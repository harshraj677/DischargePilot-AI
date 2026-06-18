"""
GroqSummaryService

Alias over DischargeSummaryGenerator (app/summary/generator.py), the
Groq-backed narrative generator for discharge summaries (hospital course,
discharge condition, medication changes) — all other sections are
deterministic templates over the knowledge base, with zero LLM calls.
"""

from app.summary.generator import DischargeSummaryGenerator

GroqSummaryService = DischargeSummaryGenerator
