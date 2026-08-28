"""Structured, privacy-aware run diagnostics for pytest executions."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

_STATUS_RANK = {"passed": 0, "skipped": 1, "failed": 2}
_SENSITIVE_KEY = re.compile(r"(?:token|secret|password|passwd|authorization|api[_-]?key)", re.I)
_SLUG = re.compile(r"[^A-Za-z0-9._-]+")


def safe_slug(value: str, *, max_length: int = 120) -> str:
    """Return a deterministic filesystem-safe identifier for a test node id."""
    normalized = _SLUG.sub("-", value).strip("-._") or "test"
    return normalized[:max_length]


def redact_url(value: str) -> str:
    """Keep URL origin/path while dropping user-info, query data, and fragments."""
    parsed = urlsplit(value)
    if not parsed.hostname:
        return value

    hostname = parsed.hostname
    host = f"[{hostname}]" if ":" in hostname else hostname
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"

    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))


def redact_mapping(values: dict[str, Any]) -> dict[str, Any]:
    """Redact common secret-bearing fields from diagnostic metadata."""
    return {
        key: "<redacted>" if _SENSITIVE_KEY.search(key) else value
        for key, value in values.items()
    }


@dataclass(frozen=True, slots=True)
class TestOutcome:
    nodeid: str
    artifact_key: str
    status: str
    phase: str
    duration_seconds: float
    worker: str


class RunManifest:
    """Collect final per-test outcomes and persist a compact JSON run manifest."""

    def __init__(self, *, run_id: str, runtime: dict[str, Any]) -> None:
        self.run_id = run_id
        self.runtime = redact_mapping(runtime)
        self.started_at_utc = datetime.now(timezone.utc).isoformat()
        self._outcomes: dict[str, TestOutcome] = {}

    @classmethod
    def from_settings(cls, settings: Any) -> "RunManifest":
        return cls(
            run_id=settings.run_id,
            runtime={
                "base_url": redact_url(settings.base_url),
                "browser": settings.browser,
                "headless": settings.headless,
                "connect_timeout_seconds": settings.connect_timeout_seconds,
                "read_timeout_seconds": settings.read_timeout_seconds,
                "retry_total": settings.retry_total,
            },
        )

    def record(
        self,
        *,
        nodeid: str,
        status: str,
        phase: str,
        duration_seconds: float,
        worker: str = "controller",
    ) -> None:
        if status not in _STATUS_RANK:
            raise ValueError(f"unsupported test status: {status!r}")

        candidate = TestOutcome(
            nodeid=nodeid,
            artifact_key=safe_slug(nodeid),
            status=status,
            phase=phase,
            duration_seconds=round(max(duration_seconds, 0.0), 6),
            worker=worker,
        )
        current = self._outcomes.get(nodeid)
        if current is None or _STATUS_RANK[candidate.status] >= _STATUS_RANK[current.status]:
            self._outcomes[nodeid] = candidate

    def as_dict(self) -> dict[str, Any]:
        outcomes = [
            asdict(item)
            for item in sorted(self._outcomes.values(), key=lambda item: item.nodeid)
        ]
        summary = {
            status: sum(item["status"] == status for item in outcomes)
            for status in ("passed", "failed", "skipped")
        }
        return {
            "schema_version": 1,
            "run_id": self.run_id,
            "started_at_utc": self.started_at_utc,
            "runtime": self.runtime,
            "summary": {**summary, "total": len(outcomes)},
            "outcomes": outcomes,
        }

    def write(self, path: Path) -> Path:
        """Write atomically so interrupted runs never leave partial JSON."""
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f"{path.suffix}.tmp")
        temporary.write_text(
            json.dumps(self.as_dict(), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)
        return path
