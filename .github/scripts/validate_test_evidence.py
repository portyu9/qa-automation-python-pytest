"""Validate retained pytest, coverage, manifest, browser, and Locust evidence."""
from __future__ import annotations

import csv
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(message)


def require_file(raw: str) -> Path:
    path = Path(raw)
    if not path.is_file() or path.stat().st_size == 0:
        fail(f"missing or empty evidence file: {path}")
    return path


def junit_counts(path: Path) -> tuple[int, int, int, int]:
    root = ET.parse(path).getroot()
    cases = root.findall(".//testcase")
    tests = len(cases)
    failures = sum(1 for case in cases if case.find("failure") is not None)
    errors = sum(1 for case in cases if case.find("error") is not None)
    skipped = sum(1 for case in cases if case.find("skipped") is not None)
    return tests, failures, errors, skipped


def manifest_summary(path: Path) -> dict[str, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        fail(f"run manifest lacks summary object: {path}")
    required = {"total", "passed", "failed", "skipped"}
    if not required.issubset(summary):
        fail(f"run manifest summary lacks required counters: {path}")
    if any(not isinstance(summary[key], int) or summary[key] < 0 for key in required):
        fail(f"run manifest summary has invalid counters: {path}")
    if summary["total"] != summary["passed"] + summary["failed"] + summary["skipped"]:
        fail(f"run manifest counters do not reconcile: {path}")
    return summary


def validate_functional(junit_raw: str, coverage_raw: str, manifest_raw: str, minimum_raw: str) -> None:
    junit = require_file(junit_raw)
    coverage = require_file(coverage_raw)
    manifest = require_file(manifest_raw)
    minimum = int(minimum_raw)
    if minimum < 1:
        fail("functional minimum must be positive")

    tests, failures, errors, skipped = junit_counts(junit)
    executed = tests - skipped
    if executed < minimum:
        fail(f"functional JUnit has {executed} executed tests; minimum is {minimum}")
    if failures or errors:
        fail(f"functional JUnit contains failures={failures}, errors={errors}")

    summary = manifest_summary(manifest)
    if summary["total"] != tests:
        fail(f"manifest/JUnit totals differ: manifest={summary['total']} junit={tests}")
    if summary["failed"] != failures:
        fail(f"manifest/JUnit failure totals differ: manifest={summary['failed']} junit={failures}")
    if summary["skipped"] != skipped:
        fail(f"manifest/JUnit skipped totals differ: manifest={summary['skipped']} junit={skipped}")

    coverage_root = ET.parse(coverage).getroot()
    lines_valid = int(coverage_root.attrib.get("lines-valid", "0"))
    lines_covered = int(coverage_root.attrib.get("lines-covered", "0"))
    branches_valid = int(coverage_root.attrib.get("branches-valid", "0"))
    branches_covered = int(coverage_root.attrib.get("branches-covered", "0"))
    line_rate = float(coverage_root.attrib.get("line-rate", "0"))
    branch_rate = float(coverage_root.attrib.get("branch-rate", "0"))
    if lines_valid <= 0 or not 0 <= lines_covered <= lines_valid:
        fail("coverage evidence contains invalid line counters")
    if branches_valid <= 0 or not 0 <= branches_covered <= branches_valid:
        fail("coverage evidence contains invalid branch counters")
    if line_rate < 0.70:
        fail(f"coverage line rate {line_rate:.4f} is below repository floor 0.70")
    if not 0 <= branch_rate <= 1:
        fail(f"coverage branch rate is invalid: {branch_rate}")

    print(
        "validated functional evidence: "
        f"executed={executed}, skipped={skipped}, "
        f"lines={lines_covered}/{lines_valid} ({line_rate:.2%}), "
        f"branches={branches_covered}/{branches_valid} ({branch_rate:.2%})"
    )


def validate_browser(junit_raw: str, manifest_raw: str, minimum_raw: str) -> None:
    junit = require_file(junit_raw)
    manifest = require_file(manifest_raw)
    minimum = int(minimum_raw)
    if minimum < 1:
        fail("browser minimum must be positive")

    tests, failures, errors, skipped = junit_counts(junit)
    executed = tests - skipped
    if executed < minimum:
        fail(f"browser JUnit has {executed} executed tests; minimum is {minimum}")
    if failures or errors:
        fail(f"browser JUnit contains failures={failures}, errors={errors}")

    summary = manifest_summary(manifest)
    if summary["total"] != tests:
        fail(f"browser manifest/JUnit totals differ: manifest={summary['total']} junit={tests}")
    if summary["failed"] != failures or summary["skipped"] != skipped:
        fail("browser manifest/JUnit outcome counters do not reconcile")

    print(f"validated browser evidence: executed={executed}, skipped={skipped}, failures=0")


def validate_locust(stats_raw: str, failures_raw: str, exceptions_raw: str, minimum_raw: str) -> None:
    stats = require_file(stats_raw)
    failures = require_file(failures_raw)
    exceptions = require_file(exceptions_raw)
    minimum = int(minimum_raw)
    if minimum < 1:
        fail("Locust request minimum must be positive")

    with stats.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    aggregate = next((row for row in rows if row.get("Name") == "Aggregated"), None)
    if aggregate is None:
        fail("Locust stats lack Aggregated row")
    requests = int(aggregate.get("Request Count", "0"))
    failures_count = int(aggregate.get("Failure Count", "0"))
    if requests < minimum:
        fail(f"Locust evidence contains {requests} requests; minimum is {minimum}")
    if failures_count != 0:
        fail(f"Locust aggregate contains {failures_count} failures")

    for path, label in ((failures, "failures"), (exceptions, "exceptions")):
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        if rows:
            fail(f"Locust {label} evidence is non-empty: {len(rows)} row(s)")

    print(f"validated Locust evidence: requests={requests}, failures=0, exceptions=0")


def main() -> int:
    if len(sys.argv) < 2:
        fail("usage: validate_test_evidence.py <functional|browser|locust> ...")
    mode = sys.argv[1]
    args = sys.argv[2:]
    if mode == "functional" and len(args) == 4:
        validate_functional(*args)
    elif mode == "browser" and len(args) == 3:
        validate_browser(*args)
    elif mode == "locust" and len(args) == 4:
        validate_locust(*args)
    else:
        fail(f"invalid evidence validator invocation for mode {mode!r}: {args!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
