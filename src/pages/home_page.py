from playwright.sync_api import Page, Locator


class HomePage:
    """
    Page object for the Playwright home page. Encapsulates navigation and selectors so my UI tests remain
    resilient to UI changes. By centralising selectors and common actions here, I can update them in one
    place when the site changes.
    """

    def __init__(self, page: Page) -> None:
        self.page = page
        # Define selectors centrally
        self.hero_title_selector = "h1"
        self.get_started_selector = "text=Get started"

    def goto(self) -> None:
        """Navigate to the Playwright documentation home page."""
        self.page.goto("https://playwright.dev/")

    def hero_title(self) -> Locator:
        """Return a locator for the hero title element used for assertions."""
        return self.page.locator(self.hero_title_selector)

    def click_get_started(self) -> None:
        """Click the 'Get started' link in the hero section to navigate to the docs."""
        self.page.locator(self.get_started_selector).click()
