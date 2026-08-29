## Change summary

Describe the problem or failure mode and the behavior this change establishes.

## Validation boundary

Identify the primary boundary affected (framework/unit, component, API/transport, contract, browser, persistence, security, performance, documentation, or CI).

## Verification

- [ ] Repository fast/quality gate passes.
- [ ] Tests directly affected by the change pass.
- [ ] Relevant extended/browser/container/performance gate passes when applicable.
- [ ] Documentation contract passes when README/governance content changed.
- [ ] Dependency changes preserve reproducible install/lock metadata and exercised affected behavior.

## Framework integrity

- [ ] Default CI remains deterministic and does not depend on an uncontrolled public service.
- [ ] No unconditional sleeps, order-dependent tests, or unexplained retry increases were introduced.
- [ ] No coverage, lint, warning, assertion, security, timeout, or quality threshold was weakened only to make CI pass.
- [ ] Failure evidence is bounded and does not expose credentials, auth values, cookies, storage/session contents, private keys, or unsanitized environment data.
- [ ] The change stays within this repository's declared tool ownership; any cross-tool integration answers a distinct documented and executed boundary.
- [ ] README, architecture, test strategy, environment examples, and CI configuration remain consistent with the implementation.

## Risk / compatibility notes

Call out runtime, browser, dependency, environment, data, or backward-compatibility considerations. Write `None` when there are no material considerations.
