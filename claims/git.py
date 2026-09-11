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


QUOTEPATH_OFF = ["-c", "core.quotepath=false"]
"""Disables git's default quoting of a non-ASCII byte in a path (e.g.
`"b/caf\\303\\251.md"` instead of `b/café.md`) — every git subprocess call
in this module, and every caller parsing that output by hand, passes this
so a non-ASCII filename doesn't get silently mis-parsed, misattributed, or
dropped. Sidesteps writing a C-quote unescaper, at the cost of a narrower
fix than it looks: a literal double-quote, backslash, or control character
(tab, newline, ...) in a filename is *always* C-quoted by git regardless
of this setting, so that case is still unhandled — deliberately accepted
as out of scope, rarer than a non-ASCII filename and not worth a
hand-rolled unescaper for."""


def tracked_files(repo_root: Path, *pathspecs: str) -> list[str]:
    """Tracked files under `repo_root`, optionally restricted to `pathspecs`.

    Splits on newlines, not whitespace — a tracked filename may contain a
    space, which `str.split()` would shred into two bogus paths.
    """

    result = subprocess.run(
        ["git", *QUOTEPATH_OFF, "-C", str(repo_root), "ls-files", *pathspecs],
        capture_output=True,
        text=True,
        errors="replace",
    )
    return [rel for rel in result.stdout.splitlines() if rel]


_DST_PREFIX = "b/"
_DST_HEADER = f"+++ {_DST_PREFIX}"


def added_lines_by_file(repo_root: Path, diff_range: str) -> dict[str, set[int]]:
    """`{path: {added line numbers, in the new file}}` for `diff_range`.

    Pins the diff header to git's default `a/`/`b/` prefix via
    `--src-prefix`/`--dst-prefix`, overriding any repo-level
    `diff.mnemonicPrefix` or `diff.noprefix` setting that would otherwise
    change the `+++` line this parses and silently zero out every result.
    See `QUOTEPATH_OFF` for the other header hazard this pins.

    `path` doubles as "still waiting for this file's `+++ ` header": reset
    to `None` by `diff --git ` (the one line no hunk content can ever
    collide with), and checked against `+++ ` only while still `None`. A
    genuine `+++ ` line always follows shortly after `diff --git `, before
    any hunk content — including a non-matching one (`+++ /dev/null` for a
    deleted file), which correctly leaves `path` at `None` rather than
    matching it against later hunk lines. Matching a bare `+++` prefix
    wherever it appears, instead of gating on this, is ambiguous: an
    *added* line whose own content starts with `++` (`++i;`, `++bold++` in
    markdown) becomes `+++i;` once the diff's own `+` marker is prepended,
    indistinguishable from the header by that match alone — dropping that
    line and desyncing every line number after it in the hunk. `diff
    --git ` sidesteps the same trap a `--- ` trigger would have: hunk
    content can start with `-- ` too (a SQL comment, say), becoming `--- `
    the same way.
    """

    diff = subprocess.run(
        [
            "git",
            *QUOTEPATH_OFF,
            "diff",
            "--unified=0",
            "--no-color",
            "--src-prefix=a/",
            f"--dst-prefix={_DST_PREFIX}",
            diff_range or "HEAD",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    added: dict[str, set[int]] = {}
    path = None
    line_no = 0
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            path = None
        elif path is None and line.startswith("+++ "):
            if line.startswith(_DST_HEADER):
                path = line[len(_DST_HEADER) :]
        elif line.startswith("@@"):
            header = re.search(r"\+(\d+)", line)
            line_no = int(header.group(1)) if header else 0
        elif line.startswith("+"):
            if path:
                added.setdefault(path, set()).add(line_no)
            line_no += 1
    return added
