# Python / pytest Quality Engineering Framework

[![CI](https://github.com/portyu9/qa-automation-python-pytest/actions/workflows/ci.yml/badge.svg)](https://github.com/portyu9/qa-automation-python-pytest/actions/workflows/ci.yml)
[![Extended](https://github.com/portyu9/qa-automation-python-pytest/actions/workflows/extended.yml/badge.svg)](https://github.com/portyu9/qa-automation-python-pytest/actions/workflows/extended.yml)
[![Security](https://github.com/portyu9/qa-automation-python-pytest/actions/workflows/security.yml/badge.svg)](https://github.com/portyu9/qa-automation-python-pytest/actions/workflows/security.yml)
[![Docs](https://github.com/portyu9/qa-automation-python-pytest/actions/workflows/docs.yml/badge.svg)](https://github.com/portyu9/qa-automation-python-pytest/actions/workflows/docs.yml)

[![Python](https://img.shields.io/badge/Python-runtime-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![pytest](https://img.shields.io/badge/pytest-orchestration-0A9EDC?logo=pytest&logoColor=white)](https://pytest.org/)
[![Selenium](https://img.shields.io/badge/Selenium-browser-43B02A?logo=selenium&logoColor=white)](https://www.selenium.dev/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-persistence-D71F00?logo=sqlalchemy&logoColor=white)](https://www.sqlalchemy.org/)
[![Locust](https://img.shields.io/badge/Locust-performance-00A398?logo=locust&logoColor=white)](https://locust.io/)
[![OWASP ZAP](https://img.shields.io/badge/OWASP%20ZAP-DAST-00549E?logo=zap&logoColor=white)](https://www.zaproxy.org/)
[![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-CI-2088FF?logo=githubactions&logoColor=white)](https://github.com/features/actions)
[![Trivy](https://img.shields.io/badge/Trivy-security-1904DA?logo=trivy&logoColor=white)](https://trivy.dev/)
[![License](https://img.shields.io/badge/License-MIT-2EA44F?logo=opensourceinitiative&logoColor=white)](LICENSE)
[![Security Policy](https://img.shields.io/badge/Security-Policy-24292F?logo=github&logoColor=white)](.github/SECURITY.md)

A layered Python quality-engineering framework for deterministic **unit, API, contract, persistence, browser, security, and performance** verification. `pytest` remains the orchestration surface; reusable framework code exists only where a durable policy needs one owner.

> [!IMPORTANT]
> The governing principle is **failure attribution before test volume**: a failed run should identify the first broken boundary without forcing the reader to reverse-engineer the framework.

**Start here:** [capabilities](#capabilities) · [architecture](#architecture) · [quick start](#quick-start) · [repository map](#repository-map) · [documentation](#documentation)

## Capabilities

| Validation plane | Purpose | Primary evidence |
| --- | --- | --- |
| Fast CI | Unit, API, OpenAPI contract, persistence, framework invariants | JUnit, coverage XML, run manifest |
| Native pytest | Parametrization, fixtures, marks, warnings/exceptions, mocking, asyncio, focused selection | Native node IDs and pytest reports |
| Browser | Critical Chrome behavior with Chrome/Firefox compatibility in extended CI | Per-browser JUnit and bounded diagnostics |
| Security | Supply-chain policy, SAST, dependency/configuration/secret risk, optional controlled DAST | CodeQL, Trivy, Dependency Review, ZAP evidence |
| Performance | Workload-policy verification and explicit latency/throughput experiments | Locust metrics |
| Documentation | README, workflow, Mermaid, link, and governance consistency | Documentation contract status |

## Architecture

```mermaid
flowchart TD
    CHANGE[Repository change] --> PYTEST[pytest orchestration]
    PYTEST --> FAST[Unit · API · Contract · Persistence]
    PYTEST --> UI[Selenium browser]
    PYTEST --> EVIDENCE[Run manifest + test evidence]

    FAST --> FIXTURE[Repository-local fixture]
    FAST --> POLICY[Config · HTTP · DB policy]
    UI --> BROWSER[WebDriver + page objects]
    UI --> FIXTURE

    CHANGE --> EXT[Extended compatibility + Locust smoke]
    CHANGE --> SEC[Security controls]
    CHANGE --> DOCS[Documentation contract]

    EVIDENCE --> CI[CI gates]
    EXT --> CI
    SEC --> CI
    DOCS --> CI
    CI --> RESULT[Qualified repository change]

    classDef entry fill:#DDF4FF,stroke:#0969DA,color:#24292F,stroke-width:1.5px;
    classDef test fill:#FFF8C5,stroke:#9A6700,color:#24292F,stroke-width:1.5px;
    classDef policy fill:#FBEFFF,stroke:#8250DF,color:#24292F,stroke-width:1.5px;
    classDef evidence fill:#DAFBE1,stroke:#1A7F37,color:#24292F,stroke-width:1.5px;
    classDef gate fill:#FFEBE9,stroke:#CF222E,color:#24292F,stroke-width:1.5px;

    class CHANGE,PYTEST entry;
    class FAST,UI,FIXTURE,BROWSER test;
    class POLICY policy;
    class EVIDENCE,RESULT evidence;
    class EXT,SEC,DOCS,CI gate;
    linkStyle default stroke:#57606A,stroke-width:1.4px;
```

Tests own **intent**, fixtures own **lifecycle**, framework modules own **cross-cutting policy**, and native tools retain their failure semantics. See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for dependency direction, lifecycle ownership, parallelism, and evidence boundaries.

## Quick start

Choose the interpreter-specific lock matching the active supported Python runtime:

```bash
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install --require-hashes -r requirements-lock/<matching-runtime>.txt
pytest --ignore=tests/e2e --ignore=tests/performance --ignore=tests/security
```

Run browser compatibility explicitly:

```bash
TEST_BROWSER=chrome pytest tests/e2e
TEST_BROWSER=firefox pytest tests/e2e
```

Run a focused native pytest capability without changing normal collection semantics:

```bash
pytest tests/framework/test_pytest_capabilities.py --capability=fixtures
```

For the complete command reference, runtime variables, dependency workflow, performance authorization, and failure triage, see [`docs/OPERATIONS.md`](docs/OPERATIONS.md).

## Repository map

```text
.
├── .github/
├── contract/
├── docs/
├── mock/
├── performance/
├── requirements-lock/
├── src/
└── tests/
```

## Engineering contracts

- **Deterministic targets:** committed framework-health gates use repository-local services rather than public demo dependencies.
- **Lowest conclusive layer:** prove requirements at unit/API/contract/persistence level before paying browser cost.
- **Native pytest semantics:** discovery, node IDs, fixtures, markers, reports, warnings, and plugin behavior remain visible.
- **Explicit lifecycle ownership:** the scope that creates a driver, engine, session, process, or evidence file owns deterministic cleanup.
- **Bounded retries and waits:** retry only known transient safe operations; synchronize browsers to observable state rather than fixed sleeps.
- **Privacy-aware evidence:** generic diagnostics are failure-oriented and exclude credential-bearing or unnecessary application data.
- **Authoritative exits:** reporting and artifact collection never convert a native test/tool failure into success.

## Quality gates

| Gate | Responsibility |
| --- | --- |
| [`ci.yml`](.github/workflows/ci.yml) | Supported-runtime fast suites, executable OpenAPI contracts, source quality, evidence validation, Chrome smoke |
| [`extended.yml`](.github/workflows/extended.yml) | Chrome/Firefox compatibility and bounded loopback Locust script-health smoke |
| [`security.yml`](.github/workflows/security.yml) | Supply-chain policy, CodeQL, Trivy, and Dependency Review when available |
| [`docs.yml`](.github/workflows/docs.yml) | README/local-link/badge/Mermaid/governance consistency |

A green gate is evidence about its defined risk boundary, not a universal claim of system quality. The detailed confidence limits are documented in [`docs/OPERATIONS.md`](docs/OPERATIONS.md#confidence-boundaries).

## Documentation

| Guide | Use it for |
| --- | --- |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | Dependency direction, configuration/HTTP/DB/browser boundaries, fixture ownership, parallelism, evidence, extension rules |
| [`docs/TEST_STRATEGY.md`](docs/TEST_STRATEGY.md) | Layer selection, browser strategy, selectors, retries, test data, security, performance, CI gating |
| [`docs/OPERATIONS.md`](docs/OPERATIONS.md) | Commands, runtime configuration, deterministic fixture/transport policy, CI evidence, dependency maintenance, triage |
| [`contract/openapi.yaml`](contract/openapi.yaml) | Version-controlled executable API contract |

The deeper flow and CI diagrams live in `/docs`; the main README intentionally retains only the architecture overview above.

## Design principle

The framework should evolve by making **test intent clearer, dependencies more explicit, failures more attributable, and retained evidence safer**. Add abstraction only when it enforces a durable engineering policy or removes a demonstrated source of ambiguity.
