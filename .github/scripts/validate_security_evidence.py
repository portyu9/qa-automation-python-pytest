"""Validate Trivy evidence against every committed Python hash-lock."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK_DIR = ROOT / "requirements-lock"
DIRECT_REQUIREMENTS = ROOT / "requirements.txt"
PYTHON_MINORS = ("3.11", "3.12", "3.13", "3.14")
EXPECTED_TRIVY_VERSION = "0.74.0"
MIN_PACKAGES_PER_LOCK = 40
_NAME = re.compile(r"[-_.]+")
_PIN = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?==([^\s\\;]+)")
_DIRECT = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?")


def fail(message: str) -> None:
    raise SystemExit(f"Trivy evidence invalid: {message}")


def normalize_name(value: str) -> str:
    return _NAME.sub("-", value).lower()


def require_json(path: Path) -> dict[str, object]:
    if not path.is_file() or path.stat().st_size == 0:
        fail(f"missing or empty report: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"report is not valid JSON: {error}")
    if not isinstance(payload, dict):
        fail("report root must be an object")
    return payload


def parse_lock(path: Path) -> dict[str, str]:
    pins: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        match = _PIN.match(raw.strip())
        if match:
            pins[normalize_name(match.group(1))] = match.group(2)
    if len(pins) < MIN_PACKAGES_PER_LOCK:
        fail(f"{path.relative_to(ROOT)} contains only {len(pins)} exact package pins")
    return pins


def direct_names() -> set[str]:
    names: set[str] = set()
    for raw in DIRECT_REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = _DIRECT.match(line)
        if not match:
            fail(f"cannot parse direct requirement: {line}")
        names.add(normalize_name(match.group(1)))
    if not names:
        fail("no direct requirements were parsed")
    return names


def result_packages(result: dict[str, object]) -> dict[str, str]:
    packages = result.get("Packages")
    if not isinstance(packages, list):
        return {}
    parsed: dict[str, str] = {}
    for package in packages:
        if not isinstance(package, dict):
            continue
        name = str(package.get("Name") or "").strip()
        version = str(package.get("Version") or "").strip()
        if name and version:
            parsed[normalize_name(name)] = version
    return parsed


def matching_result(results: list[dict[str, object]], minor: str) -> dict[str, object]:
    suffix = f"python-{minor}/requirements.txt"
    matches = [
        result
        for result in results
        if str(result.get("Target") or "").replace("\\", "/").endswith(suffix)
        and str(result.get("Type") or "").lower() in {"pip", "python-pkg", "requirements"}
    ]
    if not matches:
        # Trivy currently labels pip requirements as `pip`, but keep the target
        # attribution authoritative if its language-package type naming evolves.
        matches = [
            result
            for result in results
            if str(result.get("Target") or "").replace("\\", "/").endswith(suffix)
            and result_packages(result)
        ]
    if len(matches) != 1:
        fail(f"expected exactly one attributed Trivy result for Python {minor}, found {len(matches)}")
    return matches[0]


def validate(report_path: Path) -> None:
    payload = require_json(report_path)
    if payload.get("SchemaVersion") != 2:
        fail(f"SchemaVersion must be 2, got {payload.get('SchemaVersion')!r}")
    trivy = payload.get("Trivy")
    if not isinstance(trivy, dict) or trivy.get("Version") != EXPECTED_TRIVY_VERSION:
        fail(f"Trivy version must be {EXPECTED_TRIVY_VERSION}")
    raw_results = payload.get("Results")
    if not isinstance(raw_results, list):
        fail("Results must be an array")
    results = [item for item in raw_results if isinstance(item, dict)]

    gated = []
    for result in results:
        vulnerabilities = result.get("Vulnerabilities")
        if not isinstance(vulnerabilities, list):
            continue
        for item in vulnerabilities:
            if not isinstance(item, dict):
                continue
            if str(item.get("Severity") or "").upper() in {"HIGH", "CRITICAL"}:
                gated.append(item)
    if gated:
        fail(f"report contains {len(gated)} HIGH/CRITICAL vulnerability finding(s)")

    direct = direct_names()
    evidence: list[str] = []
    for minor in PYTHON_MINORS:
        source = parse_lock(LOCK_DIR / f"python-{minor}.txt")
        missing_direct = sorted(direct - source.keys())
        if missing_direct:
            fail(f"Python {minor} lock lacks direct requirements: {', '.join(missing_direct)}")

        result = matching_result(results, minor)
        packages = result_packages(result)
        if len(packages) < MIN_PACKAGES_PER_LOCK:
            fail(f"Python {minor} Trivy inventory has only {len(packages)} packages")

        mismatches = [
            f"{name}:lock={source[name]} trivy={packages.get(name)!r}"
            for name in sorted(direct)
            if packages.get(name) != source[name]
        ]
        if mismatches:
            fail(f"Python {minor} direct-package attribution mismatch: {'; '.join(mismatches)}")

        evidence.append(f"py{minor}={len(packages)}")

    print(
        "validated Trivy dependency evidence: "
        + ", ".join(evidence)
        + f", directPackages={len(direct)}, highCritical=0, scanner={EXPECTED_TRIVY_VERSION}"
    )


def main() -> int:
    if len(sys.argv) != 2:
        fail("usage: validate_security_evidence.py <trivy.json>")
    validate(Path(sys.argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
