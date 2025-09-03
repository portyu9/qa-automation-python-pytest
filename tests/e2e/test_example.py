"""
End‑to‑end test for example.com.

This test uses the ``page`` fixture provided by the ``pytest‑playwright``
plugin.  It navigates to example.com and asserts that the page title and
heading match expectations.  The test is marked as ``e2e``.
"""

import pytest

pytest.importorskip("playwright.sync_api")


@pytest.mark.e2e
def test_example_page(page) -> None:
    # Navigate to the example site
    page.goto("https://example.com")
    # Assert that the title is correct
    assert page.title() == "Example Domain"
    # Assert that the heading contains the expected text
    heading = page.locator("h1").inner_text()
    assert heading.strip() == "Example Domain"