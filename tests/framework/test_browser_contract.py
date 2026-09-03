import json
from types import SimpleNamespace

import pytest

from conftest import _finalize_browser
from src.browser import (
    _ResourceSafeFirefoxService,
    _redact_url,
    capture_failure_evidence,
    create_driver,
)
from src.config import TestSettings as RuntimeSettings


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


@pytest.mark.unit
def test_browser_teardown_quits_driver_when_failure_evidence_raises(monkeypatch):
    events = []

    class StubDriver:
        def quit(self):
            events.append("quit")

    def fail_evidence(*args, **kwargs):
        del args, kwargs
        events.append("evidence")
        raise OSError("evidence filesystem unavailable")

    monkeypatch.setattr("conftest.capture_failure_evidence", fail_evidence)
    request = SimpleNamespace(
        node=SimpleNamespace(
            nodeid="tests/e2e/test_example.py::test_failure",
            rep_call=SimpleNamespace(failed=True),
        )
    )
    settings = RuntimeSettings(
        base_url="http://127.0.0.1:5000",
        ui_base_url="http://127.0.0.1:5000/ui",
        browser="chrome",
        headless=True,
        browser_timeout_seconds=10.0,
        connect_timeout_seconds=5.0,
        read_timeout_seconds=15.0,
        retry_total=2,
        run_id="teardown-contract",
    )

    with pytest.raises(OSError, match="evidence filesystem unavailable"):
        _finalize_browser(StubDriver(), request=request, settings=settings)

    assert events == ["evidence", "quit"]


@pytest.mark.unit
def test_firefox_driver_uses_resource_safe_service(monkeypatch):
    captured = {}

    class StubDriver:
        def set_window_size(self, width, height):
            captured["window"] = (width, height)

        def implicitly_wait(self, seconds):
            captured["implicit_wait"] = seconds

        def set_page_load_timeout(self, seconds):
            captured["page_load_timeout"] = seconds

        def set_script_timeout(self, seconds):
            captured["script_timeout"] = seconds

    def fake_firefox(*, options, service):
        captured["options"] = options
        captured["service"] = service
        return StubDriver()

    monkeypatch.setattr("src.browser.webdriver.Firefox", fake_firefox)
    settings = RuntimeSettings(
        base_url="http://127.0.0.1:5000",
        ui_base_url="http://127.0.0.1:5000/ui",
        browser="firefox",
        headless=True,
        browser_timeout_seconds=10.0,
        connect_timeout_seconds=5.0,
        read_timeout_seconds=15.0,
        retry_total=2,
        run_id="firefox-service-contract",
    )

    assert create_driver(settings).__class__ is StubDriver
    assert isinstance(captured["service"], _ResourceSafeFirefoxService)
    assert "-headless" in captured["options"].arguments
    assert captured["window"] == (1440, 1000)
    assert captured["implicit_wait"] == 0
    assert captured["page_load_timeout"] == 10.0
    assert captured["script_timeout"] == 10.0
