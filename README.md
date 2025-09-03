# QA Automation Demo: Python with PyTest & Playwright

I built this repository to demonstrate how I design a production-ready QA automation framework in Python. It uses PyTest for test execution and Playwright for browser automation. The goal is to show how I layer tests across unit, API, database and UI and keep them maintainable.

## Features

- **Unit & component tests with PyTest** – I write concise tests that validate the core business logic in `src/calc.py` and other helpers in isolation. Fixtures and parametrisation make these tests expressive and reusable.
- **API tests using Requests** – My `api_client.py` wraps `requests` and exposes a function to fetch posts from JSONPlaceholder. The tests assert status codes and response structures.
- **Mock server** – I provide a lightweight Flask mock API in `mock/server.py` that serves sample JSON from `mock/data.json`, allowing offline development and deterministic API tests.
- **Database & repository layer** – I use SQLite together with SQLAlchemy in `db.py` to define a simple `User` model. The repository class in `src/repositories/user_repository.py` encapsulates queries and seeding for database tests.
- **Playwright Page Object Model** – The POM class in `src/pages/home_page.py` encapsulates selectors and actions for the Playwright docs site. This abstraction keeps my end-to-end tests maintainable.
- **End‑to‑end tests across browsers** – The `tests/e2e` directory contains cross-browser E2E tests using Playwright’s sync API, configured to run in Chromium, Firefox and WebKit. The tests verify content and navigation on real public sites (`example.com` and the Playwright docs).
- **Configuration & fixtures** – `pytest.ini` configures default markers and test paths. Shared fixtures in `conftest.py` spin up the database, the mock server and the Playwright browser context.
- **Scripts** – I document commands in the README. You can run unit/API/DB tests with `pytest`, run E2E tests with `pytest -m e2e`, and start the mock server with `python mock/server.py`.

## Project structure

```
mock/
├── data.json        # Seed data for the mock API
├── server.py        # Flask server serving mock endpoints

src/
├── api_client.py               # HTTP client using requests
├── calc.py                     # Calculator module
├── db.py                       # SQLAlchemy models and helper
├── pages/
│   └── home_page.py            # Playwright POM for docs site
├── repositories/
│   └── user_repository.py      # Repository abstraction for users

tests/
├── api/
│   └── test_posts.py           # API tests for api_client
├── db/
│   └── test_users.py           # DB tests using SQLAlchemy & repository
├── e2e/
│   ├── test_example.py         # Cross-browser E2E test for example.com
│   └── test_home.py            # E2E test using POM for Playwright docs
├── unit/
│   └── test_calc.py            # Unit tests for calculator

conftest.py            # Shared PyTest fixtures
pytest.ini             # PyTest configuration
requirements.txt       # Python dependencies
```

## Getting started

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Run unit, API and DB tests**:
   ```bash
   pytest -m "unit or api or db"
   ```
   or simply `pytest` to run everything except E2E tests.

3. **Run end‑to‑end tests**:
   ```bash
   pytest -m e2e
   ```
   The E2E tests use Playwright’s sync API and run headless by default. Set the `PLAYWRIGHT_HEADFUL=1` environment variable to see the browser.

4. **Start the mock API**:
   ```bash
   python mock/server.py
   ```

   This starts a Flask server at http://localhost:5000 serving endpoints defined in `mock/data.json`.

## Notes

- I keep my tests deterministic by seeding the in-memory SQLite database before each run and using a local mock API.
- The Page Object Model pattern encapsulates UI selectors and actions to reduce maintenance.
- You can extend this framework by adding more POM classes, API endpoints, or migrating to a different database without changing tests.
