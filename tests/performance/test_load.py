"""
Placeholder performance tests.

This module contains a minimal test to ensure that the Locust file is present.
Full load testing is performed via the Locust CLI; to run a load test, use
``locust -f performance/locustfile.py``.  These tests are skipped if Locust
is not installed.
"""

import os
import pytest


pytest.importorskip("locust")


@pytest.mark.performance
def test_locustfile_exists() -> None:
    """Ensure the locustfile exists in the performance directory."""
    assert os.path.isfile(os.path.join(os.path.dirname(__file__), "..", "..", "performance", "locustfile.py"))
    
