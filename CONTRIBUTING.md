# Contributing

Changes to this framework should preserve deterministic execution, explicit tool ownership, and actionable failure evidence. A contribution is complete when the implementation, tests, documentation, and CI contract describe the same behavior.

## Design the change at the right validation boundary

Before editing code, identify the cheapest validation plane that proves the requirement: framework/unit, component, API/transport, contract, browser, persistence, security, performance, or documentation. Do not promote a deterministic lower-level assertion to a live external integration merely to make it more end-to-end.

Keep technology ownership native to this repository. Do not add a second implementation of a capability that is intentionally owned by another framework repository unless the integration answers a distinct architectural question and is executed, documented, and governed here.

Default gates must be deterministic. Public services, fixed shared environments, mutable remote data, and third-party availability belong only in explicitly opt-in integration paths with bounded timeouts and clear failure semantics.

## Test-design requirements

Tests should be independent, repeatable, and diagnostic. Prefer explicit state construction over test ordering; generate collision-safe data where state is created; clean up owned state when the boundary requires it; and isolate external dependencies behind deliberate clients, fixtures, fakes, mocks, containers, or local servers.

Use framework-native synchronization and bounded polling rather than unconditional sleeps. Retries are a resilience mechanism for understood transient infrastructure conditions, not a substitute for fixing nondeterministic assertions. A retry policy must remain visible in configuration and should not hide the first failure evidence.

Assertions should verify externally meaningful behavior and stable contracts. Avoid coupling tests to implementation details that are not part of the intended interface. Negative paths, validation failures, timeout behavior, malformed inputs, and dependency failures should be covered when they are part of the framework boundary.

## Evidence and privacy

Failure artifacts must be useful without becoming a data-exfiltration path. Keep reports bounded and prefer allowlisted metadata such as test name, run ID, browser/runtime, status, duration, sanitized URL/path, and stable error category.

Do not commit or publish credentials, authorization values, cookies, session/storage contents, private keys, raw secrets, or unsanitized environment dumps. Request/response bodies, page source, database rows, and screenshots should be retained only when the framework deliberately sanitizes them or the data is known to be non-sensitive test data.

## Local verification

Use the repository README as the executable command reference. At minimum, run the documented installation/bootstrap step, the fast quality gate, tests affected by the change, and the documentation contract when README or governance surfaces change. Run the relevant extended/browser/container/performance gate when the changed boundary is exercised there.

Do not weaken coverage thresholds, assertions, lint rules, warning policies, security severity gates, timeouts, or retry limits solely to obtain a green build. If a gate is intentionally changed, document the engineering reason and update the test strategy or architecture contract when appropriate.

## Dependency changes

Keep dependency updates isolated from unrelated behavior changes whenever practical. Preserve lockfiles or equivalent reproducibility metadata, use supported runtime/toolchain versions, review release notes for breaking behavior, and exercise the framework boundaries most exposed to the dependency.

A dependency update is not complete merely because installation succeeds; the affected behavioral and extended gates must remain green.

## Pull-request contract

A pull request should state the problem or failure mode, the validation boundary affected, the implementation approach, the verification performed, and any operational or compatibility risk. Update README, architecture, test-strategy, environment examples, and CI configuration whenever their declared contract changes.

Review should reject hidden cross-tool duplication, unbounded external dependencies in default CI, secret-bearing artifacts, broad exception suppression, unexplained retries, and tests whose success depends on execution order.
