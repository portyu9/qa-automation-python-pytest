"""
Unit tests for the calculator module.

I tag these tests with the ``unit`` marker so I can run them in isolation
(`pytest -m unit`).  Each operation is tested with simple inputs as well as
edge cases like division by zero.
"""

import pytest

from src.calc import add, subtract, multiply, divide


@pytest.mark.unit
def test_add() -> None:
    assert add(2, 3) == 5
    assert add(-1, 1) == 0


@pytest.mark.unit
def test_subtract() -> None:
    assert subtract(5, 3) == 2
    assert subtract(0, 10) == -10


@pytest.mark.unit
def test_multiply() -> None:
    assert multiply(4, 3) == 12
    assert multiply(-2, -3) == 6


@pytest.mark.unit
def test_divide() -> None:
    assert divide(10, 2) == 5
    assert divide(-9, 3) == -3


@pytest.mark.unit
def test_divide_by_zero() -> None:
    with pytest.raises(ValueError):
        divide(1, 0)