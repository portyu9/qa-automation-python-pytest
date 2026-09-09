# Operations Guide

## Purpose

This guide owns the detailed operating contract for the Python / pytest Quality Engineering Framework: local execution, runtime configuration, deterministic fixtures, browser policy, persistence, CI evidence, dependency maintenance, and failure triage.

The main [`README.md`](../README.md) is intentionally a concise entry point. Deep architectural rationale remains in [`ARCHITECTURE.md`](ARCHITECTURE.md), while test-layer selection and quality strategy remain in [`TEST_STRATEGY.md`](TEST_STRATEGY.md).

## Local command reference

Create an environment and install the interpreter-specific hash lock that matches the active supported Python runtime:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --require-hashes -r requirements-lock/<matching-runtime>.txt
```

Run the deterministic fast suite:

```bash
pytest --ignore=tests/e2e --ignore=tests/performance --ignore=tests/security
```

Useful focused commands:

```bash
ruff check .
python -m compileall -q src tests
python .github/scripts/validate_readme.py

pytest --ignore=tests/e2e --ignore=tests/performance --ignore=tests/security \
  --cov=src --cov-report=term-missing

pytest tests/contract
pytest tests/performance
locust -f performance/locustfile.py --headless --host http://127.0.0.1:5000 \
  --users 1 --spawn-rate 1 --run-time 3s --only-summary
pytest tests/framework/test_pytest_capabilities.py --capability=parametrization
pytest tests/framework/test_pytest_capabilities.py --capability=fixtures
pytest tests/framework/test_pytest_capabilities.py --capability=asyncio --capability=mocking
TEST_BROWSER=chrome pytest tests/e2e -m smoke
TEST_BROWSER=firefox pytest tests/e2e
pytest tests/security -m security
```

`requirements.txt` is the human-maintained direct compatibility input. Production CI installs from the generated interpreter-specific lock under `requirements-lock/` with `pip --require-hashes`. Use `pip install -r requirements.txt` only while intentionally resolving dependency changes and regenerating all supported-runtime locks.

## Runtime configuration

`src/config.py` is the environment boundary. Invalid external values fail before useful network, database, or browser side effects.

| Variable | Purpose | Default |
| --- | --- | --- |
| `TEST_BASE_URL` | API target | `http://127.0.0.1:5000` |
| `TEST_UI_BASE_URL` | Browser target | `http://127.0.0.1:5000/ui` |
| `TEST_BROWSER` | `chrome` or `firefox` | `chrome` |
| `TEST_HEADLESS` | Headless browser mode | `true` |
| `TEST_BROWSER_TIMEOUT_SECONDS` | Browser condition budget | `10` |
| `TEST_CONNECT_TIMEOUT_SECONDS` | HTTP connect budget | `5` |
| `TEST_READ_TIMEOUT_SECONDS` | HTTP read budget | `15` |
| `TEST_RETRY_TOTAL` | Safe-method retry budget | `2` |
| `TEST_RUN_ID` | Cross-layer correlation | generated UUID |
| `TEST_REPORT_DIR` | Evidence directory | `reports` |

Base URLs may contain path prefixes but not credentials, query strings, fragments, malformed ports, or unsupported schemes.

## Pytest-native capability selection

`src/pytest_capabilities.py` adds one repeatable `--capability NAME` option without replacing pytest discovery, node IDs, fixture resolution, markers, reports, or plugin behavior.

The executable capability surface includes:

- parameter matrices with stable IDs and `pytest.approx`;
- exception and warning contracts through `pytest.raises` and `pytest.warns`;
- built-in fixtures including `tmp_path`, `monkeypatch`, `capsys`, and `caplog`;
- `pytest-mock` spies that preserve real behavior while asserting calls;
- `pytest-asyncio` native async execution;
- named capability marks for targeted troubleshooting.

Capability selection is an operator convenience, not a coverage definition. Required CI still runs the complete intended gates. Unknown capability names fail closed rather than producing an all-skipped false-green run.

## Selenium browser policy

`src/browser.py` owns driver construction, `conftest.py` owns fixture scope and teardown, and `src/pages/` owns feature interactions.

