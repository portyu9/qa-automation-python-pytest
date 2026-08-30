"""Governed Locust workload for the repository-owned posts API.

The default target is loopback. External load requires both an explicit opt-in and
an exact host allowlist entry so changing ``--host`` alone cannot redirect traffic
toward an arbitrary system.
"""

from __future__ import annotations

import ipaddress
import os
from collections.abc import Mapping
from urllib.parse import urlsplit

from locust import HttpUser, between, events, task

DEFAULT_TARGET = "http://127.0.0.1:5000"


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _normalized_host(value: str) -> str:
    return value.strip().lower().removeprefix("[").removesuffix("]")


def validate_load_target(target: str | None, env: Mapping[str, str] | None = None) -> str:
    """Return a safe absolute target or reject it before Locust sends traffic."""
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


class PostsUser(HttpUser):
    """Model read traffic against the posts collection and a representative item."""

    host = os.getenv("TEST_BASE_URL", DEFAULT_TARGET)
    wait_time = between(1, 2)

    @task(3)
    def list_posts(self) -> None:
        with self.client.get("/posts", name="GET /posts", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"unexpected status {response.status_code}")
                return
            try:
                payload = response.json()
            except ValueError:
                response.failure("response was not valid JSON")
                return
            if not isinstance(payload, list):
                response.failure("response was not a JSON array")

    @task(1)
    def get_first_post(self) -> None:
        with self.client.get("/posts/1", name="GET /posts/:id", catch_response=True) as response:
            if response.status_code != 200:
                response.failure(f"unexpected status {response.status_code}")
                return
            try:
                payload = response.json()
            except ValueError:
                response.failure("response was not valid JSON")
                return
            if not isinstance(payload, dict) or not {"id", "title", "body"}.issubset(payload):
                response.failure("response did not satisfy the post workload shape")


@events.test_start.add_listener
def enforce_target_policy(environment, **_kwargs) -> None:
    """Validate the effective host after CLI/web configuration and before traffic."""
    parsed_options = getattr(environment, "parsed_options", None)
    target = (
        getattr(environment, "host", None)
        or getattr(parsed_options, "host", None)
        or PostsUser.host
    )
    validate_load_target(target)
