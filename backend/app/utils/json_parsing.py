"""Shared JSON-parsing helpers for Claude text responses."""

import json
from typing import Any, Dict, Optional


def parse_json_response(text: str) -> Optional[Dict[str, Any]]:
    """Parse a JSON object out of a Claude text response, stripping markdown fences."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            return json.loads(text[start:end])
        except Exception:
            return None
