"""Pipeline entry point.

Usage:
    python -m sec_keyterms.run                       # previous business day
    python -m sec_keyterms.run --date 2026-07-02     # explicit date
    python -m sec_keyterms.run --forms 424B2,FWP --limit 50 --out output/
"""
from __future__ import annotations

import argparse
import datetime as dt
import logging
import pathlib
import sys

from .business_day import previous_business_day
from .config import SETTINGS
from .daily_index import fetch_filings_for_day, resolve_primary_document
from .extractor import extract_key_terms
from .http_client import EdgarClient
from .writers import write_json, write_xml

log = logging.getLogger("sec_keyterms")


def build_record(filing, doc_url, extraction) -> dict:
    # ISIN and Guarantor are optional. If only they are missing, it's still 'complete'.
    optional_fields = {"isin", "guarantor"}
    truly_missing = [f for f in extraction.missing if f not in optional_fields]    
    status = "complete" if not truly_missing else (
        "partial" if any(v for k, v in extraction.fields.items() if v and k not in optional_fields) else "failed"
    )
    return {
        "accession_number": filing.accession,
        "form_type": filing.form_type,
        "date_filed": filing.date_filed,
        "cik": filing.cik,
        "company_name_edgar": filing.company,
        "document_url": doc_url,
        "extraction_status": status,
        "key_terms": extraction.fields,
        "missing_fields": extraction.missing,
        "extraction_methods": extraction.method_used,
    }


def run(target_date: dt.date, forms: tuple[str, ...], out_dir: pathlib.Path,
        limit: int | None = None) -> int:
    client = EdgarClient()
    filings = fetch_filings_for_day(client, target_date, forms)
    if limit:
        filings = filings[:limit]

    records: list[dict] = []
    for i, filing in enumerate(filings, 1):
        log.info("[%d/%d] %s %s (%s)", i, len(filings), filing.form_type,
                 filing.company, filing.accession)
        doc_url = resolve_primary_document(client, filing)
        if doc_url is None:
            records.append(build_record(filing, None, _empty_extraction()))
            continue
        try:
            html = client.get(doc_url).text
            extraction = extract_key_terms(html, SETTINGS.target_fields)
        except Exception as exc:  # noqa: BLE001 - one bad filing must not kill the run
            log.error("Extraction failed for %s: %s", filing.accession, exc)
            extraction = _empty_extraction()
        records.append(build_record(filing, doc_url, extraction))

    stamp = target_date.strftime("%Y%m%d")
    write_json(records, out_dir / f"key_terms_{stamp}.json")
    write_xml(records, out_dir / f"key_terms_{stamp}.xml")

    complete = sum(1 for r in records if r["extraction_status"] == "complete")
    partial = sum(1 for r in records if r["extraction_status"] == "partial")
    log.info("Done: %d filings | %d complete | %d partial | outputs in %s",
             len(records), complete, partial, out_dir)
    return 0


def _empty_extraction():
    from .extractor import ExtractionResult
    r = ExtractionResult(fields={f: None for f in SETTINGS.target_fields})
    r.missing = list(SETTINGS.target_fields)
    return r


def main() -> int:
    parser = argparse.ArgumentParser(description="SEC Key Terms extraction pipeline")
    parser.add_argument("--date", help="Filing date YYYY-MM-DD (default: previous business day)")
    parser.add_argument("--forms", default=",".join(SETTINGS.form_types),
                        help="Comma-separated form types (default: %(default)s)")
    parser.add_argument("--out", default=SETTINGS.output_dir, help="Output directory")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N filings (useful for testing)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    target = (dt.date.fromisoformat(args.date) if args.date else previous_business_day())
    forms = tuple(f.strip().upper() for f in args.forms.split(",") if f.strip())
    return run(target, forms, pathlib.Path(args.out), args.limit)


if __name__ == "__main__":
    sys.exit(main())
