"""Fail when GitHub workflow dependencies use mutable references."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
USES_RE = re.compile(
    r"^\s*(?:-\s*)?uses:\s*[\"']?([^\"'\s#]+)[\"']?\s*(?:#.*)?$",
    re.MULTILINE,
)
GITHUB_SHA_RE = re.compile(r"^[^@\s]+@[0-9a-fA-F]{40}$")
DOCKER_DIGEST_RE = re.compile(r"^docker://[^@\s]+@sha256:[0-9a-fA-F]{64}$")


def main() -> int:
    errors: list[str] = []
    workflow_files = sorted((*WORKFLOW_DIR.glob("*.yml"), *WORKFLOW_DIR.glob("*.yaml")))
    if not workflow_files:
        print("Workflow pin contract failed: no workflow files found")
        return 1

    for workflow in workflow_files:
        text = workflow.read_text(encoding="utf-8")
        for reference in USES_RE.findall(text):
            if reference.startswith("./"):
                continue
            if reference.startswith("docker://"):
                if not DOCKER_DIGEST_RE.fullmatch(reference):
                    errors.append(
                        f"{workflow.relative_to(ROOT)} uses mutable Docker action reference: {reference}"
                    )
                continue
            if not GITHUB_SHA_RE.fullmatch(reference):
                errors.append(
                    f"{workflow.relative_to(ROOT)} uses mutable GitHub action/workflow reference: {reference}"
                )

    if errors:
        print("Workflow pin contract failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Workflow pin contract: all external workflow dependencies are immutable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