- Selenium Manager may resolve compatible local drivers; driver binaries are not committed.
- Chrome and Firefox are explicit compatibility dimensions.
- Implicit waits remain disabled.
- Page objects use meaningful `WebDriverWait` conditions.
- Each browser test receives a fresh session.
- Teardown always quits the driver.
- Screenshots are failure-only.
- Generic diagnostics exclude cookies, browser storage, request bodies, page source, and credential-bearing URLs.

Fixed sleeps are not readiness models. Synchronize to an observable condition such as visibility, clickability, path transition, or application state.

## Deterministic fixture and transport policy

`mock/server.py` owns `/posts`, `/posts/<id>`, `/health`, `/ui`, and `/ui/details`. Required API, OpenAPI contract, browser, and script-health performance gates therefore exercise real repository-local behavior without depending on public DNS, third-party uptime, rate limits, or content drift.

The local fixture proves listener ownership rather than treating an open port as sufficient readiness. The child process publishes its own PID/host/port token only after binding successfully, and the parent verifies that ownership during the bounded startup window.

`src/http_client.py` centralizes:

- persistent connection pooling;
- separate connect and read budgets;
- bounded retries for explicitly safe/idempotent methods;
- transient-status retry policy;
- `X-Test-Run-Id` correlation;
- deterministic session close semantics.

Assertions remain in tests. Blind retries around mutating requests are deliberately excluded.

`contract/openapi.yaml` is executable: the fast contract suite validates both the OpenAPI document and repository-owned provider responses against its committed response schema. Structural compatibility remains separate from semantic API assertions.

## Persistence policy

SQLAlchemy tests use deterministic SQLite state while retaining explicit engine/session ownership. The lifecycle rule is independent of the database technology: the scope that creates a resource closes it.

Replacing SQLite with PostgreSQL, MySQL, or SQL Server should preserve explicit transaction ownership, data creation, cleanup, isolation, and the distinction between repository semantics and provider-specific infrastructure integration.

## Performance execution policy

`performance/locustfile.py` defaults to loopback. An external workload requires both `PERF_ALLOW_EXTERNAL=true` and an exact hostname in `PERF_ALLOWED_HOSTS`; changing `--host` alone is insufficient authorization.

The extended workflow runs only a bounded single-user loopback smoke to prove workload health. Capacity, saturation, scalability, and service-level conclusions require an explicitly designed experiment against an approved environment with stated workload shape, duration, concurrency, thresholds, and environment assumptions.

## CI and evidence

The CI surfaces intentionally separate failure domains:

- `ci.yml` — source quality, xdist ownership contracts, supported-runtime fast suites, executable OpenAPI contracts, validated JUnit/coverage evidence, and deterministic Chrome coverage on the primary runtime.
- `extended.yml` — Chrome/Firefox compatibility plus a bounded loopback Locust script-health smoke with retained metrics.
- `security.yml` — supply-chain policy, CodeQL Python SAST, independent Trivy filesystem/dependency/configuration/secret scanning, and pull-request Dependency Review when GitHub Dependency graph is available.
- `docs.yml` — local-link, badge, Mermaid, governance, and documentation-contract validation without coupling success to external-site uptime.

When GitHub Dependency graph is unavailable, the pull-request security workflow records that limitation and the independent Trivy job remains the repository-wide fallback gate. Trivy is not presented as equivalent to change-aware Dependency Review.

`src/run_manifest.py` gives run-level evidence one writer under xdist: workers emit pytest events and the controller serializes the shared manifest. Browser evidence uses the same run identity.

## Confidence boundaries

A green signal is evidence about a defined risk boundary, not a universal claim about system quality.

