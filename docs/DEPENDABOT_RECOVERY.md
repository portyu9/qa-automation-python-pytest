# Dependabot recovery

Dependency recovery is a bounded qualification aid. It is not a merge authority and it does not replace the trusted Python lock publisher.

Two recovery provenance states are accepted. Ordinary Dependabot PRs must retain the existing one-commit GitHub-signed bot provenance directly on current `main`. Pip PRs may also be recovered after lock publication only when the history is exactly the canonical signed Dependabot source commit followed by one verified `github-actions[bot]` commit produced by the trusted default-branch lock publisher. That generated commit must be parented directly on the source commit, bind the exact source SHA in the canonical publisher message, and change exactly the four interpreter locks plus `requirements-lock/manifest.json`. The resulting PR file set must be exactly `requirements.txt` plus those five derived files.

The second state is **recovery-only**. Pip remains `mode: manual`; accepting the publisher chain for transient reruns does not make it eligible for autonomous merge. GitHub Actions updates continue to use the existing single-commit autonomous governance proof.

A required qualification workflow may receive one failed-job rerun only when its stable aggregate gate failed, every other job is terminal and unambiguous, every failed leaf has exactly one failed step, that step is explicitly allowlisted infrastructure, and its own timestamp-bounded log window contains a narrow transient network/service signature without deterministic blockers. The retry budget is `maxRunAttempts: 2`, so only the first failed attempt can be retried automatically.

The read-only `dependency-locks` workflow is treated separately as an auxiliary generation workflow because it intentionally has no aggregate merge gate. Before lock publication, a failed interpreter matrix may be rerun only when every failed job meets the same strict transient proof. Resolver conflicts, missing distributions, hash mismatches, ambiguous matrix states, tests, Selenium, Locust, security scanners, evidence validators, and all aggregate gates remain non-recoverable.

The privileged `dependency-lock-publisher` is never rerun or emulated by recovery. It remains the only component allowed to create the generated lock commit and update a `dependabot/pip/*` ref. Recovery contains no Git tree/commit/ref mutation and no merge transport. A stale ordinary Dependabot PR waits for native `rebase-strategy: auto`; a stale already-published pip chain is escalated rather than rewritten.

The Dependabot configuration, recovery configuration and implementation/tests, governance implementation/tests/workflow, lock generator/publisher workflows, and publisher implementation/tests are manual-review control plane.
