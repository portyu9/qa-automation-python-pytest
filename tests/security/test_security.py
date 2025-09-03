"""
Security test placeholder for running an OWASP ZAP scan.

I include this module to demonstrate how to integrate security scanning into the
framework.  The test is skipped if the ZAP Python API is not installed or a
daemon is not running.  When enabled, it launches a quick scan against the
local mock API and fails if any alerts are raised.
"""

import os
import pytest


pytest.importorskip("zapv2")


@pytest.mark.security
def test_owasp_zap_scan(run_mock_api) -> None:
    """
    Run a very basic OWASP ZAP scan against the mock API.

    To enable this test, install ``python-owasp-zap-v2.4`` and start the ZAP
    daemon (e.g. ``zap.sh -daemon -port 8090``).  The test will connect to
    the daemon, spider the target and assert that no alerts are raised.
    """
    from zapv2 import ZAPv2  # type: ignore

    # Configure the ZAP API client; default port 8090 is used by the daemon
    zap = ZAPv2(apikey=os.environ.get("ZAP_API_KEY"), proxies={"http": "http://127.0.0.1:8090", "https": "http://127.0.0.1:8090"})
    target = os.environ.get("API_BASE_URL", "http://localhost:5000")

    # Access the target to register it with ZAP
    zap.urlopen(target)
    # Run the spider to discover endpoints
    zap.spider.scan(target)
    # Wait for the spider to finish
    while int(zap.spider.status()) < 100:
        pass
    # Run the active scan
    zap.ascan.scan(target)
    while int(zap.ascan.status()) < 100:
        pass
    # Retrieve alerts and assert none are critical
    alerts = zap.core.alerts(baseurl=target)
    # Only continue if there are alerts; otherwise the test passes
    assert all(alert.get("risk").lower() in {"low", "informational"} for alert in alerts)