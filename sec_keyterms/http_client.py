"""HTTP client hardened for SEC EDGAR fair-access rules.

- Single shared requests.Session (connection pooling)
- Token-bucket rate limiter (default 8 req/s, SEC hard limit is 10)
- Exponential backoff with jitter on 403/429/5xx
- Mandatory declared User-Agent
"""
from __future__ import annotations

import logging
import random
import threading
import time

import requests

from .config import SETTINGS

log = logging.getLogger(__name__)

_RETRYABLE = {403, 429, 500, 502, 503, 504}


class _RateLimiter:
    """Simple thread-safe minimum-interval limiter."""

    def __init__(self, max_rps: float) -> None:
        self._interval = 1.0 / max_rps
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            sleep_for = self._next_allowed - now
            self._next_allowed = max(now, self._next_allowed) + self._interval
        if sleep_for > 0:
            time.sleep(sleep_for)


class EdgarClient:
    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": SETTINGS.user_agent,
                "Accept-Encoding": "gzip, deflate",
                "Host": "www.sec.gov",
            }
        )
        self._limiter = _RateLimiter(SETTINGS.max_requests_per_second)

    def get(self, url: str) -> requests.Response:
        """GET with throttle + retries. Raises after exhausting retries."""
        last_exc: Exception | None = None
        for attempt in range(1, SETTINGS.max_retries + 1):
            self._limiter.wait()
            try:
                resp = self._session.get(url, timeout=SETTINGS.request_timeout)
                if resp.status_code == 200:
                    return resp
                if resp.status_code == 404:
                    resp.raise_for_status()
                if resp.status_code in _RETRYABLE:
                    log.warning(
                        "GET %s -> %s (attempt %d/%d), backing off",
                        url, resp.status_code, attempt, SETTINGS.max_retries,
                    )
                    self._backoff(attempt)
                    continue
                resp.raise_for_status()
            except requests.exceptions.HTTPError:
                raise
            except requests.exceptions.RequestException as exc:  # network blips
                last_exc = exc
                log.warning("GET %s failed (%s), attempt %d/%d", url, exc, attempt, SETTINGS.max_retries)
                self._backoff(attempt)
        raise RuntimeError(f"Exhausted retries for {url}") from last_exc

    @staticmethod
    def _backoff(attempt: int) -> None:
        delay = SETTINGS.backoff_base_seconds * (2 ** (attempt - 1))
        time.sleep(delay + random.uniform(0, 0.5))
