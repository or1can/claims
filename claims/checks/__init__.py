"""Registers every built-in check against `claims.runner` on import.

Importing this package is what makes a check visible to `run()` — each
submodule calls `register_check` at import time. Entry points (CLI, hook,
skill) must import this package before calling `run()`.
"""

from __future__ import annotations

from . import executable_claims  # noqa: F401
from . import stale_claims  # noqa: F401
