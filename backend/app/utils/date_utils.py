import re
from datetime import datetime, date
from typing import Optional

DATE_PATTERNS = [
    r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b",
    r"\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b",
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})\b",
    r"\b(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{4})\b",
    r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})\b",
]

MONTH_MAP = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9,
    "oct": 10, "nov": 11, "dec": 12,
}


def parse_clinical_date(text: str) -> Optional[datetime]:
    text = text.strip()

    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                groups = match.groups()
                # Attempt ISO format: YYYY-MM-DD
                if re.match(r"\d{4}", groups[0]):
                    return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                # Attempt MM/DD/YYYY
                if groups[0].isdigit() and groups[1].isdigit() and groups[2].isdigit():
                    month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
                    if 1 <= month <= 12 and 1 <= day <= 31:
                        return datetime(year, month, day)
                # Attempt Month name formats
                if not groups[0].isdigit():
                    month_name = groups[0].lower()
                    month = MONTH_MAP.get(month_name)
                    if month:
                        return datetime(int(groups[2]), month, int(groups[1]))
                if not groups[1].isdigit() and len(groups) == 3:
                    month_name = groups[1].lower()
                    month = MONTH_MAP.get(month_name)
                    if month:
                        return datetime(int(groups[2]), month, int(groups[0]))
            except (ValueError, TypeError):
                continue
    return None


def format_clinical_date(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    return dt.strftime("%B %d, %Y")


def extract_first_date_from_text(text: str) -> Optional[datetime]:
    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return parse_clinical_date(match.group(0))
    return None
