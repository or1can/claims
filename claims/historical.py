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

"""The `historical` key's resolution, shared by every check that takes it.

ADR 0002 settles what it means: a reference in an append-only record
that fails against the working tree is re-tested at the commit `git
blame` attributes its line to, and failing that at that commit's parents
— the tree just before it, where a line recording a removal still held,
since it is written in the commit that makes the removal (#116). An
uncommitted line has no blamed commit, so the tree just before it is
`HEAD`. Generalized here once `check-file-refs` became the second caller
(#57); `check-links` held it privately before. What the two share is
everything except the test itself — the blame lookup, which trees to
test, the pre-adoption cutoff and the wording naming what was tested —
so a check passes in only the predicate that says whether its reference
held at a given commit, and caches that predicate's own results however
it needs to.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .config import CONFIG_FILENAME
from .git import (
    UNCOMMITTED,
    blame_commits,
    first_commit_adding,
    head_commit,
    is_ancestor,
    parent_commits,
)


class HistoricalResolver:
    """Re-tests a failed reference against the commit that wrote its line,
    and the tree just before it.

    Only consulted for a reference that already failed against the working
    tree — one that resolves today is fine by any reading, and blaming a
    file is the expensive part, so it's done lazily, once per file, and
    only for a file that actually needs it.
    """

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root
        self._adoption = first_commit_adding(repo_root, CONFIG_FILENAME)
        self._blame: dict[str, list[str] | None] = {}
        self._predates: dict[str, bool] = {}
        self._parents: dict[str, list[str]] = {}
        self._head = head_commit(repo_root)

    def held_when_written(
        self, rel: str, line_no: int, held_at: Callable[[str], bool]
    ) -> bool | str | None:
        """`True` if `held_at` holds at the line's own commit or one of its
        parents, or that line predates the plugin and is skipped; otherwise
        what was tested, worded to follow "nor at " in a finding. An
        uncommitted line is tested at `HEAD` instead, and gets `None` only
        in a repository with no `HEAD` yet, where there is nothing to test.
        """

        if rel not in self._blame:
            self._blame[rel] = blame_commits(self._repo_root, rel)
        blame = self._blame[rel]
        commit = UNCOMMITTED
        if blame is not None and line_no <= len(blame):
            commit = blame[line_no - 1]
        if commit == UNCOMMITTED:
            if self._head is None:
                return None
            return True if held_at(self._head) else "HEAD"
        if self._predates_adoption(commit):
            return True
        if held_at(commit):
            return True
        if commit not in self._parents:
            self._parents[commit] = parent_commits(self._repo_root, commit)
        parents = self._parents[commit]
        if any(held_at(parent) for parent in parents):
            return True
        where = f"{commit[:7]} where this line was written"
        return f"{where} or just before it" if parents else where

    def _predates_adoption(self, commit: str) -> bool:
        if self._adoption is None:
            return False
        if commit not in self._predates:
            self._predates[commit] = commit != self._adoption and is_ancestor(
                self._repo_root, commit, self._adoption
            )
        return self._predates[commit]
