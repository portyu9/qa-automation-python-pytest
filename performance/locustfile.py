"""Governed Locust workload for the repository-owned posts API.

The default target is loopback. External load requires both an explicit opt-in and
an exact host allowlist entry so changing ``--host`` alone cannot redirect traffic
toward an arbitrary system.
"""

from __future__ import annotations

import os

from locust import HttpUser, between, events, task

from performance.target_policy import DEFAULT_TARGET, validate_load_target


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
