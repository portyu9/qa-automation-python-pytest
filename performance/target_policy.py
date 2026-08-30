"""Traffic-authorization policy shared by Locust and fast framework contracts."""

from __future__ import annotations

import ipaddress
import os
from collections.abc import Mapping
from urllib.parse import urlsplit

DEFAULT_TARGET = "http://127.0.0.1:5000"


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _normalized_host(value: str) -> str:
    return value.strip().lower().removeprefix("[").removesuffix("]")


def validate_load_target(target: str | None, env: Mapping[str, str] | None = None) -> str:
    """Return a safe absolute target or reject it before any load traffic begins."""
    environment = os.environ if env is None else env
    raw = str(target or "").strip().rstrip("/")
    if not raw:
        raise ValueError("Locust target must be an absolute http(s) URL")

    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Locust target must use http or https with a hostname")
    if parsed.username or parsed.password:
        raise ValueError("Locust target must not contain URL credentials")
    if parsed.query or parsed.fragment:
        raise ValueError("Locust target must not contain a query string or fragment")
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("Locust target contains an invalid port") from error
    if port == 0:
        raise ValueError("Locust target port must be between 1 and 65535")

    host = _normalized_host(parsed.hostname)
    is_loopback = host == "localhost"
    if not is_loopback:
        try:
            is_loopback = ipaddress.ip_address(host).is_loopback
        except ValueError:
            is_loopback = False

    if is_loopback:
        return raw

    if not _enabled(environment.get("PERF_ALLOW_EXTERNAL")):
        raise ValueError("external Locust targets require PERF_ALLOW_EXTERNAL=true")

    allowed_hosts = {
        _normalized_host(item)
        for item in str(environment.get("PERF_ALLOWED_HOSTS", "")).split(",")
        if item.strip()
    }
    if host not in allowed_hosts:
        raise ValueError("external Locust target host is not present in PERF_ALLOWED_HOSTS")
    return raw
