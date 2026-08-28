"""Shared pytest fixtures and lifecycle infrastructure."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from src.db import get_engine, init_db


def _wait_for_port(host: str, port: int, timeout_seconds: float = 5.0) -> None:
    """Wait for a TCP listener with a bounded deadline instead of a fixed sleep."""
    deadline = time.monotonic() + timeout_seconds
    last_error: OSError | None = None

    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.25):
                return
        except OSError as error:
            last_error = error
            time.sleep(0.1)

    raise RuntimeError(f"mock API did not become ready on {host}:{port}") from last_error


@pytest.fixture(scope="session")
def db_engine() -> object:
    """Create and seed an in-memory SQLite engine for database tests."""
    engine = get_engine()
    init_db(engine)
    return engine


@pytest.fixture
def db_session(db_engine: object) -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session and close it deterministically after the test."""
    session = Session(bind=db_engine)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def run_mock_api() -> Generator[None, None, None]:
    """Run the local Flask mock API for the duration of the test session."""
    script_path = Path(__file__).parent / "mock" / "server.py"
    env = os.environ.copy()
    proc = subprocess.Popen([sys.executable, str(script_path)], env=env)

    try:
        _wait_for_port("127.0.0.1", 5000)
        yield
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


@pytest.fixture
def api_base_url(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Point API-client tests at the local deterministic mock service."""
    monkeypatch.setenv("API_BASE_URL", "http://localhost:5000")
    yield
