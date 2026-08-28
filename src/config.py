"""Validated runtime configuration for the automation framework."""

from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse
from uuid import uuid4


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}
_SUPPORTED_BROWSERS = {"chromium", "firefox", "webkit"}


def _positive_float(name: str, default: float) -> float:
    raw = os.getenv(name, str(default))
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be numeric, got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be > 0, got {value}")
    return value


def _non_negative_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if value < 0:
        raise ValueError(f"{name} must be >= 0, got {value}")
    return value


def _boolean(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be one of {sorted(_TRUE_VALUES | _FALSE_VALUES)}")


def _base_url(name: str, default: str) -> str:
    value = os.getenv(name, default).rstrip("/")
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"{name} must be an absolute http(s) URL, got {value!r}")
    return value


@dataclass(frozen=True, slots=True)
class TestSettings:
    """Immutable settings shared by test infrastructure components."""

    base_url: str
    browser: str
    headless: bool
    connect_timeout_seconds: float
    read_timeout_seconds: float
    retry_total: int
    run_id: str

    @classmethod
    def from_env(cls) -> "TestSettings":
        browser = os.getenv("TEST_BROWSER", "chromium").strip().lower()
        if browser not in _SUPPORTED_BROWSERS:
            raise ValueError(
                f"TEST_BROWSER must be one of {sorted(_SUPPORTED_BROWSERS)}, got {browser!r}"
            )

        run_id = os.getenv("TEST_RUN_ID", "").strip() or str(uuid4())
        return cls(
            base_url=_base_url(
                "TEST_BASE_URL", "https://jsonplaceholder.typicode.com"
            ),
            browser=browser,
            headless=_boolean("TEST_HEADLESS", True),
            connect_timeout_seconds=_positive_float(
                "TEST_CONNECT_TIMEOUT_SECONDS", 5.0
            ),
            read_timeout_seconds=_positive_float("TEST_READ_TIMEOUT_SECONDS", 15.0),
            retry_total=_non_negative_int("TEST_RETRY_TOTAL", 2),
            run_id=run_id,
        )
