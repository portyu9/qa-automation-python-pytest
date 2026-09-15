#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from dependency_governance import load_config  # noqa: E402
from dependency_recovery import (  # noqa: E402
    DERIVED_LOCK_FILES,
    PUBLISHED_PIP_FILES,
    PUBLISHER_BOT_EMAIL,
    PUBLISHER_BOT_LOGIN,
    PUBLISHER_BOT_USER_ID,
    PUBLISH_MESSAGE,
    assess_recovery_scope,
    classify_auxiliary_run_failure,
    classify_leaf_job_failure,
    classify_required_run_failure,
    matching_non_transient_signatures,
    matching_transient_signatures,
    run_dependency_recovery,
    validate_recovery_config,
)

ROOT = SCRIPT_DIR.parents[1]
GOVERNANCE = load_config()
RECOVERY = json.loads((ROOT / ".github" / "dependency-recovery.json").read_text(encoding="utf-8"))
START = "2026-09-15T12:00:03Z"
END = "2026-09-15T12:00:05Z"


def timed_logs(message: str) -> str:
    return f"2026-09-15T12:00:04.0000000Z {message}"


def failed_job(
    *,
    job_id: int = 10,
    name: str = "quality",
    step: str = "Install hash-locked Python 3.14 dependency graph",
    conclusion: str | None = "failure",
) -> dict[str, Any]:
    return {
        "id": job_id,
        "name": name,
        "conclusion": conclusion,
        "steps": [
            {"name": step, "conclusion": conclusion, "started_at": START, "completed_at": END}
        ],
    }


def gate(name: str = "ci-gate", conclusion: str = "failure") -> dict[str, Any]:
    return {
        "id": 99,
        "name": name,
        "conclusion": conclusion,
        "steps": [{"name": "gate", "conclusion": conclusion, "started_at": START, "completed_at": END}],
    }


def canonical_source() -> dict[str, Any]:
    base_sha = "a" * 40
    source_sha = "b" * 40
    repository = "portyu9/fixture"
    pull = {
        "number": 17,
        "state": "open",
        "user": {"login": GOVERNANCE["botLogin"], "id": GOVERNANCE["botUserId"]},
        "base": {"ref": GOVERNANCE["baseBranch"], "repo": {"full_name": repository}},
        "head": {"ref": "dependabot/pip/routine-dependencies", "repo": {"full_name": repository}, "sha": source_sha},
        "draft": False,
        "labels": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "commits": 1,
        "changed_files": 1,
    }
    source = {
        "sha": source_sha,
        "author": {"login": GOVERNANCE["botLogin"], "id": GOVERNANCE["botUserId"]},
        "committer": {"login": GOVERNANCE["trustedCommitterLogin"]},
        "commit": {
            "author": {"name": GOVERNANCE["botLogin"], "email": GOVERNANCE["botAuthorEmail"]},
            "committer": {"name": GOVERNANCE["gitCommitterName"], "email": GOVERNANCE["gitCommitterEmail"]},
            "verification": {"verified": True, "reason": "valid", "signature": "source-signature"},
            "message": (
                "deps(deps): update pytest\n\n"
                "updated-dependencies:\n"
                "- dependency-name: pytest\n"
                "  dependency-version: 9.0.2\n"
                "  dependency-type: direct:development\n"
                "  update-type: version-update:semver-patch\n"
                "...\n\n"
                f"{GOVERNANCE['signedOffBy']}"
            ),
        },
        "parents": [{"sha": base_sha}],
        "files": [{"filename": "requirements.txt"}],
    }
    return {"base_sha": base_sha, "source_sha": source_sha, "pull": pull, "source": source}


