#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import difflib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / ".github" / "dependency-governance.json"
PAGE_SIZE = 100
SAFE_TERMINAL_CONCLUSIONS = {"success", "neutral", "skipped"}
ACTION_LINE = re.compile(
    r"^(?P<prefix>\s*-\s+uses:\s+)(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"
    r"@(?P<ref>[0-9a-fA-F]{40})(?P<suffix>\s+#\s+v(?P<version>\d+(?:\.\d+){0,2})\s*)$"
)
POSITIVE_INT = re.compile(r"^[1-9]\d*$")


class GovernanceError(RuntimeError):
    """Operational/configuration failure: the workflow should fail."""


class PolicyBlock(RuntimeError):
    """Expected fail-closed policy decision: no merge, but not an outage."""


@dataclass(frozen=True)
class Assessment:
    pull: dict[str, Any]
    base_sha: str
    files: list[dict[str, Any]]
    ecosystem: str
    provenance: dict[str, Any]
    metadata: dict[str, Any]
    semantic: dict[str, Any]
    qualification: dict[str, Any] | None


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def parse_positive_integer(value: Any, name: str = "value") -> int:
    text = str(value if value is not None else "").strip()
    if not POSITIVE_INT.fullmatch(text):
        raise GovernanceError(f"{name} must be a positive integer")
    number = int(text)
    if number > 9_007_199_254_740_991:
        raise GovernanceError(f"{name} exceeds the safe integer range")
    return number


def load_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or Path(os.environ.get("GOVERNANCE_CONFIG", DEFAULT_CONFIG))
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernanceError(f"unable to read governance config {config_path}: {exc}") from exc
    errors = validate_config(config)
    if errors:
        raise GovernanceError("invalid dependency governance config:\n- " + "\n- ".join(errors))
    return config


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    def nonempty(value: Any) -> bool:
        return isinstance(value, str) and bool(value.strip())

    if config.get("schemaVersion") != 1:
        errors.append("schemaVersion must equal 1")
    if config.get("botLogin") != "dependabot[bot]":
        errors.append("botLogin must be dependabot[bot]")
    if not isinstance(config.get("botUserId"), int) or config["botUserId"] <= 0:
        errors.append("botUserId must be a positive integer")
    for key in (
        "botAuthorEmail",
        "trustedCommitterLogin",
        "gitCommitterName",
        "gitCommitterEmail",
        "signedOffBy",
        "baseBranch",
        "statusCommentMarker",
    ):
        if not nonempty(config.get(key)):
            errors.append(f"{key} must be non-empty")
    if config.get("mergeMethod") not in {"merge", "squash", "rebase"}:
        errors.append("mergeMethod is invalid")
    if not isinstance(config.get("automergeEnabled"), bool):
        errors.append("automergeEnabled must be boolean")

    for key, maximum in (
        ("maxChangedFiles", 100),
        ("maxPullRequestAgeDays", 90),
        ("maxPaginationPages", 20),
    ):
        value = config.get(key)
        if not isinstance(value, int) or value < 1 or value > maximum:
            errors.append(f"{key} must be an integer from 1 to {maximum}")

    labels = config.get("manualReviewLabels")
    if not isinstance(labels, list) or not labels or not all(nonempty(x) for x in labels):
        errors.append("manualReviewLabels must be a non-empty string list")

    workflows = config.get("requiredWorkflows")
    if not isinstance(workflows, list) or not workflows:
        errors.append("requiredWorkflows must be non-empty")
    else:
        names: set[str] = set()
        gates: set[str] = set()
        files: set[str] = set()
        for item in workflows:
            if not isinstance(item, dict):
                errors.append("each required workflow must be an object")
                continue
            workflow, gate, filename = item.get("workflow"), item.get("gate"), item.get("file")
            if not all(nonempty(x) for x in (workflow, gate, filename)):
                errors.append("each required workflow needs workflow, gate, and file")
                continue
            if "/" in filename or not re.fullmatch(r"[A-Za-z0-9._-]+\.ya?ml", filename):
                errors.append(f"workflow file {filename} must be a workflow basename")
            if workflow in names:
                errors.append(f"duplicate workflow {workflow}")
            if gate in gates:
                errors.append(f"duplicate gate {gate}")
            if filename in files:
                errors.append(f"duplicate workflow file {filename}")
            names.add(workflow)
            gates.add(gate)
            files.add(filename)

    allowed_updates = config.get("allowedActionUpdateTypes")
    if (
        not isinstance(allowed_updates, list)
        or not allowed_updates
        or any("major" in str(update) for update in allowed_updates)
    ):
        errors.append("allowedActionUpdateTypes must exist and never include major updates")

    manual_paths = config.get("manualReviewPaths")
    if not isinstance(manual_paths, list):
        errors.append("manualReviewPaths must be a list")
        manual_paths = []
    critical = {
        ".github/workflows/security.yml",
        ".github/workflows/dependency-governance.yml",
        ".github/dependency-governance.json",
        ".github/scripts/dependency_governance.py",
        ".github/scripts/dependency_governance_selfcheck.py",
        ".github/dependabot.yml",
    }
    for path in sorted(critical):
        if path not in manual_paths:
            errors.append(f"{path} must require manual review")

    ecosystems = config.get("ecosystems")
    if not isinstance(ecosystems, dict):
        errors.append("ecosystems must be configured")
        return unique(errors)
    pip = ecosystems.get("pip")
    if not isinstance(pip, dict) or pip.get("mode") != "manual":
        errors.append("pip ecosystem must be explicitly manual")
    elif not isinstance(pip.get("files"), list) or pip.get("files") != ["requirements.txt"]:
        errors.append("pip files must be exactly ['requirements.txt']")
    elif not nonempty(pip.get("reason")):
        errors.append("pip manual-review reason must be non-empty")

    actions = ecosystems.get("github-actions")
    if not isinstance(actions, dict):
        errors.append("github-actions ecosystem policy is missing")
    else:
        if not nonempty(actions.get("workflowPrefix")):
            errors.append("github-actions workflowPrefix must be non-empty")
        extensions = actions.get("extensions")
        if not isinstance(extensions, list) or sorted(extensions) != [".yaml", ".yml"]:
            errors.append("github-actions extensions must be .yml and .yaml")
    return unique(errors)


