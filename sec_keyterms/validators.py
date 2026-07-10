"""Field validation & normalization.

Checksum validation is what separates 'found a 9-character string' from
'found a CUSIP'. Both CUSIP and ISIN carry check digits we can verify.
"""
from __future__ import annotations

import datetime as dt
import re

_CUSIP_RE = re.compile(r"^[0-9A-Z@#*]{8}[0-9]$")
_ISIN_RE = re.compile(r"^[A-Z]{2}[0-9A-Z]{9}[0-9]$")


def _cusip_char_value(c: str) -> int:
    if c.isdigit():
        return int(c)
    if c.isalpha():
        return ord(c) - ord("A") + 10
    return {"*": 36, "@": 37, "#": 38}[c]


def is_valid_cusip(raw: str) -> bool:
    s = raw.strip().upper()
    if not _CUSIP_RE.match(s):
        return False
    total = 0
    for i, ch in enumerate(s[:8]):
        v = _cusip_char_value(ch)
        if i % 2 == 1:  # double every second char (1-indexed even positions)
            v *= 2
        total += v // 10 + v % 10
    return (10 - total % 10) % 10 == int(s[8])


def is_valid_isin(raw: str) -> bool:
    s = raw.strip().upper()
    if not _ISIN_RE.match(s):
        return False
    digits = "".join(str(_cusip_char_value(c)) if c.isalpha() else c for c in s[:-1])
    # Luhn over the expanded digit string, doubling from the right
    total = 0
    for i, ch in enumerate(reversed(digits)):
        v = int(ch)
        if i % 2 == 0:
            v *= 2
        total += v // 10 + v % 10
    return (10 - total % 10) % 10 == int(s[-1])


_DATE_FORMATS = (
    "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b. %d, %Y",
    "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%Y-%m-%d", "%d %B %Y", "%d %b %Y",
)


def normalize_date(raw: str) -> str | None:
    """Best-effort parse to ISO-8601. Returns None if unparseable."""
    s = re.sub(r"\s+", " ", raw).strip().strip(".")
    # Strip footnote markers and trailing qualifiers like '(expected)'
    s = re.sub(r"[\*\u2020\u2021]+$", "", s).strip()
    s = re.sub(r"\(.*?\)$", "", s).strip()
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None
# sec_keyterms/validators.py (Append to the bottom of the file)

def validate_date_sequence(trade_date: str | None, issue_date: str | None, maturity_date: str | None) -> list[str]:
    """Ensures extracted dates follow the logical flow of time."""
    warnings = []
    try:
        # Convert ISO strings back to date objects for mathematical comparison
        td = dt.date.fromisoformat(trade_date) if trade_date else None
        id = dt.date.fromisoformat(issue_date) if issue_date else None
        md = dt.date.fromisoformat(maturity_date) if maturity_date else None

        if td and id and td > id:
            warnings.append("Trade Date occurs after Issue Date (Logical Error)")
        if id and md and id >= md:
            warnings.append("Issue Date occurs on or after Maturity Date (Logical Error)")
        if td and md and td >= md:
            warnings.append("Trade Date occurs on or after Maturity Date (Logical Error)")
    except ValueError:
        warnings.append("Date sequence validation failed due to invalid ISO format.")
        
    return warnings


def calculate_confidence(method_used: dict[str, str]) -> dict[str, float]:
    """Assigns a confidence score (0.0 to 1.0) based on how the data was found."""
    # Strict deterministic tables get the highest trust. LLM gets lower trust to flag for review.
    confidence_map = {
        "section_table": 0.99,
        "doc_table": 0.98,
        "section_bold": 0.95,
        "doc_bold": 0.94,
        "doc_textline": 0.92,
        "regex_fallback": 0.90,
        "llm_nim_fallback": 0.85
    }
    
    scores = {}
    for field, method in method_used.items():
        scores[field] = confidence_map.get(method, 0.80) # Default to 0.80 if unknown
    return scores