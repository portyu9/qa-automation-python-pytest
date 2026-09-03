"""Top-level package for the QA automation framework."""

# Explicit re-exports keep core framework modules discoverable to type checkers.
from . import api_client  # noqa: F401
from . import db  # noqa: F401
