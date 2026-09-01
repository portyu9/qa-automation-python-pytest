from pathlib import Path
import re

path = Path("README.md")
text = path.read_text(encoding="utf-8")

replacements = {
    "supported Python runtimes are exercised by CI. primary Python runtime is the primary quality/browser/performance runtime; the earlier supported minors remain explicit fast-suite compatibility lines. `requirements.txt` is the human-maintained direct compatibility input; CI installs a generated, interpreter-specific hash lock. Choose the lock matching the active Python minor version.":
    "CI qualifies every supported Python runtime. One runtime is designated the primary quality, browser, and performance line; the remaining supported runtimes are explicit fast-suite compatibility lines. `requirements.txt` is the human-maintained direct compatibility input, while CI installs a generated interpreter-specific hash lock. Choose the lock matching the active Python runtime.",
    "For minimum supported Python runtime, 3.12, or 3.13, use the corresponding file in `requirements-lock/`. Use `pip install -r requirements.txt` only when intentionally resolving dependency changes and regenerating all supported-interpreter locks; it is not the CI installation path.":
    "For any supported Python runtime, use the corresponding file in `requirements-lock/`. Use `pip install -r requirements.txt` only when intentionally resolving dependency changes and regenerating all supported-interpreter locks; it is not the CI installation path.",
}
for old, new in replacements.items():
    if old not in text:
        raise SystemExit(f"missing expected README text: {old[:90]}")
    text = text.replace(old, new)

marker = "## Dependency maintenance\n"
section = """## Confidence boundaries

A green signal is evidence about a defined risk boundary, not a universal claim about system quality.

| Signal | Confidence gained | Deliberate limit |
| --- | --- | --- |
| Unit/framework contracts | Pure policy, lifecycle, selection, and failure semantics behave deterministically | Does not prove HTTP, database-engine, or browser integration |
| API + OpenAPI contract | Repository-owned provider behavior satisfies HTTP semantics and the committed structural schema | Structural compatibility does not prove every business invariant or external-provider behavior |
| SQLite persistence | Repository/session ownership, transaction behavior, and deterministic data semantics are executable | Does not prove production database engine, topology, locking, replication, or migration behavior |
| Selenium browser gates | Covered user flows behave in the explicitly qualified browser engines against the controlled fixture | Does not imply universal browser, device, assistive-technology, or deployed-environment coverage |
| Locust loopback smoke | Workload code starts, targets the authorized fixture, emits metrics, and respects execution policy | It is not a capacity, saturation, scalability, or service-level result |
| Authorized ZAP checks | The configured active-scan surface is executable against the controlled target | It is not equivalent to a penetration test or proof of vulnerability absence |
| CodeQL / Trivy / dependency review | Independent scanners evaluate their governed code, dependency, configuration, secret, and change-diff scopes | Scanner success is bounded by rule coverage, vulnerability data, repository visibility, and the evidence actually inspected |

The framework therefore treats **confidence as compositional**: choose the lowest-cost boundary that can prove the requirement, then add broader integration only when the requirement depends on broader semantics.

"""
if "## Confidence boundaries\n" not in text:
    if marker not in text:
        raise SystemExit("Dependency maintenance marker missing")
    text = text.replace(marker, section + marker)
path.write_text(text, encoding="utf-8")

patterns = [
    re.compile(r"\bPython\s+\d"),
    re.compile(r"\bpytest\s+\d", re.I),
    re.compile(r"\bSelenium\s+\d", re.I),
    re.compile(r"\bSQLAlchemy\s+\d", re.I),
    re.compile(r"\bLocust\s+\d", re.I),
    re.compile(r"\b(?:OWASP\s+)?ZAP\s+\d", re.I),
    re.compile(r"(?<!\d)3\.1\d(?!\d)"),
]
candidates = []
for md in [Path("README.md"), *Path("docs").rglob("*.md")]:
    for number, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
        if any(pattern.search(line) for pattern in patterns):
            candidates.append(f"{md}:{number}: {line}")
if candidates:
    raise SystemExit("Residual Python/tool version candidates:\n" + "\n".join(candidates))
