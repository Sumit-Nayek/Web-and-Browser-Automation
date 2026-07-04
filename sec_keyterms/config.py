"""Central configuration for the SEC Key Terms extraction pipeline.

Everything operational (identity, throttle, form types, output paths) lives
here so the pipeline can be tuned without touching business logic.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    # --- SEC fair-access identity -------------------------------------------------
    # SEC REQUIRES a descriptive User-Agent with a contact email.
    # https://www.sec.gov/os/accessing-edgar-data
    # Override via env var SEC_USER_AGENT in deployment.
    user_agent: str = os.environ.get(
        "SEC_USER_AGENT",
        "KeyTermsExtractor/1.0 (data-engineering; contact: your.name@yourfirm.com)",
    )

    # --- Endpoints ------------------------------------------------------------------
    base_archives: str = "https://www.sec.gov/Archives"
    daily_index_tpl: str = (
        "https://www.sec.gov/Archives/edgar/daily-index/{year}/QTR{qtr}/master.{yyyymmdd}.idx"
    )

    # --- Throttle / retry -------------------------------------------------------------
    # SEC allows max 10 req/s per client. We stay under it deliberately.
    max_requests_per_second: float = float(os.environ.get("SEC_MAX_RPS", "8"))
    max_retries: int = 5
    backoff_base_seconds: float = 1.5
    request_timeout: int = 30

    # --- Business rules --------------------------------------------------------------
    # Structured-note documents that carry "Key Terms" / "Terms of the Securities".
    form_types: tuple[str, ...] = ("424B2", "FWP")

    # --- Output ------------------------------------------------------------------------
    output_dir: str = os.environ.get("OUTPUT_DIR", "output")

    # Attributes we are contracted to extract (canonical names).
    target_fields: tuple[str, ...] = (
        "company_issuer",
        "guarantor",
        "trade_date",
        "original_issue_date",
        "stated_maturity_date",
        "cusip",
        "isin",
    )


SETTINGS = Settings()