def published_fixture() -> dict[str, Any]:
    fixture = canonical_source()
    publisher_sha = "c" * 40
    source_sha = fixture["source_sha"]
    publisher = {
        "sha": publisher_sha,
        "author": {"login": PUBLISHER_BOT_LOGIN, "id": PUBLISHER_BOT_USER_ID},
        "committer": {"login": GOVERNANCE["trustedCommitterLogin"]},
        "commit": {
            "author": {"name": PUBLISHER_BOT_LOGIN, "email": PUBLISHER_BOT_EMAIL},
            "committer": {"name": GOVERNANCE["gitCommitterName"], "email": GOVERNANCE["gitCommitterEmail"]},
            "verification": {"verified": True, "reason": "valid", "signature": "publisher-signature"},
            "message": (
                f"{PUBLISH_MESSAGE}\n\nGenerated from Dependabot source head {source_sha} "
                "by trusted default-branch dependency-lock-publisher."
            ),
        },
        "parents": [{"sha": source_sha}],
        "files": [{"filename": path} for path in sorted(DERIVED_LOCK_FILES)],
    }
    pull = {
        **fixture["pull"],
        "head": {**fixture["pull"]["head"], "sha": publisher_sha},
        "commits": 2,
        "changed_files": len(PUBLISHED_PIP_FILES),
    }
    return {**fixture, "pull": pull, "publisher_sha": publisher_sha, "publisher": publisher}


def workflow_run(fixture: dict[str, Any], *, name: str = "ci", path: str = ".github/workflows/ci.yml", run_id: int = 501) -> dict[str, Any]:
    return {
        "id": run_id,
        "name": name,
        "path": path,
        "event": "pull_request",
        "head_sha": fixture["pull"]["head"]["sha"],
        "head_branch": fixture["pull"]["head"]["ref"],
        "pull_requests": [{"number": fixture["pull"]["number"]}],
        "status": "completed",
        "conclusion": "failure",
        "run_attempt": 1,
        "updated_at": "2026-09-15T12:00:10Z",
    }


class FakeApi:
    def __init__(
        self,
        fixture: dict[str, Any],
        *,
        runs: list[dict[str, Any]] | None = None,
        jobs_by_run: dict[int, list[dict[str, Any]]] | None = None,
        base_sha: str | None = None,
    ) -> None:
        self.owner = "portyu9"
        self.repo = "fixture"
        self.fixture = fixture
        self.runs = runs or []
        self.jobs_by_run = jobs_by_run or {}
        self.base_sha = base_sha or fixture["base_sha"]
        self.reruns: list[int] = []

    def get(self, path: str) -> Any:
        pull = self.fixture["pull"]
        if path == f"/pulls/{pull['number']}":
            return pull
        if path.startswith("/git/ref/heads/"):
            return {"object": {"sha": self.base_sha}}
        if path == f"/commits/{self.fixture['source_sha']}":
            return self.fixture["source"]
        if self.fixture.get("publisher_sha") and path == f"/commits/{self.fixture['publisher_sha']}":
            return self.fixture["publisher"]
        raise AssertionError(f"unexpected GET {path}")

    def paginate(self, path: str, selector: str | None = None) -> list[Any]:
        pull = self.fixture["pull"]
        if path.startswith(f"/pulls/{pull['number']}/files"):
            if self.fixture.get("publisher"):
                return [{"filename": value} for value in sorted(PUBLISHED_PIP_FILES)]
            return [{"filename": "requirements.txt"}]
        if path.startswith(f"/pulls/{pull['number']}/commits"):
            commits = [self.fixture["source"]]
            if self.fixture.get("publisher"):
                commits.append(self.fixture["publisher"])
            return commits
        if path.startswith("/actions/runs?"):
            return self.runs
        match = re.match(r"/actions/runs/(\d+)/jobs", path)
        if match:
            return self.jobs_by_run.get(int(match.group(1)), [])
        if path.startswith("/pulls?state=open"):
            return [pull]
        raise AssertionError(f"unexpected paginate {path} selector={selector}")

    def post(self, path: str, payload: dict[str, Any]) -> None:
        match = re.fullmatch(r"/actions/runs/(\d+)/rerun-failed-jobs", path)
        if not match:
            raise AssertionError(f"unexpected POST {path}")
        self.reruns.append(int(match.group(1)))


