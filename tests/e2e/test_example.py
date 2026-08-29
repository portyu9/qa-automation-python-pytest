"""Deterministic browser workflow test for the repository-local UI fixture."""

import pytest
from selenium.webdriver.remote.webdriver import WebDriver

from src.config import TestSettings
from src.pages.home_page import HomePage


@pytest.mark.e2e
@pytest.mark.smoke
def test_local_fixture_navigation(driver: WebDriver) -> None:
    settings = TestSettings.from_env()
    home = HomePage(
        driver,
        base_url=settings.ui_base_url,
        timeout_seconds=settings.browser_timeout_seconds,
    ).open()

    assert home.page_title_text() == "Quality Engineering Fixture"

    home.open_details()

    assert home.details_title_text() == "Fixture Details"
