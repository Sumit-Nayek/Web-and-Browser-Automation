"""Previous-business-day logic.

EDGAR only publishes daily indexes for days the SEC accepted filings, i.e.
weekdays that are not US federal holidays. We compute US federal holidays
(including observed shifts) without external dependencies so the pipeline
has zero fragile imports.
"""
from __future__ import annotations

import datetime as dt


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    """n-th occurrence (1-based) of weekday (Mon=0) in a month."""
    d = dt.date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + dt.timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> dt.date:
    if month == 12:
        d = dt.date(year, 12, 31)
    else:
        d = dt.date(year, month + 1, 1) - dt.timedelta(days=1)
    offset = (d.weekday() - weekday) % 7
    return d - dt.timedelta(days=offset)


def _observed(d: dt.date) -> dt.date:
    """Federal observance rule: Sat -> Fri, Sun -> Mon."""
    if d.weekday() == 5:
        return d - dt.timedelta(days=1)
    if d.weekday() == 6:
        return d + dt.timedelta(days=1)
    return d


def us_federal_holidays(year: int) -> set[dt.date]:
    fixed = [
        dt.date(year, 1, 1),    # New Year's Day
        dt.date(year, 6, 19),   # Juneteenth
        dt.date(year, 7, 4),    # Independence Day
        dt.date(year, 11, 11),  # Veterans Day
        dt.date(year, 12, 25),  # Christmas
    ]
    floating = [
        _nth_weekday(year, 1, 0, 3),    # MLK Day - 3rd Mon Jan
        _nth_weekday(year, 2, 0, 3),    # Presidents' Day - 3rd Mon Feb
        _last_weekday(year, 5, 0),      # Memorial Day - last Mon May
        _nth_weekday(year, 9, 0, 1),    # Labor Day - 1st Mon Sep
        _nth_weekday(year, 10, 0, 2),   # Columbus Day - 2nd Mon Oct
        _nth_weekday(year, 11, 3, 4),   # Thanksgiving - 4th Thu Nov
    ]
    return {_observed(d) for d in fixed} | set(floating)


def is_business_day(d: dt.date) -> bool:
    return d.weekday() < 5 and d not in us_federal_holidays(d.year)


def previous_business_day(reference: dt.date | None = None) -> dt.date:
    """Most recent business day strictly before `reference` (default: today)."""
    d = (reference or dt.date.today()) - dt.timedelta(days=1)
    while not is_business_day(d):
        d -= dt.timedelta(days=1)
    return d
