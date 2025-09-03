"""Top-level package for the QA automation demo.

Importing this package ensures that the `src` directory is recognised as a
Python package, allowing relative imports in tests.  No functions or
classes are defined here.
"""

# Explicit re-exports can help type checkers find modules
from . import calc  # noqa: F401
from . import api_client  # noqa: F401
from . import db  # noqa: F401
