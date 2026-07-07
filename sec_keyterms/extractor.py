"""Layered extraction of Key Terms attributes from EDGAR HTML documents.

Issuer HTML varies enormously (JPM, GS, Barclays, Citi, RBC... all differ),
so extraction proceeds in layers, most-precise first:

  L1  label -> value pairs from tables inside/after a 'Key Terms' /
      'Terms of the Securities' heading
  L2  label -> value pairs from bold-label paragraph style
      ('<b>Trade Date:</b> July 2, 2026')
  L3  document-wide regex fallback for CUSIP / ISIN
  L4  checksum validation + date normalization

Each canonical field has a synonym set, since 'Trade Date', 'Pricing Date',
'Strike Date' etc. all name the same economic attribute.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from unittest import result

from bs4 import BeautifulSoup

from .validators import is_valid_cusip, is_valid_isin, normalize_date

log = logging.getLogger(__name__)
import warnings
from bs4 import XMLParsedAsHTMLWarning

# SEC documents often mix HTML and XML. This suppresses the noisy BeautifulSoup warning.
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
# ---------------------------------------------------------------------------
# Canonical field -> label synonyms (lowercase, punctuation-stripped matching)
# Order matters: first synonym hit wins for a field.
# ---------------------------------------------------------------------------
FIELD_SYNONYMS: dict[str, tuple[str, ...]] = {
    "company_issuer": ("issuer", "company", "issuing entity"),
    "guarantor": ("guarantor", "guarantee", "guaranteed by"),
    "trade_date": ("trade date", "pricing date", "strike date", "initial valuation date"),
    "original_issue_date": (
        "original issue date", "issue date", "settlement date",
        "original issue date settlement date", "issue date settlement date",
    ),
    "stated_maturity_date": ("stated maturity date", "maturity date", "maturity"),
    "cusip": ("cusip", "cusip number", "cusip no", "cusip isin"),
    "isin": ("isin", "isin number", "isin no"),
}

DATE_FIELDS = {"trade_date", "original_issue_date", "stated_maturity_date"}

SECTION_HEADING_RE = re.compile(
    r"(key\s+terms|terms\s+of\s+the\s+(securities|notes)|summary\s+of\s+terms)", re.I
)

CUSIP_FALLBACK_RE = re.compile(r"CUSIP\s*(?:No\.?|Number|#|:)?\s*[:\-]?\s*([0-9A-Z@#*]{9})\b", re.I)
ISIN_FALLBACK_RE = re.compile(r"ISIN\s*(?:No\.?|Number|#|:)?\s*[:\-]?\s*([A-Z]{2}[0-9A-Z]{9}[0-9])\b", re.I)


@dataclass
class ExtractionResult:
    fields: dict[str, str | None] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    method_used: dict[str, str] = field(default_factory=dict)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text).replace("\xa0", " ").strip()


def _norm_label(text: str) -> str:
    s = _clean(text).lower().rstrip(":").strip()
    s = re.sub(r"[\*\u2020\u2021\d]+$", "", s).strip()   # footnote markers
    s = re.sub(r"[^\w\s/]", "", s)
    s = s.replace("/", " ")
    return re.sub(r"\s+", " ", s).strip()


def _match_field(label: str) -> str | None:
    norm = _norm_label(label)
    if not norm or len(norm) > 60:
        return None
    for canonical, synonyms in FIELD_SYNONYMS.items():
        for syn in synonyms:
            if norm == syn or norm.startswith(syn + " ") or norm.replace(" ", "") == syn.replace(" ", ""):
                return canonical
    return None


# ---------------------------------------------------------------------------
# Layer 1: tables (within Key Terms section preferred, whole document fallback)
# ---------------------------------------------------------------------------
def _pairs_from_tables(soup: BeautifulSoup) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            # CRITICAL FIX: Ensure the row belongs to the current table, not a nested one
            if row.find_parent("table") != table:
                continue
                
            cells = [c for c in row.find_all(["td", "th"]) if _clean(c.get_text())]
            if len(cells) < 2:
                continue
            
            label = cells[0].get_text(" ")
            value = cells[1].get_text(" ")
            
            # Handle layouts that put the label in col0 and value in the last col
            if not _clean(value) and len(cells) > 2:
                value = cells[-1].get_text(" ")
                
            pairs.append((label, value))
    return pairs


# ---------------------------------------------------------------------------
# Layer 2: bold-label paragraphs:  <b>Trade Date:</b> July 2, 2026
# ---------------------------------------------------------------------------
def _pairs_from_bold_labels(soup: BeautifulSoup) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for tag in soup.find_all(["b", "strong"]):
        label = tag.get_text(" ")
        if ":" not in label and not _match_field(label):
            continue
        parent = tag.parent
        if parent is None:
            continue
        full = _clean(parent.get_text(" "))
        lab = _clean(label).rstrip(":")
        if full.lower().startswith(lab.lower()):
            value = full[len(lab):].lstrip(" :\u2013\u2014-")
            if value:
                pairs.append((lab, value))
    return pairs


# also plain-text "Label: value" lines (covers <p>Trade Date: ...</p>)
_TEXTLINE_RE = re.compile(r"^([A-Z][A-Za-z /\u2013\-]{2,50}?)\s*:\s+(.{1,200})$")


def _pairs_from_text_lines(soup: BeautifulSoup) -> list[tuple[str, str]]:
    pairs = []
    for line in soup.get_text("\n").splitlines():
        line = _clean(line)
        m = _TEXTLINE_RE.match(line)
        if m:
            pairs.append((m.group(1), m.group(2)))
    return pairs


def _scope_to_key_terms_section(soup: BeautifulSoup) -> BeautifulSoup:
    """If a Key Terms heading exists, return a soup of the ~subsequent content.

    Falls back to the whole document when no heading is found (some FWPs
    just launch straight into the table).
    """
    heading = soup.find(string=SECTION_HEADING_RE)
    if heading is None:
        return soup
    anchor = heading.parent
    html_chunks, node = [], anchor
    # collect the anchor's following siblings up its ancestor chain until we
    # have a meaningful chunk of content
    collected = 0
    while node is not None and collected < 200:
        for sib in node.find_next_siblings():
            html_chunks.append(str(sib))
            collected += 1
            if collected >= 200:
                break
        node = node.parent if getattr(node, "parent", None) and node.parent.name != "[document]" else None
    if not html_chunks:
        return soup
    return BeautifulSoup("".join(html_chunks), "lxml")


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------
def _clean_value(canonical: str, value: str) -> str | None:
    v = _clean(value)
    if not v:
        return None
        
    if canonical in DATE_FIELDS:
        parsed = normalize_date(v)
        if parsed:
            return parsed
        # Reject giant paragraphs (like the UBS layout) so it gets flagged as missing
        if len(v) > 60:
            return None
        return v  # Keep short raw text if unparseable, flag later
        
    if canonical == "cusip":
        m = re.search(r"[0-9A-Z@#*]{9}", v.upper())
        if m and is_valid_cusip(m.group(0)):
            return m.group(0)
        return None
        
    if canonical == "isin":
        m = re.search(r"[A-Z]{2}[0-9A-Z]{9}[0-9]", v.upper())
        if m and is_valid_isin(m.group(0)):
            return m.group(0)
        return None
    # For free-text fields like company_issuer, trim common boilerplate definitions
    if canonical in ["company_issuer", "guarantor"]:
        # Strip everything after a parenthesis or common boilerplate markers
        v = re.split(r'\(|“|"', v)[0].strip()
        
    return v[:300]    
    # free-text fields: trim boilerplate tails
    return v[:300]


def extract_key_terms(html: str, target_fields: tuple[str, ...]) -> ExtractionResult:
    soup = BeautifulSoup(html, "lxml")
    result = ExtractionResult(fields={f: None for f in target_fields})

    section = _scope_to_key_terms_section(soup)

    layers: list[tuple[str, list[tuple[str, str]]]] = [
        ("section_table", _pairs_from_tables(section)),
        ("section_bold", _pairs_from_bold_labels(section)),
        ("doc_table", _pairs_from_tables(soup)),
        ("doc_bold", _pairs_from_bold_labels(soup)),
        ("doc_textline", _pairs_from_text_lines(soup)),
    ]

    for method, pairs in layers:
        for label, value in pairs:
            canonical = _match_field(label)
            if canonical is None or canonical not in result.fields:
                continue
            if result.fields[canonical] is not None:
                continue  # first (most-precise layer) hit wins
            cleaned = _clean_value(canonical, value)
            if cleaned:
                result.fields[canonical] = cleaned
                result.method_used[canonical] = method

    # Layer 3: identifier regex fallback across the raw text
    text = soup.get_text(" ")
    if "cusip" in result.fields and result.fields["cusip"] is None:
        for m in CUSIP_FALLBACK_RE.finditer(text):
            if is_valid_cusip(m.group(1).upper()):
                result.fields["cusip"] = m.group(1).upper()
                result.method_used["cusip"] = "regex_fallback"
                break
    if "isin" in result.fields and result.fields["isin"] is None:
        for m in ISIN_FALLBACK_RE.finditer(text):
            if is_valid_isin(m.group(1).upper()):
                result.fields["isin"] = m.group(1).upper()
                result.method_used["isin"] = "regex_fallback"
                break
    
    result.missing = [f for f, v in result.fields.items() if v is None]
    # Add this snippet near the bottom of extract_key_terms, right before identifier fallbacks
    issuer_name = result.fields.get("company_issuer", "") or ""
    if "Goldman Sachs" in issuer_name and any(v is None for v in result.fields.values()):
        # Example placeholder: Execute Goldman-specific regex or table logic here
        # doc_text = soup.get_text(" ")
        # custom_gs_extraction(doc_text, result)
        pass
    return result
