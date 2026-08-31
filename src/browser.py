"""Selenium WebDriver construction and bounded browser-failure evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.remote.webdriver import WebDriver

from src.config import TestSettings
from src.run_manifest import redact_text


_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")


class _ResourceSafeFirefoxService(FirefoxService):
    """Stop geckodriver without Selenium's unsupported remote-shutdown probe.

    Selenium 4.48's base Service probes ``/shutdown`` through ``urllib`` before
    terminating the driver process. Geckodriver returns HTTP 405 for that
    endpoint; on Python 3.14 the caught-but-unclosed ``HTTPError`` response is
    surfaced as a ``ResourceWarning``. The base ``Service.stop`` method always
    terminates the process after this hook, so skipping the unsupported probe
    preserves deterministic process cleanup without suppressing resource
    warnings for framework-owned code.
    """

    def send_remote_shutdown_command(self) -> None:
        """Let the inherited stop path terminate geckodriver directly."""


def create_driver(settings: TestSettings) -> WebDriver:
    """Create a Selenium driver from validated framework settings.

    Selenium Manager resolves the matching driver when one is not already
    available on PATH. The framework keeps implicit waits disabled so all
    synchronization remains explicit and attributable.
    """
    if settings.browser == "chrome":
        options = webdriver.ChromeOptions()
        if settings.headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1440,1000")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        driver: WebDriver = webdriver.Chrome(options=options)
    elif settings.browser == "firefox":
        options = webdriver.FirefoxOptions()
        if settings.headless:
            options.add_argument("-headless")
        driver = webdriver.Firefox(
            options=options,
            service=_ResourceSafeFirefoxService(),
        )
        driver.set_window_size(1440, 1000)
    else:  # Defensive guard; TestSettings rejects unsupported values first.
        raise ValueError(f"unsupported browser {settings.browser!r}")

    driver.implicitly_wait(0)
    driver.set_page_load_timeout(settings.browser_timeout_seconds)
    driver.set_script_timeout(settings.browser_timeout_seconds)
    return driver


def capture_failure_evidence(
    driver: WebDriver,
    *,
    report_dir: Path,
    nodeid: str,
    run_id: str,
) -> None:
    """Write bounded browser diagnostics for a failed test.

    The metadata intentionally excludes cookies, local/session storage,
    response bodies, page source, and URL user-info/query/fragment. Test labels
    are redacted/bounded before persistence because parameter values can carry
    sensitive material. Richer surfaces should only be collected by an
    application-specific evidence policy.
    """
    evidence_dir = report_dir / "browser"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    safe_nodeid = redact_text(nodeid)
    label = _SAFE_NAME.sub("-", safe_nodeid).strip("-")[:80] or "browser-test"
    # A random, non-secret-derived suffix prevents redaction/truncation from
    # collapsing distinct failures onto the same artifact path.
    stem = f"{label}-{uuid4().hex}"

    screenshot_name = f"{stem}.png"
    screenshot_path = evidence_dir / screenshot_name
    screenshot_written = False
    try:
        screenshot_written = driver.save_screenshot(str(screenshot_path))
    except WebDriverException:
        screenshot_written = False

    metadata = {
        "schemaVersion": 1,
        "runId": run_id,
        "test": safe_nodeid,
        "currentUrl": _redact_url(_safe_current_url(driver)),
        "screenshot": screenshot_name if screenshot_written else None,
    }
    (evidence_dir / f"{stem}.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _safe_current_url(driver: WebDriver) -> str:
    try:
        return driver.current_url
    except WebDriverException:
        return ""


def _redact_url(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return "<invalid-url>"

    hostname = parsed.hostname or ""
    if not hostname:
        return "<invalid-url>"

    netloc = hostname
    try:
        if parsed.port is not None:
            netloc = f"{hostname}:{parsed.port}"
    except ValueError:
        return "<invalid-url>"

    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))