"""Regression tests for the repository-owned Trivy evidence validator."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory

from validate_security_evidence import (
    EXPECTED_TRIVY_VERSION,
    LOCK_DIR,
    PYTHON_MINORS,
    parse_lock,
    validate,
)


def report_fixture() -> dict[str, object]:
    results: list[dict[str, object]] = []
    for minor in PYTHON_MINORS:
        pins = parse_lock(LOCK_DIR / f"python-{minor}.txt")
        results.append(
            {
                "Target": f"reports/security/trivy-input/python-{minor}/requirements.txt",
                "Class": "lang-pkgs",
                "Type": "pip",
                "Packages": [
                    {"Name": name, "Version": version, "ID": f"{name}@{version}"}
                    for name, version in sorted(pins.items())
                ],
                "Vulnerabilities": None,
            }
        )
    return {
        "SchemaVersion": 2,
        "Trivy": {"Version": EXPECTED_TRIVY_VERSION},
        "Results": results,
    }


def assert_fails(payload: dict[str, object], expected: str) -> None:
    with TemporaryDirectory(prefix="python-trivy-policy-") as temp_dir:
        path = Path(temp_dir) / "trivy.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        try:
            validate(path)
        except SystemExit as error:
            if expected not in str(error):
                raise AssertionError(f"expected {expected!r} in {error!r}") from error
        else:
            raise AssertionError(f"expected validator failure containing {expected!r}")


def main() -> int:
    clean = report_fixture()
    with TemporaryDirectory(prefix="python-trivy-policy-") as temp_dir:
        path = Path(temp_dir) / "trivy.json"
        path.write_text(json.dumps(clean), encoding="utf-8")
        validate(path)

    missing_target = deepcopy(clean)
    missing_target["Results"] = missing_target["Results"][:-1]  # type: ignore[index]
    assert_fails(missing_target, "Python 3.14")

    wrong_version = deepcopy(clean)
    wrong_version["Trivy"]["Version"] = "0.0.0"  # type: ignore[index]
    assert_fails(wrong_version, "Trivy version")

    shallow = deepcopy(clean)
    shallow["Results"][0]["Packages"] = shallow["Results"][0]["Packages"][:10]  # type: ignore[index]
    assert_fails(shallow, "inventory has only")

    vulnerable = deepcopy(clean)
    vulnerable["Results"][0]["Vulnerabilities"] = [  # type: ignore[index]
        {"Severity": "HIGH", "VulnerabilityID": "CVE-TEST"}
    ]
    assert_fails(vulnerable, "HIGH/CRITICAL")

    mismatch = deepcopy(clean)
    mismatch["Results"][0]["Packages"][0]["Version"] = "0.0.0"  # type: ignore[index]
    assert_fails(mismatch, "direct-package attribution mismatch")

    print("Python Trivy evidence validator self-test: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
