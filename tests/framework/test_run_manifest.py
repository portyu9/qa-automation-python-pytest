from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.run_manifest import (
    RunManifest,
    redact_mapping,
    redact_text,
    redact_url,
    safe_slug,
)


def test_safe_slug_is_deterministic_and_filesystem_friendly() -> None:
    assert safe_slug("tests/api/test_posts.py::test post[case/1]") == (
        "tests-api-test_posts.py-test-post-case-1"
    )


def test_redaction_removes_secret_fields_url_components_and_bounded_labels() -> None:
    assert redact_mapping({"api_key": "secret", "browser": "chromium"}) == {
        "api_key": "<redacted>",
        "browser": "chromium",
    }
    assert redact_url(
        "https://user:password@example.com/api?access_token=secret#fragment"
    ) == "https://example.com/api"
    assert redact_url("http://[::1]:8080/path?token=secret") == (
        "http://[::1]:8080/path"
    )
    redacted = redact_text(
        "case[password=secret at https://user:password@example.com/api?token=secret]"
    )
    assert "password=<redacted>" in redacted
    assert "user:password" not in redacted
    assert "?token=secret" not in redacted
    assert redact_text("x" * 600).endswith("…<truncated>")


def test_manifest_keeps_the_most_severe_outcome_per_test(tmp_path: Path) -> None:
    manifest = RunManifest(run_id="run-123", runtime={"browser": "chromium"})
    manifest.record(
        nodeid="tests/test_example.py::test_case",
        status="passed",
        phase="call",
        duration_seconds=0.25,
    )
    manifest.record(
        nodeid="tests/test_example.py::test_case",
        status="failed",
        phase="teardown",
        duration_seconds=0.01,
    )

    output = manifest.write(tmp_path / "run-manifest.json")
    payload = json.loads(output.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert payload["run_id"] == "run-123"
    assert payload["summary"] == {
        "failed": 1,
        "passed": 0,
        "skipped": 0,
        "total": 1,
    }
    assert payload["outcomes"][0]["status"] == "failed"
    assert payload["outcomes"][0]["phase"] == "teardown"


def test_manifest_redacts_parameterized_nodeids_and_rejects_nonfinite_durations() -> None:
    manifest = RunManifest(run_id="run-123", runtime={"browser": "chromium"})
    manifest.record(
        nodeid=(
            "tests/test_example.py::test_case[password=secret-"
            "https://user:password@example.test/path?token=secret]"
        ),
        status="failed",
        phase="call",
        duration_seconds=0.1,
    )

    outcome = manifest.as_dict()["outcomes"][0]
    assert "password=<redacted>" in outcome["nodeid"]
    assert "user:password" not in outcome["nodeid"]
    assert "?token=secret" not in outcome["nodeid"]
    assert len(outcome["nodeid"]) <= 512

    with pytest.raises(ValueError, match="finite"):
        manifest.record(
            nodeid="tests/test_example.py::test_nan",
            status="failed",
            phase="call",
            duration_seconds=float("nan"),
        )
