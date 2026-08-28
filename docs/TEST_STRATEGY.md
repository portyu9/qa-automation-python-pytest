# Test strategy

## Purpose

The suite is organized to answer failures at the lowest-cost layer capable of proving the behavior. A browser test is not inherently stronger than an API or unit test; it is appropriate only when the browser boundary is part of the behavior under test.

## Layer model

| Layer | Primary question | Dependency model | Default cadence |
| --- | --- | --- | --- |
| Unit | Does one function/object preserve its local contract? | In-process | Every change |
| Framework contract | Do configuration, diagnostics, lifecycle, and helpers preserve framework invariants? | In-process / deterministic local | Every change |
| API | Does HTTP behavior satisfy semantic expectations? | Local mock where possible | Every change |
| Contract | Does the API shape match versioned expectations? | Version-controlled schema/OpenAPI | Every change |
| Database | Do repository and persistence semantics hold? | In-memory SQLite | Every change |
| Browser | Does a critical user-visible path work in a real browser? | Chromium CI gate | Pull request / release |
| Security | Do explicit security assertions hold against a controlled target? | Authorized target | Scheduled / release |
| Performance | Are agreed budgets preserved under controlled load? | Authorized environment | Controlled run |

## Pull-request gate

The CI graph deliberately separates failure classes.

### Quality job

The quality job proves:

- Ruff correctness/style policy;
- source/test compilation;
- framework tests under a real two-worker pytest-xdist run;
- controller-owned run-manifest serialization with no leftover temporary artifact.

The xdist contract is important because unit-testing the manifest serializer alone cannot prove multi-process ownership.

### Functional matrix

Python 3.11, 3.12, and 3.13 run the fast layers with JUnit and coverage. Browser, performance, and security directories are excluded so a runtime/version regression can be distinguished from external browser or controlled-environment failures.

### Browser job

Chromium is installed explicitly and browser tests run in their own job. This isolates browser installation/runtime failures from the language matrix and preserves browser-specific evidence.

## Test selection rules

Add a test at the lowest layer that can observe the required behavior:

- parsing, validation, redaction, retry configuration → unit/framework contract;
- request/response semantics → API;
- storage/query semantics → database;
- cross-service shape compatibility → contract;
- rendering, focus, browser navigation, or user interaction → browser.

Do not duplicate large input matrices in the browser if a lower layer can prove them deterministically.

## Reliability policy

A test is reliable when failure means the asserted contract changed or its explicit dependency failed—not when the machine happened to be slow.

Required practices:

- bounded waits tied to observable state;
- no fixed sleeps for readiness;
- unique mutable test data;
- deterministic local dependencies for fast layers;
- explicit cleanup ownership;
- no blanket assertion retries;
- no hidden dependence on execution order.

Transport retries are infrastructure policy and are limited to safe/idempotent operations. pytest reruns, when used for diagnosis, do not convert a flaky test into a healthy one.

## Configuration-negative testing

Framework configuration is tested as a contract, including invalid booleans, unsupported browsers, non-positive budgets, malformed URLs, invalid ports, URL credentials, and query/fragment-bearing base URLs.

The desired failure point is configuration load—before a browser, socket, process, or external request is created.

## Diagnostic evidence

Use evidence in this order:

1. pytest assertion/exception and node ID;
2. JUnit for structured CI status;
3. `run-manifest.json` for run correlation, final phase/outcome, worker attribution, and aggregate status;
4. coverage for untested code-path context;
5. browser screenshot/trace or other high-volume evidence only when the browser boundary is involved.

Structured diagnostic URLs contain only origin/path. Credentials, query data, and fragments are removed before persistence.

## Failure classification

| Failure class | First action |
| --- | --- |
| Configuration | Correct the invalid runtime input; do not rerun |
| Quality/static | Fix the reported source issue |
| Framework contract | Treat as infrastructure regression |
| Local dependency readiness | Inspect process lifecycle/port ownership |
| API assertion | Compare semantic contract and response |
| External timeout | Classify dependency/transport before changing assertions |
| Browser | Inspect trace/screenshot and correlated run metadata |
| Flake/retry-only pass | Open a reliability investigation rather than accepting the rerun |

## Parallelism strategy

Fast tests should be parallel-safe by default. Data, files, ports, and mutable resources require clear ownership. Run-level artifacts must have one writer; worker-specific artifacts require worker/run namespacing.

Tests that cannot safely execute concurrently should be isolated with an explicit serial marker and a documented state constraint. Global serial execution is a last resort.

## Security and performance boundaries

Security and performance checks are not made safe by labeling them as tests. They require explicit target authorization and environment ownership. Keep destructive or high-load behavior outside the ordinary pull-request path.

Test evidence may contain application-visible synthetic data. Do not use production credentials or sensitive user data merely because artifact retention is bounded.

## Exit criteria

A change is eligible to merge when:

- quality and framework-contract checks pass;
- all supported Python fast-layer matrix entries pass;
- the Chromium browser gate passes when browser tests are in scope;
- no failing command is suppressed;
- artifacts required for failure attribution are generated successfully;
- any changed framework policy is reflected in tests and documentation.
