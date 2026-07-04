import datetime as dt
import pathlib

from sec_keyterms.business_day import previous_business_day, us_federal_holidays
from sec_keyterms.config import SETTINGS
from sec_keyterms.extractor import extract_key_terms
from sec_keyterms.validators import is_valid_cusip, is_valid_isin, normalize_date

FIXTURE = (pathlib.Path(__file__).parent / "sample_424b2.html").read_text()


# ---------------- validators ----------------
def test_cusip_checksum():
    assert is_valid_cusip("037833100")       # Apple
    assert is_valid_cusip("48130CFY6")       # fixture note
    assert not is_valid_cusip("48130CFY5")   # bad check digit
    assert not is_valid_cusip("ABC")


def test_isin_checksum():
    assert is_valid_isin("US0378331005")     # Apple
    assert is_valid_isin("US48130CFY66")     # fixture note
    assert not is_valid_isin("US48130CFY65")


def test_date_normalization():
    assert normalize_date("July 2, 2026*") == "2026-07-02"
    assert normalize_date("07/02/2026") == "2026-07-02"
    assert normalize_date("2 July 2026") == "2026-07-02"
    assert normalize_date("not a date") is None


# ---------------- business day ----------------
def test_previous_business_day_skips_weekend():
    # Monday 2026-07-06 -> previous business day is Thursday 2026-07-02,
    # because Friday 2026-07-03 is the observed Independence Day holiday.
    assert previous_business_day(dt.date(2026, 7, 6)) == dt.date(2026, 7, 2)


def test_observed_holiday():
    # July 4, 2026 is a Saturday -> observed Friday July 3
    assert dt.date(2026, 7, 3) in us_federal_holidays(2026)


# ---------------- extractor ----------------
def test_extract_key_terms_from_fixture():
    res = extract_key_terms(FIXTURE, SETTINGS.target_fields)
    f = res.fields
    assert f["company_issuer"].startswith("JPMorgan Chase Financial Company LLC")
    assert f["guarantor"] == "JPMorgan Chase & Co."
    assert f["trade_date"] == "2026-07-02"           # from 'Pricing Date' synonym
    assert f["original_issue_date"] == "2026-07-08"  # 'Original Issue Date (Settlement Date)'
    assert f["stated_maturity_date"] == "2029-07-06"
    assert f["cusip"] == "48130CFY6"
    assert f["isin"] == "US48130CFY66"
    assert res.missing == []


def test_extractor_reports_missing_fields():
    res = extract_key_terms("<html><body><p>Nothing here</p></body></html>",
                            SETTINGS.target_fields)
    assert set(res.missing) == set(SETTINGS.target_fields)
