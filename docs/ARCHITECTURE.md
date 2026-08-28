# Framework architecture

## Boundaries

The framework separates *test intent* from *integration mechanics*.

- **Tests** describe behavior and assertions. They should not own URL construction, retry loops, SQL connection lifecycle, or browser locator plumbing.
- **Domain clients** expose operations meaningful to the system under test and translate transport responses into test-facing data.
- **Transport** (`HttpClient`) owns connection pooling, timeouts, correlation metadata, and narrowly scoped retry behavior.
- **Repositories** own persistence access and query semantics.
- **Pages/components** own browser selectors and interaction primitives.
- **Configuration** is immutable after startup and validated before side effects.
- **Fixtures/hooks** own lifecycle and composition, not business assertions.

This direction keeps dependencies pointing inward: tests depend on domain abstractions; domain abstractions depend on infrastructure; infrastructure does not import tests.

## Configuration lifecycle

`TestSettings.from_env()` is the boundary between process configuration and typed framework state. Fixtures should construct it once at session scope and pass the resulting object to clients/factories. This avoids repeated environment parsing and prevents a test from accidentally mutating global configuration.

Secrets are never represented in `.env.example`. Secret-bearing settings should be injected from a secret manager or CI secret store and must be redacted from logs.

## HTTP behavior

Retries are limited to transient errors and idempotent methods. POST/PATCH operations are not retried automatically because doing so can duplicate state. If an API supports idempotency keys, a domain client can opt into a domain-specific retry strategy explicitly.

Timeouts are mandatory. An unbounded request is a test-runner resource leak.

## Browser model

Page objects/components should expose user-meaningful operations rather than generic wrappers around every Playwright/Selenium method. Prefer semantic locators (role, label, accessible name, stable test id). Waiting belongs at the interaction boundary and must target observable conditions; fixed sleeps are prohibited except in deliberate timing/performance tests.

## Database model

Repository helpers should use parameterized queries and explicit transactions. Tests should prefer disposable data and rollback/cleanup. Shared static records create ordering and parallelism hazards.

## Contract and schema checks

Contract fixtures are version-controlled beside the tests that consume them. Schema validation supplements behavioral assertions; it does not replace them. Breaking contract changes should be visible as reviewable artifact diffs.

## Parallelism

The default assumption is parallel safety. Unique resource names should include `TEST_RUN_ID` and, where necessary, worker identity. Only tests that truly require exclusive state should carry the `serial` marker.

## Observability

A test run should be traceable across client logs and server telemetry using `X-Test-Run-Id`. Additional correlation IDs returned by the system should be captured in failure output. Diagnostic code must use an allowlist approach to logged headers/fields to avoid secret leakage.
