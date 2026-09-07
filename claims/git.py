"""Shared git plumbing used by more than one check."""

from __future__ import annotations

import subprocess
from pathlib import Path


def tracked_files(repo_root: Path, *pathspecs: str) -> list[str]:
    """Tracked files under `repo_root`, optionally restricted to `pathspecs`.

    Splits on newlines, not whitespace — a tracked filename may contain a
    space, which `str.split()` would shred into two bogus paths.
    """

    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", *pathspecs],
        capture_output=True,
        text=True,
        errors="replace",
    )
    return [rel for rel in result.stdout.splitlines() if rel]
