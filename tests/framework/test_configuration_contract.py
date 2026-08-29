import pytest

from src.config import TestSettings as RuntimeSettings


@pytest.mark.unit
def test_settings_normalize_url_and_boolean(monkeypatch):
    monkeypatch.setenv("TEST_BASE_URL", "https://example.test/")
    monkeypatch.setenv("TEST_HEADLESS", "no")
    monkeypatch.setenv("TEST_BROWSER", "firefox")
    monkeypatch.setenv("TEST_RUN_ID", "contract-test-run")

    settings = RuntimeSettings.from_env()

    assert settings.base_url == "https://example.test"
    assert settings.headless is False
    assert settings.browser == "firefox"
    assert settings.run_id == "contract-test-run"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("TEST_BASE_URL", "localhost:8080"),
        ("TEST_BASE_URL", "https://:443"),
        ("TEST_BASE_URL", "https://example.test:not-a-port"),
        ("TEST_BASE_URL", "https://user:password@example.test"),
        ("TEST_BASE_URL", "https://example.test/api?access_token=secret"),
        ("TEST_BASE_URL", "https://example.test/api#fragment"),
        ("TEST_HEADLESS", "sometimes"),
        ("TEST_BROWSER", "internet-explorer"),
        ("TEST_RETRY_TOTAL", "-1"),
        ("TEST_READ_TIMEOUT_SECONDS", "0"),
    ],
)
def test_invalid_settings_fail_before_test_execution(monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError):
        RuntimeSettings.from_env()