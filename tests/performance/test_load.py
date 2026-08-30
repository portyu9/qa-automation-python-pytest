"""Fast contracts for the governed Locust workload."""

from __future__ import annotations

import pytest

from performance.target_policy import DEFAULT_TARGET, validate_load_target


@pytest.mark.performance
@pytest.mark.parametrize(
    "target",
    [
        DEFAULT_TARGET,
        "http://localhost:5000",
        "http://[::1]:5000",
    ],
)
def test_loopback_load_targets_are_safe_without_external_opt_in(target: str) -> None:
    assert validate_load_target(target, {}) == target


@pytest.mark.performance
@pytest.mark.parametrize(
    "target",
    [
        "",
        "localhost:5000",
        "ftp://127.0.0.1/resource",
        "http://user:password@127.0.0.1:5000",
        "http://127.0.0.1:0",
        "http://127.0.0.1:5000?token=secret",
        "http://127.0.0.1:5000#fragment",
        "https://example.test/api",
    ],
)
def test_unsafe_or_unapproved_load_targets_fail_before_traffic(target: str) -> None:
    with pytest.raises(ValueError):
        validate_load_target(target, {})


@pytest.mark.performance
def test_external_load_requires_opt_in_and_exact_host_allowlist() -> None:
    target = "https://performance.example.test/api"

    with pytest.raises(ValueError, match="PERF_ALLOWED_HOSTS"):
        validate_load_target(
            target,
            {"PERF_ALLOW_EXTERNAL": "true", "PERF_ALLOWED_HOSTS": "other.example.test"},
        )

    assert validate_load_target(
        target,
        {
            "PERF_ALLOW_EXTERNAL": "true",
            "PERF_ALLOWED_HOSTS": "performance.example.test",
        },
    ) == target
