"""Fetch and parse EDGAR's daily master index, then resolve each filing's
primary HTML document.

master.YYYYMMDD.idx format (pipe-delimited after a header block):

    CIK|Company Name|Form Type|Date Filed|Filename
    19617|JPMORGAN CHASE & CO|424B2|2026-07-02|edgar/data/19617/0000019617-26-001234.txt
"""
from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass

from .config import SETTINGS
from .http_client import EdgarClient

log = logging.getLogger(__name__)


@dataclass
class FilingRef:
    cik: str
    company: str
    form_type: str
    date_filed: str
    raw_path: str  # e.g. edgar/data/19617/0000019617-26-001234.txt

    @property
    def accession(self) -> str:
        return self.raw_path.rsplit("/", 1)[-1].replace(".txt", "")

    @property
    def folder_url(self) -> str:
        acc_nodash = self.accession.replace("-", "")
        return f"{SETTINGS.base_archives}/edgar/data/{int(self.cik)}/{acc_nodash}"

    @property
    def index_json_url(self) -> str:
        return f"{self.folder_url}/index.json"


def daily_index_url(day: dt.date) -> str:
    qtr = (day.month - 1) // 3 + 1
    return SETTINGS.daily_index_tpl.format(
        year=day.year, qtr=qtr, yyyymmdd=day.strftime("%Y%m%d")
    )


def fetch_filings_for_day(
    client: EdgarClient, day: dt.date, form_types: tuple[str, ...]
) -> list[FilingRef]:
    url = daily_index_url(day)
    log.info("Fetching daily index: %s", url)
    text = client.get(url).text

    wanted = {f.upper() for f in form_types}
    filings: list[FilingRef] = []
    for line in text.splitlines():
        parts = line.split("|")
        if len(parts) != 5:
            continue  # header / separator lines
        cik, company, form_type, date_filed, path = (p.strip() for p in parts)
        if not cik.isdigit():
            continue
        if form_type.upper() in wanted:
            filings.append(FilingRef(cik, company, form_type, date_filed, path))
    log.info("Found %d filings matching %s on %s", len(filings), sorted(wanted), day)
    return filings


def resolve_primary_document(client: EdgarClient, filing: FilingRef) -> str | None:
    """Return URL of the filing's primary HTML document.

    Strategy: list the accession folder via index.json and choose the largest
    .htm file that isn't the auto-generated index page. Pricing supplements
    are by far the largest HTML in the folder, so size is a robust heuristic;
    we also prefer names hinting at the prospectus type (424b, fwp, pricing).
    """
    try:
        listing = client.get(filing.index_json_url).json()
    except Exception as exc:  # noqa: BLE001 - degrade to skipping this filing
        log.error("Could not list %s: %s", filing.index_json_url, exc)
        return None

    items = listing.get("directory", {}).get("item", [])
    candidates = []
    for it in items:
        name = it.get("name", "")
        lname = name.lower()
        if not lname.endswith((".htm", ".html")):
            continue
        if "index" in lname or lname.startswith("r"):  # R1.htm etc are XBRL renders
            continue
        size = int(it.get("size") or 0)
        bonus = 10_000_000 if any(k in lname for k in ("424b", "fwp", "pricing", "prosp")) else 0
        candidates.append((size + bonus, name))

    if not candidates:
        log.warning("No HTML documents found for %s", filing.accession)
        return None

    candidates.sort(reverse=True)
    return f"{filing.folder_url}/{candidates[0][1]}"