| Signal | Confidence gained | Deliberate limit |
| --- | --- | --- |
| Unit/framework contracts | Pure policy, lifecycle, selection, and failure semantics behave deterministically | Does not prove HTTP, database-engine, or browser integration |
| API + OpenAPI contract | Repository-owned provider behavior satisfies HTTP semantics and the committed structural schema | Does not prove every business invariant or external-provider behavior |
| SQLite persistence | Repository/session ownership, transaction behavior, and deterministic data semantics are executable | Does not prove production database topology, locking, replication, or migration behavior |
| Selenium browser gates | Covered user flows behave in the explicitly qualified browser engines against the controlled fixture | Does not imply universal browser, device, assistive-technology, or deployed-environment coverage |
| Locust loopback smoke | Workload code starts, targets the authorized fixture, emits metrics, and respects execution policy | It is not a capacity, saturation, scalability, or service-level result |
| Authorized ZAP checks | The configured active-scan surface is executable against the controlled target | It is not equivalent to a penetration test or proof of vulnerability absence |
| CodeQL / Trivy / Dependency Review | Independent scanners evaluate their governed code, dependency, configuration, secret, and change-diff scopes | Scanner success is bounded by rule coverage, vulnerability data, repository visibility, and inspected evidence |

Confidence is compositional: choose the lowest-cost boundary that can conclusively prove the requirement, then add broader integration only when the requirement depends on broader semantics.

## Dependency maintenance

Dependabot is configured for **pip** and **GitHub Actions**. `requirements.txt` declares bounded direct compatibility, while `requirements-lock/<matching-runtime>.txt` represents generated per-interpreter resolution artifacts. Each lock pins the complete resolved graph and package hashes; production CI installs with `pip --require-hashes` and verifies the installed graph with `pip check`.

Maintenance policy:

- version updates run weekly on Monday at 09:00 America/New_York;
- scheduled pip version updates are limited to direct dependencies declared by the project;
- resolver-owned transitive packages move when compatible direct dependency resolution requires them rather than being upgraded independently;
- routine direct minor/patch updates are grouped to reduce review noise;
- major upgrades remain isolated so compatibility changes stay attributable;
- GitHub Actions are maintained as their own dependency surface;
- dependency changes require intentional lock regeneration for every supported Python minor, manifest-provenance validation, strict-hash installation, and installed-graph consistency checks;
- automated dependency PRs still require CI, security, docs, release-note, resolved-graph, and behavioral-impact review.

The compatibility manifest and generated locks have different jobs: `requirements.txt` expresses allowed direct ranges; committed locks make CI resolution reproducible. Dependabot complements rather than replaces CodeQL, Dependency Review, and Trivy.

## Failure triage

| Signal | First interpretation |
| --- | --- |
| Capability selection/discovery | Marker/selector contract; confirm the intended slice before debugging test logic |
| Configuration contract | Invalid framework/runtime input |
| Hash-locked install | Dependency graph drift, missing artifact hash, or wrong interpreter lock |
| Local fixture startup | Repository-owned service lifecycle or listener ownership |
| HTTP transport | Connectivity, timeout, or retry policy |
| API assertion/schema | Protocol, semantic, or contract behavior |
| Persistence | Repository, transaction, or lifecycle semantics |
| Driver creation | Browser/runtime infrastructure |
| Explicit-wait timeout | Expected observable browser state absent |
| Browser-only failure | UI behavior or compatibility |
| Retry-only pass | Reliability/flakiness signal |
| Security/docs | Independent repository-governance failure |
| External-target-only failure | Environment/integration first |

## Explicit anti-patterns

- required CI against public demo sites or APIs;
- replacing pytest collection/reporting with a custom framework merely to group tests;
- browser setup for behavior that can be conclusively proven below the UI;
- fixed sleeps or mixed implicit/explicit waits;
- blanket retries, especially around mutations;
- shared mutable test state or multi-writer evidence files;
- credentials, cookies, storage, page source, or arbitrary payloads in generic diagnostics;
- reports that swallow the original process exit code;
- abstractions that merely rename native pytest, Selenium, or requests APIs.

## Related design documentation

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — dependency direction, ownership boundaries, parallelism, evidence, and extension rules.
- [`TEST_STRATEGY.md`](TEST_STRATEGY.md) — layer selection, browser coverage, reliability, security, performance, and CI gating.
- [`../contract/openapi.yaml`](../contract/openapi.yaml) — version-controlled executable API contract.

The framework should evolve by making test intent clearer, dependencies more explicit, failures more attributable, and retained evidence safer. New abstraction is justified only when it enforces a durable engineering policy or removes a demonstrated source of ambiguity.