class RecoverySelfCheck(unittest.TestCase):
    def test_config_is_bounded_and_semantic_steps_are_forbidden(self) -> None:
        self.assertEqual(validate_recovery_config(RECOVERY), [])
        self.assertEqual(RECOVERY["maxRunAttempts"], 2)
        for forbidden in (
            "Validate lock provenance and installed graph",
            "Run fast test gate",
            "Run deterministic Chrome/Selenium gate",
            "Run Selenium compatibility contract",
            "Run bounded Locust script-health smoke against owned fixture",
            "Scan hash-locked dependencies, configuration, and repository secrets",
            "Require applicable security jobs",
            "Download only lock artifacts from the completed read-only run",
            "Validate provenance and atomically publish generated locks",
        ):
            self.assertNotIn(forbidden, RECOVERY["transientSteps"])
        invalid = {**RECOVERY, "transientSteps": [*RECOVERY["transientSteps"], "Run fast test gate"]}
        self.assertTrue(validate_recovery_config(invalid))

    def test_pip_deterministic_signatures_override_transient_evidence(self) -> None:
        for text, expected in (
            ("ERROR: ResolutionImpossible", "pip-resolution-impossible"),
            ("Could not find a version that satisfies the requirement x", "pip-unsatisfied-requirement"),
            ("No matching distribution found for x", "pip-no-matching-distribution"),
            ("THESE PACKAGES DO NOT MATCH THE HASHES FROM THE REQUIREMENTS FILE", "pip-hash-mismatch"),
        ):
            self.assertIn(expected, matching_non_transient_signatures(text))
        result = classify_leaf_job_failure(
            failed_job(step="Compile hash-locked dependency graph"),
            timed_logs("EAI_AGAIN then ResolutionImpossible"),
            RECOVERY,
        )
        self.assertFalse(result["transient"])
        self.assertIn("pip-resolution-impossible", result["blockers"])
        self.assertIn("dns-eai-again", matching_transient_signatures("EAI_AGAIN"))

    def test_required_workflow_needs_failed_stable_gate(self) -> None:
        run = {"status": "completed", "conclusion": "failure", "run_attempt": 1}
        leaf = failed_job()
        positive = classify_required_run_failure(
            run, [leaf, gate()], {10: timed_logs("ETIMEDOUT")}, "ci-gate", RECOVERY
        )
        self.assertTrue(positive["rerunnable"], positive["reason"])
        blocked = classify_required_run_failure(
            run, [leaf], {10: timed_logs("ETIMEDOUT")}, "ci-gate", RECOVERY
        )
        self.assertFalse(blocked["rerunnable"])

    def test_auxiliary_generation_has_no_fake_aggregate_gate_but_fails_closed(self) -> None:
        run = {"status": "completed", "conclusion": "failure", "run_attempt": 1}
        transient = failed_job(name="Python 3.11 hash lock", step="Install pinned lock compiler")
        result = classify_auxiliary_run_failure(
            run, [transient], {10: timed_logs("HTTP 503")}, RECOVERY
        )
        self.assertTrue(result["rerunnable"], result["reason"])
        ambiguous = {"id": 20, "name": "Python 3.12 hash lock", "conclusion": "cancelled", "steps": []}
        blocked = classify_auxiliary_run_failure(
            run, [transient, ambiguous], {10: timed_logs("HTTP 503")}, RECOVERY
        )
        self.assertFalse(blocked["rerunnable"])
        self.assertIn("ambiguous terminal state", blocked["reason"])

    def test_one_rerun_cap_applies_to_auxiliary_and_required_runs(self) -> None:
        run = {"status": "completed", "conclusion": "failure", "run_attempt": 2}
        leaf = failed_job()
        required = classify_required_run_failure(
            run, [leaf, gate()], {10: timed_logs("EAI_AGAIN")}, "ci-gate", RECOVERY
        )
        auxiliary = classify_auxiliary_run_failure(
            run, [leaf], {10: timed_logs("EAI_AGAIN")}, RECOVERY
        )
        self.assertFalse(required["rerunnable"])
        self.assertFalse(auxiliary["rerunnable"])
        self.assertIn("recovery cap", required["reason"])

    def test_canonical_pip_source_is_recovery_eligible_but_manual_merge(self) -> None:
        fixture = canonical_source()
        api = FakeApi(fixture)
        scope = assess_recovery_scope(
            api,
            fixture["pull"],
            [{"filename": "requirements.txt"}],
            [fixture["source"]],
            fixture["base_sha"],
            GOVERNANCE,
        )
        self.assertTrue(scope["eligible"], scope["reasons"])
        self.assertEqual(scope["ecosystem"], "pip")
        self.assertEqual(scope["mergePolicy"], "manual")
        self.assertEqual(scope["provenanceState"], "canonical-dependabot")

    def test_exact_trusted_publisher_chain_is_recovery_eligible_only(self) -> None:
        fixture = published_fixture()
        api = FakeApi(fixture)
        scope = assess_recovery_scope(
            api,
            fixture["pull"],
            [{"filename": value} for value in sorted(PUBLISHED_PIP_FILES)],
            [fixture["source"], fixture["publisher"]],
            fixture["base_sha"],
            GOVERNANCE,
        )
        self.assertTrue(scope["eligible"], scope["reasons"])
        self.assertEqual(scope["ecosystem"], "pip")
        self.assertEqual(scope["mergePolicy"], "manual")
        self.assertEqual(scope["provenanceState"], "dependabot-plus-trusted-lock-publisher")
        self.assertEqual(GOVERNANCE["ecosystems"]["pip"]["mode"], "manual")

    def test_publisher_identity_message_parent_signature_and_files_are_all_mandatory(self) -> None:
        mutations = (
            ("author", {"login": "portyu9", "id": 1}),
            ("parents", [{"sha": "d" * 40}]),
            ("files", [{"filename": "requirements-lock/python-3.14.txt"}]),
        )
        for field, value in mutations:
            fixture = published_fixture()
            fixture["publisher"][field] = value
            scope = assess_recovery_scope(
                FakeApi(fixture),
                fixture["pull"],
                [{"filename": item} for item in sorted(PUBLISHED_PIP_FILES)],
                [fixture["source"], fixture["publisher"]],
                fixture["base_sha"],
                GOVERNANCE,
            )
            self.assertFalse(scope["eligible"], field)
        fixture = published_fixture()
        fixture["publisher"]["commit"]["message"] = PUBLISH_MESSAGE
        scope = assess_recovery_scope(
            FakeApi(fixture), fixture["pull"],
            [{"filename": item} for item in sorted(PUBLISHED_PIP_FILES)],
            [fixture["source"], fixture["publisher"]], fixture["base_sha"], GOVERNANCE,
        )
        self.assertFalse(scope["eligible"])

    def test_published_chain_rejects_stale_source_base(self) -> None:
        fixture = published_fixture()
        scope = assess_recovery_scope(
            FakeApi(fixture, base_sha="d" * 40), fixture["pull"],
            [{"filename": item} for item in sorted(PUBLISHED_PIP_FILES)],
            [fixture["source"], fixture["publisher"]], "d" * 40, GOVERNANCE,
        )
        self.assertFalse(scope["eligible"])
        self.assertTrue(any("current base branch head" in reason for reason in scope["reasons"]))

    def test_auxiliary_transient_failure_reruns_only_before_publisher_commit(self) -> None:
        fixture = canonical_source()
        auxiliary = workflow_run(
            fixture, name="dependency-locks", path=".github/workflows/dependency-locks.yml", run_id=701
        )
        lock_job = failed_job(name="Python 3.11 hash lock", step="Install pinned lock compiler")
        api = FakeApi(fixture, runs=[auxiliary], jobs_by_run={701: [lock_job]})
        result = run_dependency_recovery(
            api, "workflow_run", {"workflow_run": {"pull_requests": [{"number": 17}]}},
            GOVERNANCE, RECOVERY, True, lambda _api, _job: timed_logs("EAI_AGAIN")
        )
        self.assertEqual(api.reruns, [701])
        assert isinstance(result, dict)
        self.assertEqual(result["actions"][0]["workflow"], "dependency-locks")

        published = published_fixture()
        published_aux = workflow_run(
            published, name="dependency-locks", path=".github/workflows/dependency-locks.yml", run_id=702
        )
        published_api = FakeApi(published, runs=[published_aux], jobs_by_run={702: [lock_job]})
        published_result = run_dependency_recovery(
            published_api, "workflow_run", {"workflow_run": {"pull_requests": [{"number": 17}]}},
            GOVERNANCE, RECOVERY, True, lambda _api, _job: timed_logs("EAI_AGAIN")
        )
        self.assertEqual(published_api.reruns, [])
        assert isinstance(published_result, dict)
        self.assertEqual(published_result["scope"]["provenanceState"], "dependabot-plus-trusted-lock-publisher")

    def test_published_chain_can_recover_required_transient_failure_without_merging(self) -> None:
        fixture = published_fixture()
        required = workflow_run(fixture, run_id=801)
        api = FakeApi(fixture, runs=[required], jobs_by_run={801: [failed_job(), gate()]})
        result = run_dependency_recovery(
            api, "workflow_run", {"workflow_run": {"pull_requests": [{"number": 17}]}},
            GOVERNANCE, RECOVERY, True, lambda _api, _job: timed_logs("ECONNRESET")
        )
        self.assertEqual(api.reruns, [801])
        assert isinstance(result, dict)
        self.assertEqual(result["scope"]["mergePolicy"], "manual")

    def test_rebase_and_recovery_wiring_are_control_plane(self) -> None:
        dependabot = (ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
        ecosystems = re.findall(r"^\s*-\s+package-ecosystem:", dependabot, flags=re.M)
        rebases = re.findall(r"^\s*rebase-strategy:\s*auto\s*$", dependabot, flags=re.M)
        self.assertGreater(len(ecosystems), 0)
        self.assertEqual(len(rebases), len(ecosystems))
        workflow = (ROOT / ".github" / "workflows" / "dependency-governance.yml").read_text(encoding="utf-8")
        self.assertIn("workflows: [ci, extended, security, docs, dependency-locks]", workflow)
        for path in (
            ".github/dependency-recovery.json",
            ".github/scripts/dependency_recovery.py",
            ".github/scripts/dependency_recovery_selfcheck.py",
        ):
            self.assertIn(path, workflow)
            self.assertIn(path, GOVERNANCE["manualReviewPaths"])
        self.assertIn("ALLOW_RERUN", workflow)

    def test_recovery_never_duplicates_trusted_publisher_or_merge_transport(self) -> None:
        source = (SCRIPT_DIR / "dependency_recovery.py").read_text(encoding="utf-8")
        self.assertNotIn("/merges", source)
        self.assertNotIn("api.patch(", source)
        self.assertNotIn("api.put(", source)
        self.assertNotIn("/git/trees", source)
        self.assertNotIn("/git/commits", source)
        self.assertNotIn("update-branch", source)
        publisher = (SCRIPT_DIR / "dependency_lock_publisher.py").read_text(encoding="utf-8")
        self.assertIn(f'PUBLISH_MESSAGE = "{PUBLISH_MESSAGE}"', publisher)
        self.assertIn("api.patch(ref_path", publisher)
        self.assertEqual(GOVERNANCE["ecosystems"]["pip"]["mode"], "manual")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(RecoverySelfCheck)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
