import pytest

from src.config import TestSettings as RuntimeSettings


@pytest.mark.unit
def test_committed_defaults_target_repository_local_fixture(monkeypatch):
    monkeypatch.delenv("TEST_BASE_URL", raising=False)
    monkeypatch.delenv("TEST_UI_BASE_URL", raising=False)

    settings = RuntimeSettings.from_env()

    assert settings.base_url == "http://127.0.0.1:5000"
    assert settings.ui_base_url == "http://127.0.0.1:5000/ui"


@pytest.mark.unit
def test_settings_normalize_urls_and_boolean(monkeypatch):
    monkeypatch.setenv("TEST_BASE_URL", "https://api.example.test/v1/")
    monkeypatch.setenv("TEST_UI_BASE_URL", "https://ui.example.test/app/")
    monkeypatch.setenv("TEST_HEADLESS", "no")
    monkeypatch.setenv("TEST_BROWSER", "firefox")
    monkeypatch.setenv("TEST_BROWSER_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("TEST_RUN_ID", "contract-test-run")

    settings = RuntimeSettings.from_env()

    assert settings.base_url == "https://api.example.test/v1"
    assert settings.ui_base_url == "https://ui.example.test/app"
    assert settings.headless is False
    assert settings.browser == "firefox"
    assert settings.browser_timeout_seconds == 12.5
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
        ("TEST_UI_BASE_URL", "file:///tmp/test.html"),
        ("TEST_UI_BASE_URL", "https://user:password@example.test/ui"),
        ("TEST_UI_BASE_URL", "https://example.test/ui?token=secret"),
        ("TEST_HEADLESS", "sometimes"),
        ("TEST_BROWSER", "internet-explorer"),
        ("TEST_BROWSER_TIMEOUT_SECONDS", "0"),
        ("TEST_RETRY_TOTAL", "-1"),
        ("TEST_READ_TIMEOUT_SECONDS", "0"),
    ],
)
def test_invalid_settings_fail_before_test_execution(monkeypatch, name, value):
    monkeypatch.setenv(name, value)

    with pytest.raises(ValueError):
        RuntimeSettings.from_env()
