"""Reusable HTTP transport with bounded retries and correlation metadata."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from src.config import TestSettings


class HttpClient:
    """Small transport abstraction; domain assertions belong above this layer."""

    _RETRYABLE_METHODS = frozenset({"DELETE", "GET", "HEAD", "OPTIONS", "PUT"})
    _RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})

    def __init__(self, settings: TestSettings, session: requests.Session | None = None):
        self.settings = settings
        self.session = session or requests.Session()
        retry = Retry(
            total=settings.retry_total,
            connect=settings.retry_total,
            read=settings.retry_total,
            status=settings.retry_total,
            allowed_methods=self._RETRYABLE_METHODS,
            status_forcelist=self._RETRYABLE_STATUSES,
            backoff_factor=0.25,
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=20, pool_maxsize=20)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        self.session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "qa-automation-python-pytest/1.0",
                "X-Test-Run-Id": settings.run_id,
            }
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
        **kwargs: Any,
    ) -> requests.Response:
        parsed = urlparse(path)
        if parsed.scheme or parsed.netloc:
            raise ValueError("request path must be relative to the validated TEST_BASE_URL")

        url = f"{self.settings.base_url}/{path.lstrip('/')}"
        kwargs.setdefault(
            "timeout",
            (
                self.settings.connect_timeout_seconds,
                self.settings.read_timeout_seconds,
            ),
        )
        return self.session.request(method, url, headers=headers, **kwargs)

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "HttpClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()