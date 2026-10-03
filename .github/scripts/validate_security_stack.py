"""Fail closed when the repository's Python/Actions scanner contract drifts."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SECURITY_WORKFLOW = ROOT / ".github" / "workflows" / "security.yml"
CODEQL_BY_SUFFIX = {".py": "python", ".pyi": "python"}
KNOWN_CODE_SUFFIXES = set(CODEQL_BY_SUFFIX) | {
    ".js", ".jsx", ".ts", ".tsx", ".go", ".sh", ".bash", ".zsh", ".ksh",
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp", ".cs", ".java",
    ".kt", ".kts", ".rb", ".rs", ".swift", ".php", ".scala", ".lua", ".ps1",
}
SHELL_SHEBANG = re.compile(r"^#!.*\b(?:ba|da|k|z)?sh\b")


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    )
    return [ROOT / item.decode("utf-8") for item in result.stdout.split(b"\x00") if item]


def main() -> int:
    errors: list[str] = []
    files = tracked_files()
    workflow_text = SECURITY_WORKFLOW.read_text(encoding="utf-8")
    discovered_codeql: set[str] = set()

    for path in files:
        suffix = path.suffix.lower()
        relative = path.relative_to(ROOT)
        if suffix in CODEQL_BY_SUFFIX:
            discovered_codeql.add(CODEQL_BY_SUFFIX[suffix])
        elif suffix in KNOWN_CODE_SUFFIXES:
            errors.append(
                f"tracked source {relative} has no scanner mapping; extend the security gate before merging"
            )

        if path.is_file():
            try:
                first_line = path.open("r", encoding="utf-8").readline().rstrip("\n")
            except UnicodeDecodeError:
                first_line = ""
            if SHELL_SHEBANG.search(first_line):
                errors.append(
                    f"tracked shell entrypoint {relative} is outside the declared Python/Actions scanner stack"
                )

    if discovered_codeql != {"python"}:
        errors.append(
            "first-party CodeQL language inventory mismatch: "
            f"found {sorted(discovered_codeql)}, expected ['python']"
        )

    workflows = sorted((ROOT / ".github" / "workflows").glob("*.y*ml"))
    if not workflows:
        errors.append("no GitHub Actions workflows found for CodeQL Actions analysis")

    required_contracts = {
        "Python and Actions analysis": "languages: python,actions",
        "security-extended queries": "queries: security-extended",
        "zero-alert enforcement": "python .github/scripts/validate_codeql_sarif.py",
        "SARIF retention": "Upload CodeQL SARIF evidence",
        "SARIF self-check": "python .github/scripts/validate_codeql_sarif_selfcheck.py",
        "stack inventory self-check": "python .github/scripts/validate_security_stack.py",
    }
    for name, needle in required_contracts.items():
        if needle not in workflow_text:
            errors.append(f"security workflow is missing {name}")

    sarif_gate = (ROOT / ".github" / "scripts" / "validate_codeql_sarif.py").read_text(
        encoding="utf-8"
    )
    if "CodeQL zero-alert gate rejected" not in sarif_gate:
        errors.append("CodeQL SARIF gate must reject every code-scanning result")

    if errors:
        print("Security stack coverage contract failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Security stack coverage contract: Python and GitHub Actions are zero-alert gated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
