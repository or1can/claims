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

"""The trees a past or superseded claim is read at (ADR 0019, #267), and
a copy of each that the reading agent, which has no shell, can read.

A past claim is read where ADR 0002 reads a historical reference: at the
commit `git blame` attributes its line to, and just before it, at that
commit's parents; an uncommitted line in the working tree and at `HEAD`.

A superseded claim is read just before the change that superseded it,
found from the line its kind rests on: the Status note, or the line of
the record it points to, saying the claim is replaced or withdrawn. That
change is the commit that first added the line, traced back through
every later edit to it, not the one blame names: blame on a note
reworded after the change it records names the rewording, and just
before that the claim is already replaced. A note added in the working
tree supersedes there, so the claim is read at `HEAD`.
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Literal, NamedTuple

from .git import (
    UNCOMMITTED,
    check_out_to,
    line_commit,
    line_origin,
    parent_commits,
    resolve_commit,
    toplevel,
    tracked_files,
)
from .lines import git_lines, tracked_text

# The kinds `claim_trees` names trees for; a current or intended claim is
# read in the tree as it stands.
TREE_KINDS = ("past", "superseded")

# Where `tree_copy` keeps its copies, at the top of the work tree.
CACHE_DIR = ".claims"


class Tree(NamedTuple):
    """One tree a claim is named at: `role` is `written`, `superseded` or
    `before`, and `commit` is `None` for the working tree."""

    role: Literal["written", "superseded", "before"]
    commit: str | None


def tree_copy(repo_root: Path, rev: str) -> Path:
    """A read-only copy of the tracked files at the commit `rev` names,
    with no `.git`, made once per commit under `.claims/trees/` at the top
    of the work tree and reused after. Raises `ValueError` when `rev`
    names no commit.

    In the work tree, where an editor shows it, as `.git/` it often
    doesn't; and `.claims/` ignores itself, as `.pytest_cache/` does, so
    `git status` never lists it and a search that honours ignore files
    doesn't read an old tree as the tree as it stands, as one passing
    `--hidden` from the top would read `.git/`."""

    commit = resolve_commit(repo_root, rev)
    top = toplevel(repo_root)
    if commit is None or top is None:
        raise ValueError(f"{rev} names no commit")
    if (top / CACHE_DIR).is_symlink():
        raise ValueError(f"{CACHE_DIR} is a symlink, so a copy there could be written anywhere")
    # `icase`: on a case-insensitive filesystem a committed `.CLAIMS/` is
    # this same directory.
    if tracked_files(top, f":(icase){CACHE_DIR}"):
        # A copy git tracks is whatever was committed, not the commit's tree.
        raise ValueError(f"git tracks {CACHE_DIR}/, which holds copies claims makes itself")
    cache = top / CACHE_DIR / "trees"
    dest = cache / commit
    if cache.is_symlink() or dest.is_symlink():
        raise ValueError(f"{CACHE_DIR}/trees holds a symlink, so a copy there could be written anywhere")
    if dest.is_dir():
        return dest
    cache.mkdir(parents=True, exist_ok=True)
    ignore = top / CACHE_DIR / ".gitignore"
    if not ignore.exists():
        ignore.write_text("*\n", encoding="utf-8")
    staging = Path(tempfile.mkdtemp(prefix=f".{commit}-", dir=cache))
    if not check_out_to(repo_root, commit, staging):
        shutil.rmtree(staging)
        raise ValueError(f"{rev} names no commit")
    for path in staging.rglob("*"):
        if path.is_file() and not path.is_symlink():
            path.chmod(path.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    try:
        os.rename(staging, dest)
    except OSError:
        if not dest.is_dir():
            raise
        # Another run made it first; theirs is the same tree. Its
        # directories stay writable, so its read-only files can go.
        shutil.rmtree(staging)
    return dest


def claim_trees(repo_root: Path, rel: str, line_no: int, kind: str) -> list[Tree]:
    """The trees a `kind` claim is named at, from line `line_no` of `rel`
    in the working tree: for `past`, the claim's own line, `written` where
    it was and `before` at each parent; for `superseded`, the line the kind
    rests on, `superseded` where it came in and `before` at each parent,
    the trees the claim is read at. Raises `ValueError` for a line `rel`
    doesn't have."""

    try:
        count = len(git_lines(tracked_text(repo_root / rel, errors="replace")))
    except OSError:
        count = 0
    if not 1 <= line_no <= count:
        raise ValueError(f"{rel} has no line {line_no}")
    role = "written" if kind == "past" else "superseded"
    blamed = line_commit(repo_root, rel, line_no)
    if blamed is None or blamed[0] == UNCOMMITTED:
        head = resolve_commit(repo_root, "HEAD")
        return [Tree(role, None), *([Tree("before", head)] if head else [])]
    commit, origin_line, origin_path = blamed
    if kind == "superseded":
        commit = line_origin(repo_root, commit, origin_path, origin_line) or commit
    return [Tree(role, commit), *(Tree("before", p) for p in parent_commits(repo_root, commit))]