class GitHubApi:
    def __init__(self, token: str, repository: str, max_pagination_pages: int):
        if not token:
            raise GovernanceError("GITHUB_TOKEN is required")
        if repository.count("/") != 1:
            raise GovernanceError("GITHUB_REPOSITORY must be owner/repo")
        self.token = token
        self.repository = repository
        self.owner, self.repo = repository.split("/", 1)
        self.root = f"https://api.github.com/repos/{repository}"
        self.max_pagination_pages = max_pagination_pages

    def request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
        url = path if path.startswith("https://") else f"{self.root}{path}"
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "dependency-governance",
                **({"Content-Type": "application/json"} if payload is not None else {}),
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:1000]
            raise GovernanceError(
                f"GitHub API {method} {url} failed ({exc.code}): {detail}"
            ) from exc
        except OSError as exc:
            raise GovernanceError(f"GitHub API {method} {url} failed: {exc}") from exc
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise GovernanceError(f"GitHub API {method} {url} returned invalid JSON") from exc

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self.request("POST", path, payload)

    def patch(self, path: str, payload: dict[str, Any]) -> Any:
        return self.request("PATCH", path, payload)

    def put(self, path: str, payload: dict[str, Any]) -> Any:
        return self.request("PUT", path, payload)

    def paginate(self, path: str, selector: str | None = None) -> list[Any]:
        values: list[Any] = []
        for page in range(1, self.max_pagination_pages + 1):
            separator = "&" if "?" in path else "?"
            payload = self.get(f"{path}{separator}per_page={PAGE_SIZE}&page={page}")
            page_values = payload.get(selector) if selector else payload
            if not isinstance(page_values, list):
                raise GovernanceError(
                    f"pagination endpoint {path} did not return {selector or 'an array'}"
                )
            values.extend(page_values)
            if len(page_values) < PAGE_SIZE:
                return values
        raise GovernanceError(
            f"pagination safety limit reached for {path} after "
            f"{self.max_pagination_pages} page(s)"
        )

    def file_at(self, filename: str, ref: str) -> str:
        encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in filename.split("/"))
        payload = self.get(f"/contents/{encoded_path}?ref={urllib.parse.quote(ref, safe='')}")
        if payload.get("encoding") != "base64" or not isinstance(payload.get("content"), str):
            raise GovernanceError(f"unable to decode {filename}@{ref}")
        return base64.b64decode(payload["content"].replace("\n", "")).decode("utf-8")


def parse_dependabot_metadata(message: str) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    in_block = False
    for line in str(message or "").splitlines():
        if line.strip() == "updated-dependencies:":
            in_block = True
            continue
        if not in_block:
            continue
        if line.strip() == "...":
            break
        match = re.match(r"\s*-\s+dependency-name:\s*(.+?)\s*$", line)
        if match:
            if current:
                result.append(current)
            current = {"name": _unquote(match.group(1))}
            continue
        if not current:
            continue
        for key, field in (
            ("version", "dependency-version"),
            ("dependencyType", "dependency-type"),
            ("updateType", "update-type"),
        ):
            match = re.match(rf"\s+{re.escape(field)}:\s*(.+?)\s*$", line)
            if match:
                current[key] = _unquote(match.group(1))
    if current:
        result.append(current)
    return result


def _unquote(value: str) -> str:
    text = value.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {"'", '"'}:
        return text[1:-1]
    return text


