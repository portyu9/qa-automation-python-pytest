# QA Automation Demo: Python with PyTest & Playwright

This repository demonstrates a production-ready QA automation framework in Python. It combines PyTest for test execution with Playwright for browser automation, Requests for API interactions, SQLAlchemy for ORM, Locust for load testing, and OWASP ZAP for security scanning. The goal is to show how to layer tests across unit, API, database, performance, security, and UI and keep them maintainable with GitHub Actions CI.

## Features

- **Unit & component tests** – Validate the core business logic in `src/calc.py` and other helpers in isolation using PyTest fixtures and parametrization.
- **API tests** – `tests/api/test_posts.py` exercises the JSONPlaceholder posts endpoint through the helper in `src/api_client.py`, checking status codes and response structures.
- **Database & repository layer** – `src/db.py` uses SQLite together with SQLAlchemy to define a simple `User` model and helper functions. A repository in `src/repositories/user_repository.py` encapsulates queries and seeding for database tests. Tests in `tests/db/test_users.py` verify that the repository behaves correctly.
- **Playwright Page Object Model** – The page object class in `src/pages/home_page.py` encapsulates selectors and actions for the Playwright docs site, enabling maintainable UI tests.
- **Cross-browser end-to-end tests** – The `tests/e2e` directory contains cross-browser end-to-end tests using Playwright’s sync API, configured to run in Chromium, Firefox and WebKit. These tests navigate real public sites (such as example.com and the Playwright docs) and verify content and navigation.
- **Mock server** – `mock/server.py` implements a lightweight Flask API that serves sample JSON from `mock/data.json` to support offline development and deterministic API tests.
- **Load and performance testing** – A Locust load test is defined in `performance/locustfile.py` to simulate concurrent users hitting the posts API. A placeholder test in `tests/performance/test_load.py` ensures the file exists and directs you to run Locust via the CLI.
- **Security testing** – `tests/security/test_security.py` provides a skeleton for integrating automated security scanning using OWASP ZAP. Extend it with the ZAP CLI or API to scan the target application for vulnerabilities.
- **Contract testing** – `contract/openapi.yaml` defines an OpenAPI specification for the mock server. Contract tests can validate that API responses conform to this specification.
- **Configuration & fixtures** – `pytest.ini` configures markers and default test paths. Shared fixtures in `conftest.py` provide a seeded database, the Flask mock server, and a Playwright browser context.
- **Scripts and commands** – The commands to run each suite are described below. Use `pytest` markers to run specific suites, start the mock server with `python mock/server.py`, and run Locust and ZAP separately for load and security scans.

## Project structure

```
mock/
├── data.json            # Seed data for the mock API
├── server.py            # Flask server serving endpoints

src/
├── api_client.py        # HTTP client using requests
├── calc.py              # Calculator module
├── db.py                # SQLAlchemy models and helper functions
├── pages/               # Playwright Page Object Model
│   └── home_page.py
├── repositories/
│   └── user_repository.py  # Repository abstraction for users

tests/
├── api/
│   └── test_posts.py        # API tests for api_client
├── db/
│   └── test_users.py        # Database tests using SQLAlchemy & repository
├── e2e/
│   ├── test_example.py      # Cross-browser E2E test for example.com
│   └── test_home.py         # E2E test using POM for Playwright docs
├── performance/
│   └── test_load.py         # Placeholder and marker for load tests
├── security/
│   └── test_security.py     # Skeleton for OWASP ZAP security tests
├── unit/
│   └── test_calc.py         # Unit tests for calculator

performance/
└── locustfile.py            # Locust load test script

contract/
└── openapi.yaml             # OpenAPI spec for the mock API

conftest.py                  # Shared PyTest fixtures
pytest.ini                   # PyTest configuration
requirements.txt             # Python dependencies
```

## Getting started

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Run unit, API and database tests**

   Use markers to run specific suites or run everything except end-to-end tests:

   ```bash
   pytest -m "unit or api or db"
   pytest    # runs all tests except those marked as e2e, performance or security
   ```

3. **Run end-to-end tests**

   ```bash
   pytest -m e2e
   ```

   These tests use Playwright’s sync API and run headless by default. Set the `PLAYWRIGHT_HEADFUL=1` environment variable to view the browser.

4. **Run performance placeholder tests**

   The placeholder test in `tests/performance/test_load.py` ensures the Locust file exists. To perform an actual load test, run Locust directly:

   ```bash
   locust -f performance/locustfile.py --host=https://jsonplaceholder.typicode.com
   ```

   Then open the Locust web UI at `http://localhost:8089` to configure and start the test.

5. **Run security scan**

   The `tests/security` directory contains a skeleton for OWASP ZAP integration. Use the ZAP CLI or API to scan your target application. For example:

   ```bash
   zap-cli quick-scan --self-contained --spider-url=https://example.com https://example.com
   ```

6. **Start the mock API**

   ```bash
   python mock/server.py
   ```

   This command starts a Flask server at `http://localhost:5000` serving endpoints defined in `mock/data.json`.

## Notes

- Tests are deterministic: the in-memory SQLite database is seeded before each run and a local mock API is used to eliminate external dependencies.
- The Page Object Model encapsulates UI selectors and actions to reduce maintenance.
- The framework is extensible: add more page object classes, API endpoints, or migrate to a different database without changing tests.
<!-- Minor note: added for commit message consistency -->
 
