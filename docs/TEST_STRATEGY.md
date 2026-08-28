# Test strategy

## Selection by feedback speed

The default pull-request gate should contain deterministic unit, API, contract, and lightweight integration checks. Browser, security, and performance suites have distinct cost and environment requirements and run as dedicated jobs or scheduled/release workflows.

A test belongs at the lowest layer that can detect the defect with sufficient confidence. Duplicating the same assertion at every layer increases maintenance without increasing signal.

## Flake policy

A retry is diagnostic containment, not a fix. `pytest-rerunfailures` may be used temporarily for known external instability, but every retried test should have an owner and remediation path. Framework code must not catch assertion failures and rerun arbitrary blocks.

Common flake causes to eliminate:

- fixed sleeps instead of condition-based waits;
- shared accounts/records across workers;
- non-unique generated data;
- reliance on test order;
- unbounded network calls;
- stale browser state;
- eventual-consistency assertions without bounded polling.

## Test data

Use builders/factories for data with meaningful defaults and allow each test to override only relevant fields. Prefer API/database setup over UI setup when setup behavior is not itself under test. Every stateful test should define cleanup or use ephemeral infrastructure.

## Negative testing

For each externally visible capability, cover success plus representative validation, authorization, not-found, conflict/idempotency, boundary, and malformed-input cases where applicable. Avoid combinatorial explosion by choosing equivalence partitions and risk-based boundaries.

## Contract testing

Validate both structure and critical semantics. JSON Schema/OpenAPI checks catch shape drift; behavioral assertions catch incorrect values/status transitions. Consumer-provider contract testing is appropriate where independent services deploy separately and compatibility must be proven before release.

## Security checks

Security tests are isolated from ordinary functional CI because active scanning may be destructive or slow. Targets must be explicitly authorized. Failures should include rule identifier, target endpoint, and evidence while redacting tokens and sensitive payload fields.

## Performance checks

Performance tests should define a workload model and pass/fail thresholds before execution. Separate smoke, baseline, load, stress, and soak profiles. Compare like-for-like environments and track percentiles/error rate rather than average latency alone.

## Release gates

A release gate should be based on risk and environment confidence, typically requiring:

- fast functional suite green;
- contract compatibility green;
- critical browser journeys green;
- no unresolved high-severity security regression;
- applicable performance SLO thresholds green;
- diagnostic artifacts retained for failed gates.

Quarantined tests do not count as coverage for a release criterion.
