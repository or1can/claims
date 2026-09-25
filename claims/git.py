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
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple


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


_SRC_PREFIX = "a/"
_DST_PREFIX = "b/"
_SRC_HEADER = f"--- {_SRC_PREFIX}"
_DST_HEADER = f"+++ {_DST_PREFIX}"


class DiffHunkStart(NamedTuple):
    """An `@@` hunk header's first line number on the new side."""

    new_start: int


class DiffLine(NamedTuple):
    """One hunk content line. `sign` is `"+"` or `"-"`; `text` excludes it."""

    sign: str
    text: str


class FileDiff(NamedTuple):
    """One file's diff: its header paths, plus its hunk/line body in order.

    `src`/`dst` are `None` for that side's `/dev/null` — a new file has no
    `src`, a deleted file has no `dst`. `body` is empty (and both paths
    `None`) for a file with no `--- `/`+++ ` pair at all — a pure rename,
    a binary file, or a mode-only change.

    Grouped per file rather than as one flat event stream, so there is no
    cross-file state a caller could forget to reset: reading `src`/`dst`
    or walking `body` for one `FileDiff` can never see a stale value left
    over from the previous one, because there's nothing to carry — each
    `FileDiff` is a fresh, self-contained tuple.
    """

    src: str | None
    dst: str | None
    body: list[DiffHunkStart | DiffLine]


def _header_path(line: str, header: str) -> str | None:
    return line[len(header) :] if line.startswith(header) else None


def iter_diff(repo_root: Path, diff_range: str) -> Iterator[FileDiff]:
    """Walk `git diff --unified=0` for `diff_range`, one `FileDiff` per file.

    Pins the diff header to git's default `a/`/`b/` prefix via
    `--src-prefix`/`--dst-prefix`, overriding any repo-level
    `diff.mnemonicPrefix` or `diff.noprefix` setting that would otherwise
    change the header lines this parses and silently lose every path. See
    `QUOTEPATH_OFF` for the other header hazard this pins.

    A file's `--- `/`+++ ` header is only read while still waiting for it
    — a state cleared by `diff --git ` (the one line no hunk content can
    ever collide with) and closed the moment a `+++ ` line is seen.
    Matching a bare `+++`/`--- ` prefix wherever it appears, instead of
    gating on this, is ambiguous: an *added* line whose own content
    starts with `++` (`++i;`) becomes `+++i;` once the diff's own `+`
    marker is prepended, and a *removed* line starting with `-- ` (a SQL
    comment, say) becomes `--- ` the same way — either indistinguishable
    from a real header by a bare prefix match alone, dropping that line
    entirely.
    """

    diff = subprocess.run(
        [
            "git",
            *QUOTEPATH_OFF,
            "diff",
            "--unified=0",
            "--no-color",
            f"--src-prefix={_SRC_PREFIX}",
            f"--dst-prefix={_DST_PREFIX}",
            diff_range or "HEAD",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    in_file = False
    awaiting_header = False
    src: str | None = None
    dst: str | None = None
    body: list[DiffHunkStart | DiffLine] = []
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            if in_file:
                yield FileDiff(src, dst, body)
            in_file = True
            awaiting_header = True
            src, dst, body = None, None, []
        elif awaiting_header and line.startswith("--- "):
            src = _header_path(line, _SRC_HEADER)
        elif awaiting_header and line.startswith("+++ "):
            dst = _header_path(line, _DST_HEADER)
            awaiting_header = False
        elif line.startswith("@@"):
            match = re.search(r"\+(\d+)", line)
            body.append(DiffHunkStart(int(match.group(1)) if match else 0))
        elif line.startswith("+") or line.startswith("-"):
            body.append(DiffLine(line[0], line[1:]))
    if in_file:
        yield FileDiff(src, dst, body)


def added_lines_by_file(repo_root: Path, diff_range: str) -> dict[str, set[int]]:
    """`{path: {added line numbers, in the new file}}` for `diff_range`."""

    added: dict[str, set[int]] = {}
    for file_diff in iter_diff(repo_root, diff_range):
        line_no = 0
        for item in file_diff.body:
            if isinstance(item, DiffHunkStart):
                line_no = item.new_start
            elif item.sign == "+":
                if file_diff.dst:
                    added.setdefault(file_diff.dst, set()).add(line_no)
                line_no += 1
    return added


UNCOMMITTED = "0" * 40
"""`git blame`'s own marker for a working-tree line no commit has yet."""

_BLAME_HEADER_RE = re.compile(r"^([0-9a-f]{40}) \d+ \d+")


def blame_commits(repo_root: Path, rel: str) -> list[str] | None:
    """The commit each working-tree line of `rel` was last written in, in
    line order — `UNCOMMITTED` for a line not yet in any commit (staged or
    not). `None` when `rel` isn't in `HEAD` at all, which `git blame`
    refuses to blame: an untracked or newly-added file is entirely
    uncommitted, and the caller treats it that way.

    Porcelain format: a `<sha> <orig-line> <final-line>[ <count>]` header
    per line, metadata lines (`author ...`, `filename ...`) that never start
    with forty hex digits and a space, and the content itself tab-prefixed
    — so matching the header shape alone is unambiguous.
    """

    result = subprocess.run(
        ["git", *QUOTEPATH_OFF, "-C", str(repo_root), "blame", "--porcelain", "--", rel],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if result.returncode != 0:
        return None
    return [
        m.group(1)
        for line in result.stdout.splitlines()
        if (m := _BLAME_HEADER_RE.match(line))
    ]


def blob_text(repo_root: Path, commit: str, rel: str) -> str | None:
    """`rel`'s content as of `commit`, or `None` if it had no such path."""

    result = subprocess.run(
        ["git", *QUOTEPATH_OFF, "-C", str(repo_root), "cat-file", "-p", f"{commit}:{rel}"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    return result.stdout if result.returncode == 0 else None


def is_file_at(repo_root: Path, commit: str, rel: str) -> bool:
    """Whether `commit`'s tree has a file at `rel` — asks for the object's
    type rather than reading it, so answering costs nothing per byte, and
    a directory at `rel` (a tree, not a blob) is not a file."""

    result = subprocess.run(
        ["git", *QUOTEPATH_OFF, "-C", str(repo_root), "cat-file", "-t", f"{commit}:{rel}"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    return result.returncode == 0 and result.stdout.strip() == "blob"


def first_commit_adding(repo_root: Path, rel: str) -> str | None:
    """The oldest commit that added `rel`, or `None` if none has."""

    result = subprocess.run(
        ["git", "-C", str(repo_root), "log", "--diff-filter=A", "--format=%H", "--", rel],
        capture_output=True,
        text=True,
        errors="replace",
    )
    commits = result.stdout.split()
    return commits[-1] if commits else None


def is_ancestor(repo_root: Path, ancestor: str, descendant: str) -> bool:
    """Whether `ancestor` is `descendant` or one of its ancestors."""

    result = subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", "--is-ancestor", ancestor, descendant],
        capture_output=True,
    )
    return result.returncode == 0
