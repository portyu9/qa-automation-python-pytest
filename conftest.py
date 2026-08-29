"""Shared pytest fixtures and lifecycle infrastructure."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from selenium.webdriver.remote.webdriver import WebDriver
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from src import pytest_capabilities as capability_plugin
from src.browser import capture_failure_evidence, create_driver
from src.config import TestSettings as RuntimeSettings
from src.db import get_engine, init_db
from src.run_manifest import RunManifest


class _RunManifestPlugin:
    """Collect reports in the controller process, including xdist worker results."""

    def __init__(self, config: pytest.Config) -> None:
        self.config = config
        self.manifest = RunManifest.from_settings(RuntimeSettings.from_env())

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        # Normal outcomes come from the call phase. Setup/teardown failures and
        # setup-time skips are also retained because no call report may exist.
        if report.when != "call" and report.outcome == "passed":
            return
        self.manifest.record(
            nodeid=report.nodeid,
            status=report.outcome,
            phase=report.when,
            duration_seconds=report.duration,
            worker=str(getattr(report, "worker_id", "controller")),
        )

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        del exitstatus
        # xdist workers must never race to write the same manifest. The controller
        # receives their reports and owns the single run-level artifact.
        if hasattr(session.config, "workerinput"):
            return
        report_dir = Path(os.getenv("TEST_REPORT_DIR", "reports"))
        self.manifest.write(report_dir / "run-manifest.json")


def pytest_addoption(parser: pytest.Parser) -> None:
    """Delegate focused capability selection to the framework extension module."""
    capability_plugin.pytest_addoption(parser)


def pytest_configure(config: pytest.Config) -> None:
    """Register operational diagnostics without changing native pytest semantics."""
    capability_plugin.register_capability_marker(config)
    plugin_name = "framework-run-manifest"
    if not config.pluginmanager.hasplugin(plugin_name):
        config.pluginmanager.register(_RunManifestPlugin(config), plugin_name)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply optional capability slicing after pytest has built the collection."""
    capability_plugin.pytest_collection_modifyitems(config, items)


def pytest_report_header(config: pytest.Config) -> str | None:
    """Surface capability slicing through pytest's standard terminal metadata."""
    return capability_plugin.pytest_report_header(config)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo[object]):
    """Expose phase reports to fixtures without replacing pytest's report model."""
    del call
    outcome = yield
    report = outcome.get_result()
    setattr(item, f"rep_{report.when}", report)


def _fixture_log_tail(log_path: Path, max_chars: int = 2_000) -> str:
    try:
        text = log_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "<fixture log unavailable>"
    return text[-max_chars:] or "<fixture log empty>"


def _wait_for_fixture_owner(
    proc: subprocess.Popen[bytes],
    ready_file: Path,
    log_path: Path,
    timeout_seconds: float = 5.0,
) -> None:
    """Require the spawned process to prove it owns the expected listener."""
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        return_code = proc.poll()
        if return_code is not None:
            raise RuntimeError(
                "mock API exited before claiming its listener "
                f"(exit={return_code}): {_fixture_log_tail(log_path)}"
            )

        if ready_file.exists():
            try:
                payload = json.loads(ready_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                # The child publishes by atomic rename, but tolerate a transient
                # filesystem visibility race within the bounded startup window.
                pass
            else:
                expected = {"pid": proc.pid, "host": "127.0.0.1", "port": 5000}
                if payload != expected:
                    raise RuntimeError(
                        f"mock API ownership token mismatch: expected {expected!r}, got {payload!r}"
                    )
                return

        time.sleep(0.05)

    raise RuntimeError(
        "mock API did not claim 127.0.0.1:5000 before the startup deadline: "
        f"{_fixture_log_tail(log_path)}"
    )


@pytest.fixture(scope="session")
def db_engine() -> Generator[Engine, None, None]:
    """Create, seed, and deterministically dispose an in-memory SQLite engine."""
    engine = get_engine()
    init_db(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(db_engine: Engine) -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session and close it deterministically after the test."""
    session = Session(bind=db_engine)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def run_mock_api() -> Generator[None, None, None]:
    """Run the repository-local Flask fixture and verify listener ownership."""
    script_path = Path(__file__).parent / "mock" / "server.py"
    env = os.environ.copy()

    with TemporaryDirectory(prefix="pytest-local-fixture-") as temp_dir:
        temp_path = Path(temp_dir)
        ready_file = temp_path / "ready.json"
        log_path = temp_path / "server.log"
        env["MOCK_READY_FILE"] = str(ready_file)

        with log_path.open("w", encoding="utf-8") as log_handle:
            proc = subprocess.Popen(
                [sys.executable, str(script_path)],
                env=env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
            )

            try:
                _wait_for_fixture_owner(proc, ready_file, log_path)
                yield
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=5)


@pytest.fixture
def local_api_settings(monkeypatch: pytest.MonkeyPatch) -> RuntimeSettings:
    """Return validated settings that target the deterministic loopback API."""
    monkeypatch.setenv("TEST_BASE_URL", "http://127.0.0.1:5000")
    monkeypatch.setenv("TEST_RUN_ID", "local-api-contract")
    return RuntimeSettings.from_env()


@pytest.fixture
def driver(run_mock_api: None, request: pytest.FixtureRequest) -> Generator[WebDriver, None, None]:
    """Own one isolated Selenium WebDriver session per browser test."""
    del run_mock_api
    settings = RuntimeSettings.from_env()
    browser = create_driver(settings)
    try:
        yield browser
    finally:
        call_report = getattr(request.node, "rep_call", None)
        if call_report is not None and call_report.failed:
            capture_failure_evidence(
                browser,
                report_dir=Path(os.getenv("TEST_REPORT_DIR", "reports")),
                nodeid=request.node.nodeid,
                run_id=settings.run_id,
            )
        browser.quit()
