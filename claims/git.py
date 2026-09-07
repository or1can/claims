# Copyright 2026 Orican Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Shared git plumbing used by more than one check."""

from __future__ import annotations

import re
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


def added_lines_by_file(repo_root: Path, diff_range: str) -> dict[str, set[int]]:
    """`{path: {added line numbers, in the new file}}` for `diff_range`.

    Only recognizes git's default `+++ b/<path>` header prefix — a repo with
    `diff.mnemonicPrefix` or `diff.noprefix` set produces a different prefix
    and is silently seen as having no added lines. Ported as-is from
    Project B's `tools/claim-words.py`, which has the same limitation.
    """

    diff = subprocess.run(
        ["git", "diff", "--unified=0", "--no-color", diff_range or "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    added: dict[str, set[int]] = {}
    path = None
    line_no = 0
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif line.startswith("@@"):
            header = re.search(r"\+(\d+)", line)
            line_no = int(header.group(1)) if header else 0
        elif line.startswith("+") and not line.startswith("+++"):
            if path:
                added.setdefault(path, set()).add(line_no)
            line_no += 1
    return added
