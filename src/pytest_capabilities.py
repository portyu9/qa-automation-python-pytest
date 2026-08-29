"""Pytest extension hooks for capability-focused execution."""

from __future__ import annotations

from collections.abc import Iterable

import pytest

CAPABILITY_MARKER = "capability"


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add a repeatable selector without changing the default full-suite behavior."""
    group = parser.getgroup("capability selection")
    group.addoption(
        "--capability",
        action="append",
        default=[],
        metavar="NAME",
        help=(
            "Run tests marked with capability(NAME). Repeat the option to select "
            "multiple capability slices. Unmarked tests are skipped only when a "
            "selector is supplied."
        ),
    )


def register_capability_marker(config: pytest.Config) -> None:
    """Register the marker dynamically so strict-marker mode remains authoritative."""
    config.addinivalue_line(
        "markers",
        "capability(name): implementation capability used for focused execution",
    )


def _requested_capabilities(config: pytest.Config) -> frozenset[str]:
    values = config.getoption("capability") or []
    return frozenset(value.strip() for value in values if value and value.strip())


def _item_capabilities(item: pytest.Item) -> frozenset[str]:
    names: set[str] = set()
    for marker in item.iter_markers(name=CAPABILITY_MARKER):
        if marker.args and isinstance(marker.args[0], str) and marker.args[0].strip():
            names.add(marker.args[0].strip())
    return frozenset(names)


def pytest_collection_modifyitems(config: pytest.Config, items: Iterable[pytest.Item]) -> None:
    """Apply capability selection after collection so node ids and reports stay native."""
    requested = _requested_capabilities(config)
    if not requested:
        return

    reason = f"not selected by --capability={','.join(sorted(requested))}"
    skip = pytest.mark.skip(reason=reason)
    for item in items:
        if _item_capabilities(item).isdisjoint(requested):
            item.add_marker(skip)


def pytest_report_header(config: pytest.Config) -> str | None:
    """Expose focused execution in the normal pytest terminal header."""
    requested = _requested_capabilities(config)
    if not requested:
        return None
    return f"capability selection: {', '.join(sorted(requested))}"
