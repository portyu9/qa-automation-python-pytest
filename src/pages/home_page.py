"""Selenium page object for the deterministic browser fixture."""

from __future__ import annotations

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class HomePage:
    """Expose stable user-facing interactions for the local UI fixture."""

    _PAGE_TITLE = (By.CSS_SELECTOR, "[data-testid='page-title']")
    _DETAILS_LINK = (By.CSS_SELECTOR, "[data-testid='details-link']")
    _DETAILS_TITLE = (By.CSS_SELECTOR, "[data-testid='details-title']")

    def __init__(
        self,
        driver: WebDriver,
        *,
        base_url: str,
        timeout_seconds: float,
    ) -> None:
        self.driver = driver
        self.base_url = base_url.rstrip("/")
        self.wait = WebDriverWait(driver, timeout_seconds)

    def open(self) -> "HomePage":
        """Navigate to the configured UI target and wait for its primary landmark."""
        self.driver.get(self.base_url)
        self.wait.until(EC.visibility_of_element_located(self._PAGE_TITLE))
        return self

    def page_title_text(self) -> str:
        """Return the visible primary heading after explicit synchronization."""
        return self.wait.until(EC.visibility_of_element_located(self._PAGE_TITLE)).text

    def open_details(self) -> None:
        """Follow the fixture's details link and wait for the destination landmark."""
        self.wait.until(EC.element_to_be_clickable(self._DETAILS_LINK)).click()
        self.wait.until(EC.visibility_of_element_located(self._DETAILS_TITLE))

    def details_title_text(self) -> str:
        """Return the details-page heading after navigation completes."""
        return self.wait.until(EC.visibility_of_element_located(self._DETAILS_TITLE)).text
