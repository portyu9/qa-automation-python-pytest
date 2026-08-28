# Python / pytest Test Automation Framework

A pytest-based automation framework for unit, API, contract, database, browser, security, and performance verification. The repository is organized so test intent is separated from infrastructure concerns and so the same test suite can run locally and in CI with explicit environment configuration.

## Engineering goals

- deterministic, repeatable test execution;
- clear separation between test cases, domain helpers, transport clients, persistence access, and page objects;
- fail-fast configuration validation before external systems are touched;
- bounded network timeouts and retry behavior for transient transport failures only;
- explicit test taxonomy through pytest markers;
- parallel-safe tests by default, with serial execution reserved for shared-state cases;
- diagnostic artifacts suitable for CI triage;
- contract, security, and performance checks kept distinct from the fast functional gate;
- no credentials or environment-specific secrets committed to the repository.

## Repository layout

```text
.
├── .github/workflows/ci.yml       # quality, functional, and browser CI gates
├── contract/                      # API contract artifacts
├── docs/                          # architecture and test strategy
├── mock/                          # local deterministic service
├── performance/                   # Locust workload definitions
├── src/
│   ├── config.py                  # validated runtime settings
│   ├── http_client.py             # bounded/retrying HTTP transport
│   ├── api_client.py              # domain API access
│   ├── db.py                      # persistence helpers
│   ├── pages/                     # browser page abstractions
│   └── repositories/              # data-access abstractions
├── tests/
│   ├── unit/
│   ├── api/
│   ├── db/
│   ├── e2e/
│   ├── security/
│   ├── performance/
│   └── framework/                 # framework self-tests
├── conftest.py                    # shared pytest fixtures/hooks
├── pytest.ini                     # marker and execution policy
└── pyproject.toml                 # lint/coverage tool policy
```

## Runtime configuration

Copy `.env.example` values into the environment used to execute tests. The framework deliberately reads environment variables rather than loading secrets from a committed file.

| Variable | Purpose | Default |
| --- | --- | --- |
| `TEST_BASE_URL` | primary application/API base URL | `https://jsonplaceholder.typicode.com` |
| `TEST_BROWSER` | browser selector used by UI fixtures | `chromium` |
| `TEST_HEADLESS` | run browser headlessly | `true` |
| `TEST_CONNECT_TIMEOUT_SECONDS` | TCP/TLS connection timeout | `5` |
| `TEST_READ_TIMEOUT_SECONDS` | response read timeout | `15` |
| `TEST_RETRY_TOTAL` | transient transport retry budget | `2` |
| `TEST_RUN_ID` | correlation identifier emitted with requests | generated UUID |

`src/config.py` validates URL schemes, positive timeout values, supported browser names, and boolean syntax. Invalid configuration fails before a test makes a network call.

## Installation

```bash
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

## Execution model

Fast functional gate:

```bash
pytest -m "not e2e and not performance and not security" --cov=src --cov-report=term-missing
```

API only:

```bash
pytest tests/api -m api
```

Browser suite:

```bash
pytest tests/e2e --browser chromium
```

Parallel execution for tests that do not share mutable state:

```bash
pytest -n auto -m "not serial"
```

Security and load tests are intentionally separate because they have different prerequisites and failure semantics:

```bash
pytest tests/security
locust -f performance/locustfile.py
```

## Marker policy

Markers are declared centrally and `--strict-markers` is enabled. New test categories must be registered in `pytest.ini`; ad-hoc marker names are rejected. The default taxonomy is `unit`, `api`, `contract`, `integration`, `db`, `e2e`, `smoke`, `security`, `performance`, and `serial`.

A test should use the narrowest applicable marker. `serial` is a constraint, not a test type, and should only be used when isolation cannot be achieved economically.

## HTTP reliability policy

`src/http_client.py` provides a reusable `HttpClient` with:

- separate connect/read timeouts;
- retry only for idempotent methods and transient status codes;
- exponential backoff through urllib3 retry semantics;
- a per-run `X-Test-Run-Id` correlation header;
- a single session for connection pooling;
- explicit `close()` / context-manager lifecycle.

Application assertions remain in tests or domain clients. The transport layer does not hide 4xx/5xx responses by automatically calling `raise_for_status()`.

## Test data and isolation

Prefer generated data or API-created fixtures over static shared records. Tests that create state should own cleanup. Database tests should use transactions or disposable schemas/containers where the target system permits it. Browser tests should prepare state through APIs instead of UI setup when doing so does not invalidate the behavior under test.

Never make test ordering a dependency. A test must be able to run alone, repeatedly, and in a different worker process unless explicitly marked `serial`.

## Failure diagnostics

CI always publishes JUnit and coverage outputs from the functional gate. Browser jobs retain Playwright/pytest artifacts when available. When adding new integrations, diagnostics should include request correlation IDs and safe metadata, while authentication tokens, cookies, authorization headers, passwords, and connection strings must be redacted.

## CI quality gates

The GitHub Actions workflow separates concerns:

1. **quality** — install dependencies, run Ruff, and compile Python sources;
2. **functional** — execute fast tests across a supported Python matrix with JUnit and coverage output;
3. **browser** — install Chromium and execute the browser suite separately.

This keeps pull-request feedback fast while preserving higher-cost UI validation and actionable artifacts.

## Adding a test

1. Place the test in the directory matching the system boundary.
2. Reuse a domain client, repository, or page abstraction instead of embedding transport/selector details in the test.
3. Apply a registered marker.
4. Keep arrange/act/assert intent visible.
5. Avoid sleeps; wait on observable state with bounded timeouts.
6. Ensure created state is unique and cleaned up.
7. Verify the test can run independently and, unless constrained, in parallel.
8. Add or update schema/contract fixtures when the external interface changes.

## Design references

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for component boundaries and [`docs/TEST_STRATEGY.md`](docs/TEST_STRATEGY.md) for selection, flake management, test data, CI, and release-gate guidance.
