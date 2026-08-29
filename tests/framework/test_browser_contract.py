import pytest

from src.browser import _redact_url


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
