from uuid import UUID

import pytest

from src.config import TestSettings as RuntimeSettings


@pytest.mark.unit
def test_generated_run_identity_is_unique_uuid(monkeypatch) -> None:
    """Default correlation IDs must be safe, parseable, and unique across runs."""
    monkeypatch.delenv("TEST_RUN_ID", raising=False)

    first = RuntimeSettings.from_env().run_id
    second = RuntimeSettings.from_env().run_id

    assert first != second
    assert UUID(first).version == 4
    assert UUID(second).version == 4