def classify_ecosystem(files: list[dict[str, Any]], config: dict[str, Any]) -> str:
    names = [str(file.get("filename", "")) for file in files]
    pip_files = set(config["ecosystems"]["pip"]["files"])
    if names and all(name in pip_files for name in names):
        return "pip"
    actions = config["ecosystems"]["github-actions"]
    prefix, extensions = actions["workflowPrefix"], tuple(actions["extensions"])
    if names and all(name.startswith(prefix) and name.endswith(extensions) for name in names):
        return "github-actions"
    return "unknown"


def validate_provenance(
    pull: dict[str, Any],
    commits: list[dict[str, Any]],
    base_sha: str,
    config: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    now = now or datetime.now(timezone.utc)
    user = pull.get("user") or {}
    if user.get("login") != config["botLogin"]:
        reasons.append(f"PR author is {user.get('login') or 'unknown'}, not {config['botLogin']}")
    if user.get("id") != config["botUserId"]:
        reasons.append(
            f"PR author numeric identity is {user.get('id', 'unknown')}, expected {config['botUserId']}"
        )
    base = pull.get("base") or {}
    head = pull.get("head") or {}
    if base.get("ref") != config["baseBranch"]:
        reasons.append(f"base branch is {base.get('ref')}, expected {config['baseBranch']}")
    if (head.get("repo") or {}).get("full_name") != (base.get("repo") or {}).get("full_name"):
        reasons.append("Dependabot PR head must be in the same repository")
    if not str(head.get("ref") or "").startswith("dependabot/"):
        reasons.append("head branch is not a Dependabot branch")
    if pull.get("draft"):
        reasons.append("draft PRs are never autonomously merged")
    if config.get("automergeEnabled") is not True:
        reasons.append("repository autonomous merge kill switch is disabled")

    labels = {
        label if isinstance(label, str) else label.get("name")
        for label in (pull.get("labels") or [])
    }
    for label in config["manualReviewLabels"]:
        if label in labels:
            reasons.append(f"PR carries manual-review label {label}")

    try:
        created_at = datetime.fromisoformat(str(pull.get("created_at")).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        reasons.append("PR creation timestamp is invalid")
    else:
        age = now - created_at.astimezone(timezone.utc)
        if age.total_seconds() > config["maxPullRequestAgeDays"] * 86_400:
            reasons.append(
                f"PR is older than autonomous limit {config['maxPullRequestAgeDays']} day(s)"
            )

    if len(commits) != 1 or pull.get("commits") != 1:
        reasons.append("autonomous merge requires exactly one untouched Dependabot commit")
    commit = commits[0] if len(commits) == 1 else None
    if commit:
        author = commit.get("author") or {}
        committer = commit.get("committer") or {}
        git_commit = commit.get("commit") or {}
        git_author = git_commit.get("author") or {}
        git_committer = git_commit.get("committer") or {}
        verification = git_commit.get("verification") or {}
        if author.get("login") != config["botLogin"]:
            reasons.append(
                f"commit author is {author.get('login') or 'unknown'}, not {config['botLogin']}"
            )
        if author.get("id") != config["botUserId"]:
            reasons.append("commit author numeric identity does not match canonical Dependabot")
        if committer.get("login") != config["trustedCommitterLogin"]:
            reasons.append(
                f"commit was materialized by {committer.get('login') or 'unknown'}, "
                f"expected {config['trustedCommitterLogin']}"
            )
        if git_author.get("name") != config["botLogin"]:
            reasons.append("Git commit author name does not match Dependabot")
        if git_author.get("email") != config["botAuthorEmail"]:
            reasons.append("Git commit author email does not match canonical Dependabot identity")
        if (
            git_committer.get("name") != config["gitCommitterName"]
            or git_committer.get("email") != config["gitCommitterEmail"]
        ):
            reasons.append("Git commit committer identity does not match GitHub signing infrastructure")
        if verification.get("verified") is not True or verification.get("reason") != "valid":
            reasons.append("Dependabot commit signature is not GitHub-verified as valid")
        if not isinstance(verification.get("signature"), str) or not verification["signature"]:
            reasons.append("Dependabot commit has no verifiable signature material")
        if config["signedOffBy"] not in str(git_commit.get("message") or ""):
            reasons.append("Dependabot commit is missing the canonical Signed-off-by trailer")
        parents = commit.get("parents") or []
        if len(parents) != 1:
            reasons.append("Dependabot commit must not be a merge commit")
        elif parents[0].get("sha") != base_sha:
            reasons.append("PR is not rebased directly on the current base branch head")
        if commit.get("sha") != head.get("sha"):
            reasons.append("PR head SHA does not equal the verified Dependabot commit SHA")
    return {"eligible": not reasons, "reasons": unique(reasons), "commit": commit}


def validate_signed_metadata(commit: dict[str, Any] | None) -> dict[str, Any]:
    metadata = parse_dependabot_metadata(((commit or {}).get("commit") or {}).get("message", ""))
    reasons: list[str] = []
    if not metadata:
        reasons.append("verified Dependabot commit contains no updated-dependencies metadata")
    for item in metadata:
        if not item.get("name") or not item.get("version"):
            reasons.append("Dependabot metadata entry is incomplete")
    return {"eligible": not reasons, "reasons": unique(reasons), "metadata": metadata}


def parse_version(value: str) -> tuple[int, int, int] | None:
    parts = value.split(".")
    if not 1 <= len(parts) <= 3 or any(not part.isdigit() for part in parts):
        return None
    numbers = [int(part) for part in parts]
    numbers.extend([0] * (3 - len(numbers)))
    return tuple(numbers)  # type: ignore[return-value]


def compare_versions(old: str, new: str) -> str:
    old_v, new_v = parse_version(old), parse_version(new)
    if old_v is None or new_v is None:
        return "unknown"
    if new_v < old_v:
        return "downgrade"
    if new_v[0] != old_v[0]:
        return "major"
    if old_v[0] == 0 and new_v[1] != old_v[1]:
        return "major-risk"
    if new_v[1] != old_v[1]:
        return "minor"
    if new_v[2] != old_v[2]:
        return "patch"
    return "same"


def _changed_line_pairs(base_text: str, head_text: str) -> list[tuple[str | None, str | None]]:
    before = base_text.splitlines()
    after = head_text.splitlines()
    matcher = difflib.SequenceMatcher(a=before, b=after, autojunk=False)
    pairs: list[tuple[str | None, str | None]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        old = before[i1:i2]
        new = after[j1:j2]
        if tag != "replace" or len(old) != len(new):
            pairs.extend((line, None) for line in old)
            pairs.extend((None, line) for line in new)
            continue
        pairs.extend(zip(old, new, strict=True))
    return pairs


def validate_actions_semantic_change(
    files: list[dict[str, Any]],
    base_contents: dict[str, str],
    head_contents: dict[str, str],
    metadata: list[dict[str, str]],
    config: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    changes: list[dict[str, str]] = []
    manual_paths = set(config["manualReviewPaths"])
    metadata_by_name = {item.get("name"): item for item in metadata if item.get("name")}

    for file in files:
        filename = str(file.get("filename") or "")
        if filename in manual_paths:
            reasons.append(f"{filename} is dependency-governance control plane and requires manual review")
            continue
        before = base_contents.get(filename)
        after = head_contents.get(filename)
        if before is None or after is None:
            reasons.append(f"unable to load both revisions of {filename}")
            continue

        pairs = _changed_line_pairs(before, after)
        if not pairs:
            reasons.append(f"{filename} contains no semantic action reference change")
            continue
        for old_line, new_line in pairs:
            if old_line is None or new_line is None:
                reasons.append(f"{filename} changes line structure outside a uses reference")
                continue
            old_match, new_match = ACTION_LINE.fullmatch(old_line), ACTION_LINE.fullmatch(new_line)
            if not old_match or not new_match:
                reasons.append(f"{filename} changes content outside an immutable uses reference")
                continue
            if old_match.group("prefix") != new_match.group("prefix"):
                reasons.append(f"{filename} changes YAML structure around an action reference")
                continue
            if old_match.group("action") != new_match.group("action"):
                reasons.append(f"{filename} changes action identity")
                continue
            if old_match.group("ref") == new_match.group("ref"):
                reasons.append(f"{filename} changes action annotation without changing immutable SHA")
                continue

            action = old_match.group("action")
            signed = metadata_by_name.get(action)
            if not signed:
                reasons.append(f"{action} changed but is absent from signed Dependabot metadata")
                continue
            update_type = signed.get("updateType")
            if update_type not in config["allowedActionUpdateTypes"]:
                reasons.append(f"{action} uses non-autonomous update type {update_type or 'unknown'}")

            old_version, new_version = old_match.group("version"), new_match.group("version")
            signed_version = signed.get("version")
            if signed_version:
                parsed_signed = parse_version(signed_version)
                parsed_annotation = parse_version(new_version)
                if parsed_signed is None or parsed_annotation is None:
                    reasons.append(f"{action} signed or annotated version is not a stable numeric release")
                else:
                    annotation_parts = len(new_version.split("."))
                    if parsed_signed[:annotation_parts] != parsed_annotation[:annotation_parts]:
                        reasons.append(
                            f"{action} signed Dependabot version {signed_version} contradicts "
                            f"workflow annotation v{new_version}"
                        )
            risk = compare_versions(old_version, new_version)
            if risk in {"major", "major-risk", "downgrade", "unknown"}:
                reasons.append(f"{action} action annotation transition is {risk}")
            elif risk == "same" and update_type not in config["allowedActionUpdateTypes"]:
                reasons.append(f"{action} coarse action annotation cannot prove a non-major update")
            changes.append(
                {
                    "ecosystem": "github-actions",
                    "name": action,
                    "from": old_version,
                    "to": new_version,
                    "risk": risk,
                }
            )

    changed_names = {change["name"] for change in changes}
    metadata_names = {item.get("name") for item in metadata}
    extras = sorted(name for name in metadata_names if name and name not in changed_names)
    if extras:
        reasons.append(
            "signed metadata contains dependency changes not proven in workflow diff: "
            + ", ".join(extras)
        )
    if not changes:
        reasons.append("no immutable GitHub Action update could be proven")
    return {"eligible": not reasons, "reasons": unique(reasons), "changes": changes}


def validate_pip_manual(config: dict[str, Any]) -> dict[str, Any]:
    return {
        "eligible": False,
        "reasons": [config["ecosystems"]["pip"]["reason"]],
        "changes": [],
    }


def workflow_identity_matches(
    run: dict[str, Any], pull: dict[str, Any], requirement: dict[str, str]
) -> bool:
    expected_path = f".github/workflows/{requirement['file']}"
    associations = run.get("pull_requests")
    association_matches = (
        not isinstance(associations, list)
        or not associations
        or any(item.get("number") == pull.get("number") for item in associations)
    )
    return (
        run.get("name") == requirement["workflow"]
        and run.get("path") == expected_path
        and run.get("event") == "pull_request"
        and run.get("head_sha") == (pull.get("head") or {}).get("sha")
        and run.get("head_branch") == (pull.get("head") or {}).get("ref")
        and association_matches
    )


def select_qualification_run(
    runs: list[dict[str, Any]], pull: dict[str, Any], requirement: dict[str, str]
) -> dict[str, Any] | None:
    matches = [run for run in runs if workflow_identity_matches(run, pull, requirement)]
    matches.sort(
        key=lambda run: str(run.get("updated_at") or run.get("created_at") or ""),
        reverse=True,
    )
    return matches[0] if matches else None


def qualification_for_head(
    api: GitHubApi, pull: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    head_sha = (pull.get("head") or {}).get("sha")
    query = urllib.parse.urlencode({"head_sha": head_sha, "event": "pull_request"})
    runs = api.paginate(f"/actions/runs?{query}", "workflow_runs")
    qualifications: list[dict[str, Any]] = []
    any_failed = False
    all_success = True

    for requirement in config["requiredWorkflows"]:
        run = select_qualification_run(runs, pull, requirement)
        if not run:
            all_success = False
            qualifications.append({**requirement, "state": "missing", "runId": None})
            continue
        if run.get("status") != "completed":
            all_success = False
            qualifications.append(
                {**requirement, "state": str(run.get("status") or "pending"), "runId": run.get("id")}
            )
            continue
        if run.get("conclusion") != "success":
            all_success = False
            any_failed = True
            qualifications.append(
                {
                    **requirement,
                    "state": f"workflow-{run.get('conclusion') or 'unknown'}",
                    "runId": run.get("id"),
                }
            )
            continue

        jobs = api.paginate(f"/actions/runs/{run['id']}/jobs", "jobs")
        gates = [job for job in jobs if job.get("name") == requirement["gate"]]
        if len(gates) != 1:
            state = "gate-missing" if not gates else "gate-ambiguous"
            all_success = False
        else:
            gate = gates[0]
            if gate.get("status") != "completed":
                state = str(gate.get("status") or "gate-pending")
                all_success = False
            elif gate.get("conclusion") != "success":
                state = f"gate-{gate.get('conclusion') or 'unknown'}"
                all_success = False
                any_failed = True
            else:
                state = "success"
        qualifications.append({**requirement, "state": state, "runId": run.get("id")})

    exact_runs = [
        run
        for run in runs
        if run.get("head_sha") == head_sha and run.get("event") == "pull_request"
    ]
    exact_runs.sort(
        key=lambda run: str(run.get("updated_at") or run.get("created_at") or ""),
        reverse=True,
    )
    latest_by_identity: dict[str, dict[str, Any]] = {}
    for run in exact_runs:
        identity = str(run.get("path") or run.get("name") or run.get("id"))
        latest_by_identity.setdefault(identity, run)
    for run in latest_by_identity.values():
        if run.get("status") != "completed":
            all_success = False
        elif run.get("conclusion") not in SAFE_TERMINAL_CONCLUSIONS:
            all_success = False
            any_failed = True

    return {
        "allSuccess": all_success,
        "anyFailed": any_failed,
        "qualifications": qualifications,
        "runCount": len(runs),
    }


def get_current_base_sha(api: GitHubApi, branch: str) -> str:
    payload = api.get(f"/git/ref/heads/{urllib.parse.quote(branch, safe='')}")
    sha = ((payload or {}).get("object") or {}).get("sha")
    if not sha:
        raise GovernanceError(f"unable to resolve base branch {branch}")
    return sha


def get_pull_files(
    api: GitHubApi, pull: dict[str, Any], config: dict[str, Any]
) -> list[dict[str, Any]]:
    reported = pull.get("changed_files")
    if isinstance(reported, int) and reported > config["maxChangedFiles"]:
        raise PolicyBlock(
            f"PR changes {reported} files, exceeding autonomous limit {config['maxChangedFiles']}"
        )
    files = api.paginate(f"/pulls/{pull['number']}/files")
    if len(files) > config["maxChangedFiles"]:
        raise PolicyBlock(
            f"PR changes {len(files)} files, exceeding autonomous limit {config['maxChangedFiles']}"
        )
    if isinstance(reported, int) and reported != len(files):
        raise GovernanceError(
            f"GitHub reports {reported} changed files but pagination enumerated {len(files)}"
        )
    return files


def get_pull_commits(api: GitHubApi, pull: dict[str, Any]) -> list[dict[str, Any]]:
    reported = pull.get("commits")
    if isinstance(reported, int) and reported > 100:
        raise PolicyBlock(f"PR contains {reported} commits; refusing oversized autonomous history")
    commits = api.paginate(f"/pulls/{pull['number']}/commits")
    if isinstance(reported, int) and reported != len(commits):
        raise GovernanceError(
            f"GitHub reports {reported} commits but pagination enumerated {len(commits)}"
        )
    return commits


def assess_pull(
    api: GitHubApi,
    number: int,
    config: dict[str, Any],
    include_qualification: bool = True,
) -> Assessment:
    pull = api.get(f"/pulls/{number}")
    base_sha = get_current_base_sha(api, config["baseBranch"])
    try:
        files = get_pull_files(api, pull, config)
        commits = get_pull_commits(api, pull)
    except PolicyBlock as exc:
        fallback = {"eligible": False, "reasons": [str(exc)], "commit": None}
        return Assessment(
            pull,
            base_sha,
            [],
            "unknown",
            fallback,
            {
                "eligible": False,
                "reasons": ["provenance could not be established"],
                "metadata": [],
            },
            {
                "eligible": False,
                "reasons": ["change semantics were not evaluated"],
                "changes": [],
            },
            {"allSuccess": False, "anyFailed": False, "qualifications": []}
            if include_qualification
            else None,
        )

    provenance = validate_provenance(pull, commits, base_sha, config)
    metadata = (
        validate_signed_metadata(provenance["commit"])
        if provenance["commit"]
        else {
            "eligible": False,
            "reasons": ["no single verified Dependabot commit"],
            "metadata": [],
        }
    )
    ecosystem = classify_ecosystem(files, config)

    if ecosystem == "pip":
        semantic = validate_pip_manual(config)
    elif ecosystem == "github-actions" and provenance["eligible"] and metadata["eligible"]:
        base_ref = base_sha
        head_ref = (pull.get("head") or {}).get("sha")
        base_contents: dict[str, str] = {}
        head_contents: dict[str, str] = {}
        for file in files:
            filename = str(file.get("filename") or "")
            base_contents[filename] = api.file_at(filename, base_ref)
            head_contents[filename] = api.file_at(filename, head_ref)
        semantic = validate_actions_semantic_change(
            files, base_contents, head_contents, metadata["metadata"], config
        )
    elif ecosystem == "github-actions":
        semantic = {
            "eligible": False,
            "reasons": [
                "semantic auto-merge evaluation skipped because provenance or signed metadata is not eligible"
            ],
            "changes": [],
        }
    else:
        semantic = {
            "eligible": False,
            "reasons": [
                "changed files do not match an autonomously supported dependency ecosystem"
            ],
            "changes": [],
        }

    qualification = None
    if include_qualification:
        if provenance["eligible"] and metadata["eligible"] and semantic["eligible"]:
            qualification = qualification_for_head(api, pull, config)
        else:
            qualification = {
                "allSuccess": False,
                "anyFailed": False,
                "qualifications": [
                    {**item, "state": "not-evaluated", "runId": None}
                    for item in config["requiredWorkflows"]
                ],
            }
    return Assessment(
        pull,
        base_sha,
        files,
        ecosystem,
        provenance,
        metadata,
        semantic,
        qualification,
    )


def render_comment(
    assessment: Assessment,
    config: dict[str, Any],
    merged: bool = False,
    dispatches: list[dict[str, str]] | None = None,
) -> str:
    dispatches = dispatches or []
    pull = assessment.pull
    eligible = (
        assessment.provenance["eligible"]
        and assessment.metadata["eligible"]
        and assessment.semantic["eligible"]
    )
    exact_green = bool(assessment.qualification and assessment.qualification.get("allSuccess"))
    decision = "MERGED" if merged else "QUALIFIED" if eligible and exact_green else "MANUAL / WAIT"
    lines = [
        config["statusCommentMarker"],
        "## Dependency governance",
        "",
        f"**Decision:** `{decision}`",
        "",
        f"- Ecosystem: `{assessment.ecosystem}`",
        f"- Head: `{(pull.get('head') or {}).get('sha', 'unknown')}`",
        f"- Current `{config['baseBranch']}`: `{assessment.base_sha}`",
        f"- Canonical provenance: `{'pass' if assessment.provenance['eligible'] else 'blocked'}`",
        f"- Signed metadata: `{'pass' if assessment.metadata['eligible'] else 'blocked'}`",
        f"- Semantic scope: `{'pass' if assessment.semantic['eligible'] else 'blocked'}`",
    ]
    blockers = unique(
        assessment.provenance["reasons"]
        + assessment.metadata["reasons"]
        + assessment.semantic["reasons"]
    )
    if blockers:
        lines.extend(["", "**Why autonomous merge is blocked**", ""])
        lines.extend(f"- {reason}" for reason in blockers)

    if assessment.qualification:
        lines.extend(
            [
                "",
                "**Exact-head qualification**",
                "",
                "| Workflow | Stable gate | State |",
                "| --- | --- | --- |",
            ]
        )
        for item in assessment.qualification["qualifications"]:
            lines.append(
                f"| `{item['workflow']}` | `{item['gate']}` | `{item['state']}` |"
            )

    if merged and dispatches:
        lines.extend(
            [
                "",
                "**Post-merge main requalification dispatch**",
                "",
                "| Workflow | Dispatch |",
                "| --- | --- |",
            ]
        )
        for item in dispatches:
            lines.append(f"| `{item['workflow']}` | `{item['state']}` |")

    lines.extend(
        [
            "",
            "> Safety invariant: privileged governance executes only trusted default-branch code, "
            "requires an untouched GitHub-signed Dependabot commit directly on current main, proves "
            "exact workflow identities and stable gates for the exact head, never regenerates Python "
            "locks inside a dependency PR, and never autonomously merges major, downgrade, stale-base, "
            "aged-out, control-plane, or semantically ambiguous changes.",
            "",
        ]
    )
    return "\n".join(lines)


def upsert_comment(api: GitHubApi, pull_number: int, marker: str, body: str) -> None:
    comments = api.paginate(f"/issues/{pull_number}/comments")
    matches = [
        comment
        for comment in comments
        if (comment.get("user") or {}).get("login") == "github-actions[bot]"
        and marker in str(comment.get("body") or "")
    ]
    if len(matches) > 1:
        raise GovernanceError(
            f"found {len(matches)} governance status comments; refusing ambiguous idempotent update"
        )
    if matches:
        api.patch(f"/issues/comments/{matches[0]['id']}", {"body": body})
    else:
        api.post(f"/issues/{pull_number}/comments", {"body": body})


def maybe_merge(
    api: GitHubApi,
    assessment: Assessment,
    config: dict[str, Any],
    allow_merge: bool,
) -> tuple[bool, Assessment, list[dict[str, str]]]:
    eligible = (
        assessment.provenance["eligible"]
        and assessment.metadata["eligible"]
        and assessment.semantic["eligible"]
    )
    if not eligible or not (assessment.qualification or {}).get("allSuccess") or not allow_merge:
        return False, assessment, []

    refreshed = assess_pull(api, assessment.pull["number"], config, include_qualification=True)
    still_eligible = (
        refreshed.pull.get("state") == "open"
        and (refreshed.pull.get("head") or {}).get("sha")
        == (assessment.pull.get("head") or {}).get("sha")
        and refreshed.base_sha == assessment.base_sha
        and refreshed.provenance["eligible"]
        and refreshed.metadata["eligible"]
        and refreshed.semantic["eligible"]
        and bool((refreshed.qualification or {}).get("allSuccess"))
    )
    if not still_eligible:
        return False, refreshed, []

    result = api.put(
        f"/pulls/{refreshed.pull['number']}/merge",
        {
            "merge_method": config["mergeMethod"],
            "sha": (refreshed.pull.get("head") or {})["sha"],
            "commit_title": refreshed.pull.get("title") or "Qualified dependency update",
            "commit_message": (
                "Qualified and merged by dependency governance after canonical provenance, "
                "semantic-scope, exact-base, CI, extended, security, and documentation gates."
            ),
        },
    )
    merged = bool(result and result.get("merged") is True)
    if not merged:
        raise GovernanceError(f"GitHub rejected exact-head merge: {result}")

    dispatches: list[dict[str, str]] = []
    for requirement in config["requiredWorkflows"]:
        try:
            api.post(
                f"/actions/workflows/{urllib.parse.quote(requirement['file'], safe='')}/dispatches",
                {"ref": config["baseBranch"]},
            )
            dispatches.append(
                {
                    "workflow": requirement["workflow"],
                    "file": requirement["file"],
                    "state": "requested",
                }
            )
        except GovernanceError as exc:
            dispatches.append(
                {
                    "workflow": requirement["workflow"],
                    "file": requirement["file"],
                    "state": "failed",
                    "error": str(exc),
                }
            )
    return True, refreshed, dispatches


def process_pull(
    api: GitHubApi,
    number: int,
    config: dict[str, Any],
    allow_merge: bool,
) -> dict[str, Any]:
    assessment = assess_pull(api, number, config, include_qualification=True)
    user = assessment.pull.get("user") or {}
    if user.get("login") != config["botLogin"] or user.get("id") != config["botUserId"]:
        return {"skipped": True, "reason": "not canonical Dependabot", "merged": False}

    merged, final_assessment, dispatches = maybe_merge(api, assessment, config, allow_merge)
    body = render_comment(final_assessment, config, merged=merged, dispatches=dispatches)
    upsert_comment(api, number, config["statusCommentMarker"], body)

    failed_dispatches = [item for item in dispatches if item["state"] != "requested"]
    if merged and failed_dispatches:
        detail = "; ".join(
            f"{item['workflow']}: {item.get('error', 'unknown error')}"
            for item in failed_dispatches
        )
        raise GovernanceError(
            f"merge succeeded but {len(failed_dispatches)} post-merge workflow dispatch(es) failed: {detail}"
        )
    return {"skipped": False, "merged": merged, "assessment": final_assessment}


def reconcile_independently(
    pulls: list[dict[str, Any]],
    processor: Callable[[dict[str, Any]], Any],
) -> tuple[list[tuple[int, Any]], list[tuple[int, str]]]:
    results: list[tuple[int, Any]] = []
    failures: list[tuple[int, str]] = []
    for pull in pulls:
        number = pull.get("number")
        try:
            results.append((number, processor(pull)))
        except Exception as exc:
            failures.append((number, str(exc)))
    return results, failures


def event_pull_number(event: dict[str, Any], event_name: str) -> int | None:
    if event_name in {"pull_request_target", "pull_request"}:
        number = (event.get("pull_request") or {}).get("number")
        return number if isinstance(number, int) else None
    if event_name == "workflow_dispatch":
        raw = (event.get("inputs") or {}).get("pr-number")
        return None if raw in {None, ""} else parse_positive_integer(
            raw, "workflow_dispatch pr-number"
        )
    if event_name == "workflow_run":
        associations = (event.get("workflow_run") or {}).get("pull_requests") or []
        if associations and isinstance(associations[0].get("number"), int):
            return associations[0]["number"]
    return None


def resolve_workflow_run_pull(api: GitHubApi, event: dict[str, Any]) -> int | None:
    direct = event_pull_number(event, "workflow_run")
    if direct:
        return direct
    branch = (event.get("workflow_run") or {}).get("head_branch")
    if not branch:
        return None
    query = urllib.parse.urlencode({"state": "open", "head": f"{api.owner}:{branch}"})
    pulls = api.paginate(f"/pulls?{query}")
    return pulls[0]["number"] if len(pulls) == 1 else None


def _read_event() -> dict[str, Any]:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path:
        raise GovernanceError("GITHUB_EVENT_PATH is required")
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernanceError(f"unable to read GitHub event payload: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--validate-config", action="store_true")
    args = parser.parse_args(argv)
    config = load_config()
    if args.validate_config:
        print("dependency-governance config: valid")
        return 0

    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not event_name:
        raise GovernanceError("GITHUB_EVENT_NAME is required")
    event = _read_event()
    api = GitHubApi(token, repository, config["maxPaginationPages"])
    allow_merge = os.environ.get("ALLOW_MERGE") == "true"

    if event_name == "schedule":
        pulls = api.paginate("/pulls?state=open")
        dependabot_pulls = [
            pull
            for pull in pulls
            if (pull.get("user") or {}).get("login") == config["botLogin"]
            and (pull.get("user") or {}).get("id") == config["botUserId"]
        ]
        results, failures = reconcile_independently(
            dependabot_pulls,
            lambda pull: process_pull(api, pull["number"], config, allow_merge),
        )
        print(json.dumps({"reconciled": len(results), "failed": failures}, indent=2))
        if failures:
            raise GovernanceError(
                f"scheduled dependency governance failed for {len(failures)} PR(s)"
            )
        return 0

    number = event_pull_number(event, event_name)
    if number is None and event_name == "workflow_run":
        number = resolve_workflow_run_pull(api, event)
    if number is None:
        print(f"No pull request resolved for {event_name}; nothing to do.")
        return 0

    result = process_pull(api, number, config, allow_merge)
    print(
        json.dumps(
            {
                "pr": number,
                "skipped": result.get("skipped", False),
                "merged": result.get("merged", False),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PolicyBlock as exc:
        print(f"policy block: {exc}")
        raise SystemExit(0) from None
    except GovernanceError as exc:
        print(f"governance error: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
