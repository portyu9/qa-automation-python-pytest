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
            "multiple capability slices. Unknown names fail collection instead of "
            "silently producing an all-skipped run."
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
    """Apply fail-closed capability selection after pytest has built the collection."""
    requested = _requested_capabilities(config)
    if not requested:
        return

    collected = list(items)
    available = frozenset(
        capability
        for item in collected
        for capability in _item_capabilities(item)
    )
    unknown = requested - available
    if unknown:
        unknown_text = ", ".join(sorted(unknown))
        available_text = ", ".join(sorted(available)) or "<none>"
        raise pytest.UsageError(
            f"unknown --capability value(s): {unknown_text}; available: {available_text}"
        )

    reason = f"not selected by --capability={','.join(sorted(requested))}"
    skip = pytest.mark.skip(reason=reason)
    for item in collected:
        if _item_capabilities(item).isdisjoint(requested):
            item.add_marker(skip)


def pytest_report_header(config: pytest.Config) -> str | None:
    """Expose focused execution in the normal pytest terminal header."""
    requested = _requested_capabilities(config)
    if not requested:
        return None
    return f"capability selection: {', '.join(sorted(requested))}"
