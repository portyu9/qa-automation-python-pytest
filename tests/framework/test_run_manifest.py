from __future__ import annotations

import json
from pathlib import Path

from src.run_manifest import RunManifest, redact_mapping, redact_url, safe_slug


def test_safe_slug_is_deterministic_and_filesystem_friendly() -> None:
    assert safe_slug("tests/api/test_posts.py::test post[case/1]") == (
        "tests-api-test_posts.py-test-post-case-1"
    )


def test_redaction_removes_secret_fields_and_url_user_info() -> None:
    assert redact_mapping({"api_key": "secret", "browser": "chromium"}) == {
        "api_key": "<redacted>",
        "browser": "chromium",
    }
    assert redact_url("https://user:password@example.com/api?q=1") == (
        "https://example.com/api?q=1"
    )


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
