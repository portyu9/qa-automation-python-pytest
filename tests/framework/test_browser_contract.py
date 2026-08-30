import json

import pytest

from src.browser import _redact_url, capture_failure_evidence


@pytest.mark.unit
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (
            "https://user:password@example.test:8443/app/page?access_token=secret#debug",
            "https://example.test:8443/app/page",
        ),
        ("http://127.0.0.1:5000/ui?token=secret", "http://127.0.0.1:5000/ui"),
        ("not-a-url", "<invalid-url>"),
        ("", ""),
    ],
)
def test_browser_evidence_url_redaction(raw, expected):
    assert _redact_url(raw) == expected


@pytest.mark.unit
def test_browser_evidence_paths_remain_unique_after_label_redaction(tmp_path):
    class StubDriver:
        current_url = "https://example.test/ui?token=secret"

        def save_screenshot(self, path):
            with open(path, "wb") as screenshot:
                screenshot.write(b"png")
            return True

    driver = StubDriver()
    nodeid = "tests/ui/test_login.py::test_login[password=secret]"

    capture_failure_evidence(
        driver,
        report_dir=tmp_path,
        nodeid=nodeid,
        run_id="run-42",
    )
    capture_failure_evidence(
        driver,
        report_dir=tmp_path,
        nodeid=nodeid,
        run_id="run-42",
    )

    evidence_dir = tmp_path / "browser"
    json_files = sorted(evidence_dir.glob("*.json"))
    screenshot_files = sorted(evidence_dir.glob("*.png"))

    assert len(json_files) == 2
    assert len(screenshot_files) == 2
    assert json_files[0].stem != json_files[1].stem
    for metadata_path in json_files:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert "secret" not in metadata["test"]
        assert metadata["currentUrl"] == "https://example.test/ui"
        assert metadata["screenshot"]
