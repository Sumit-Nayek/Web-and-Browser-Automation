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
