"""Selenium WebDriver construction and bounded browser-failure evidence."""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.remote.webdriver import WebDriver

from src.config import TestSettings


_SAFE_NAME = re.compile(r"[^A-Za-z0-9_.-]+")


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
        driver = webdriver.Firefox(options=options)
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
    response bodies, page source, and URL user-info/query/fragment. Those
    surfaces commonly contain credentials or customer data and should only be
    collected by an application-specific evidence policy.
    """
    evidence_dir = report_dir / "browser"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    stem = _SAFE_NAME.sub("-", nodeid).strip("-")[:120] or "browser-test"

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
        "test": nodeid,
        "currentUrl": _redact_url(_safe_current_url(driver)),
        "screenshot": screenshot_name if screenshot_written else None,
    }
    (evidence_dir / f"{stem}.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
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
