"""
Shared PyTest fixtures for the QA automation project.

I use these fixtures to centralise setup and teardown logic across tests.  The
database fixtures provide an in‑memory SQLite engine seeded with sample data.
The `run_mock_api` fixture spawns the Flask mock server in a subprocess for
tests that exercise the HTTP API.  An `api_base_url` fixture can override
`API_BASE_URL` so that the client points to the local server during tests.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Generator, Optional

import pytest
from sqlalchemy.orm import Session

from src.db import get_engine, init_db


@pytest.fixture(scope="session")
def db_engine() -> object:
    """Create a new in‑memory SQLite engine and seed it with users.

    This engine is session scoped so it is initialised once per test session.
    """
    engine = get_engine()
    init_db(engine)
    return engine


@pytest.fixture
def db_session(db_engine: object) -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session bound to the in‑memory engine.

    Tests can use this fixture to query or mutate the database.  The session is
    automatically closed after each test.
    """
    session = Session(bind=db_engine)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="session")
def run_mock_api() -> Generator[None, None, None]:
    """Start the Flask mock API in a subprocess for the duration of the session.

    This fixture runs the server defined in ``mock/server.py`` on port 5000.  It
    sleeps briefly to ensure the server is ready before yielding control.  At
    teardown it terminates the subprocess.  Tests that need the server should
    request this fixture explicitly.
    """
    # Compute the path to server.py relative to this file
    script_path = Path(__file__).parent / "mock" / "server.py"
    # Launch the server as a background process
    env = os.environ.copy()
    proc = subprocess.Popen([
        "python",
        str(script_path),
    ], env=env)
    # Give the server a moment to start
    time.sleep(1)
    try:
        yield
    finally:
        proc.terminate()
        proc.wait(timeout=5)


@pytest.fixture
def api_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Override the API base URL for tests to point at the local mock server.

    When this fixture is requested, it sets the ``API_BASE_URL`` environment
    variable for the duration of the test.  The ``api_client`` module reads
    this variable on import.
    """
    monkeypatch.setenv("API_BASE_URL", "http://localhost:5000")
    # The yield allows the fixture to be used with a with‑statement if desired
    yield