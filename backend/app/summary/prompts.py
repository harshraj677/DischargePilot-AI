"""
Summary generation prompts.

All prompts follow the anti-hallucination constraint:
- Only use facts explicitly present in the provided knowledge base context
- Never infer, speculate, or fabricate clinical information
- If information is missing, state 'Not documented' — never guess
"""

SUMMARY_SYSTEM_PROMPT = """You are a clinical documentation AI assisting in generating structured discharge summaries.

CRITICAL CONSTRAINTS — VIOLATION IS PROHIBITED:
1. ONLY use clinical facts explicitly stated in the PROVIDED KNOWLEDGE BASE CONTEXT below.
2. NEVER infer, speculate, or fabricate any clinical information.
3. If a fact is missing or unclear in the context, write "Not documented" — do NOT guess.
4. Do not add clinical opinions, diagnoses, or treatment recommendations.
5. Write in clear, professional medical prose suitable for a discharge summary.
6. Every sentence must be traceable to the knowledge base context.

Your output will be reviewed by a licensed clinician before use."""


HOSPITAL_COURSE_PROMPT = """{system_context}

KNOWLEDGE BASE CONTEXT:
{kb_context}

HOSPITAL COURSE FACTS FROM SOURCE DOCUMENTS:
{hospital_course_facts}

TASK:
Write a concise, factual hospital course narrative for this patient's discharge summary.

Requirements:
- Summarize the clinical events in chronological order where possible
- Include presenting complaint, key interventions, clinical response, and reason for discharge
- Write 2–4 paragraphs in professional clinical prose
- Only include facts present in the context above
- Do NOT add any clinical interpretation not present in the source

If insufficient information is available, write a brief factual statement with what is known
and note "Additional documentation may be required."

HOSPITAL COURSE NARRATIVE:"""


DISCHARGE_CONDITION_PROMPT = """{system_context}

KNOWLEDGE BASE CONTEXT:
{kb_context}

DISCHARGE CONDITION FACTS:
{condition_facts}

TASK:
Write a brief, factual description of the patient's condition at discharge.
Use only the facts provided. One short paragraph only.

DISCHARGE CONDITION:"""


MEDICATION_CHANGES_PROMPT = """{system_context}

ADMISSION MEDICATIONS:
{admission_meds}

DISCHARGE MEDICATIONS:
{discharge_meds}

TASK:
List all medication changes between admission and discharge in this format:
- CONTINUED: [medication] [dose]
- CHANGED: [medication] from [old dose] to [new dose] — Reason: [if documented]
- NEW: [medication] [dose] — Indication: [if documented]
- DISCONTINUED: [medication] — Reason: [if documented]

Only include actual changes. Use only the information provided above.
If no changes are documented, write "No medication changes documented."

MEDICATION CHANGES:"""
