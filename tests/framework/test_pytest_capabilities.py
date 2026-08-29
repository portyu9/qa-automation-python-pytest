"""Executable contracts for pytest's native extension and fixture model."""

from __future__ import annotations

import asyncio
import logging
import os

import pytest


@pytest.mark.capability("parametrization")
@pytest.mark.parametrize(
    ("numerator", "denominator", "expected"),
    [(6, 3, 2), (7, 2, 3.5), (-9, 3, -3)],
    ids=["integer-result", "fractional-result", "negative-result"],
)
def test_parametrized_assertion_matrix(numerator: int, denominator: int, expected: float) -> None:
    assert numerator / denominator == pytest.approx(expected)


@pytest.mark.capability("exceptions")
def test_exception_and_warning_assertions() -> None:
    with pytest.raises(ZeroDivisionError):
        _ = 1 / 0

    with pytest.warns(UserWarning, match="degraded fixture"):
        import warnings

        warnings.warn("degraded fixture", UserWarning, stacklevel=1)


@pytest.mark.capability("fixtures")
def test_builtin_fixture_isolation(tmp_path, monkeypatch, capsys, caplog) -> None:
    payload = tmp_path / "evidence.txt"
    payload.write_text("deterministic evidence\n", encoding="utf-8")

    with monkeypatch.context() as patch:
        patch.setenv("CAPABILITY_TEST_TOKEN", "isolated")
        assert os.environ["CAPABILITY_TEST_TOKEN"] == "isolated"

    assert "CAPABILITY_TEST_TOKEN" not in os.environ

    print(payload.read_text(encoding="utf-8").strip())
    assert capsys.readouterr().out == "deterministic evidence\n"

    with caplog.at_level(logging.INFO):
        logging.getLogger(__name__).info("capability-event", extra={"run_id": "fixture-contract"})
    assert any(record.message == "capability-event" for record in caplog.records)


@pytest.mark.capability("mocking")
def test_pytest_mock_spy_preserves_real_behavior(mocker) -> None:
    class Calculator:
        def multiply(self, left: int, right: int) -> int:
            return left * right

    calculator = Calculator()
    spy = mocker.spy(calculator, "multiply")

    assert calculator.multiply(6, 7) == 42
    spy.assert_called_once_with(6, 7)


@pytest.mark.capability("asyncio")
@pytest.mark.asyncio
async def test_asyncio_integration_uses_native_async_test_execution() -> None:
    async def resolve() -> dict[str, str]:
        await asyncio.sleep(0)
        return {"status": "ready"}

    assert await resolve() == {"status": "ready"}
