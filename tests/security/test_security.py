"""Optional OWASP ZAP dynamic scan against the deterministic local mock API."""

from __future__ import annotations

import os
import socket
import time
from collections.abc import Callable

import pytest

pytest.importorskip("zapv2")

_ZAP_HOST = "127.0.0.1"
_ZAP_PORT = 8090
_LOCAL_TARGET = "http://127.0.0.1:5000"


def _wait_for_scan(
    status: Callable[[], str], *, timeout_seconds: float = 60.0, poll_seconds: float = 0.25
) -> None:
    """Wait for a ZAP asynchronous scan with a bounded deadline."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if int(status()) >= 100:
            return
        time.sleep(poll_seconds)
    raise TimeoutError(f"ZAP scan did not complete within {timeout_seconds:.0f}s")


@pytest.mark.security
def test_owasp_zap_scan(run_mock_api) -> None:
    """Actively scan only the loopback mock API and reject medium-or-higher alerts."""
    from zapv2 import ZAPv2  # type: ignore

    try:
        with socket.create_connection((_ZAP_HOST, _ZAP_PORT), timeout=2):
            pass
    except OSError:
        pytest.skip(f"ZAP daemon not running on {_ZAP_HOST}:{_ZAP_PORT}")

    proxy = f"http://{_ZAP_HOST}:{_ZAP_PORT}"
    zap = ZAPv2(
        apikey=os.environ.get("ZAP_API_KEY"),
        proxies={"http": proxy, "https": proxy},
    )

    # The active scanner is intentionally hard-bound to the local fixture target.
    # An environment variable cannot redirect this test toward an external system.
    zap.urlopen(_LOCAL_TARGET)
    zap.spider.scan(_LOCAL_TARGET)
    _wait_for_scan(zap.spider.status)

    zap.ascan.scan(_LOCAL_TARGET)
    _wait_for_scan(zap.ascan.status)

    alerts = zap.core.alerts(baseurl=_LOCAL_TARGET)
    unacceptable = [
        alert
        for alert in alerts
        if str(alert.get("risk", "")).strip().lower()
        not in {"low", "informational"}
    ]
    assert not unacceptable, f"ZAP reported medium-or-higher findings: {unacceptable}"
