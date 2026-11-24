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

ADR 0020 changed what the answer decides. A reference that held, or
whose line predates the adoption commit, is no longer passed but
demoted to a markable advisory finding: whether the line around it is a
past claim or a current one that has gone false is a reading's to say,
not this resolver's. Only a post-adoption line whose reference held
nowhere is still a gate. A pre-adoption line is tested anyway, so its
finding says whether it held.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from .config import CONFIG_FILENAME
from .git import (
    UNCOMMITTED,
    blame_commits,
    first_commit_adding,
    head_commit,
    is_ancestor,
    parent_commits,
)


class Resolution(NamedTuple):
    """What a failed reference's history decides: whether its finding is
    still a gate, and the text that follows the check's own account of the
    failure inside its parentheses, such as "not in the working tree"."""

    gate: bool
    suffix: str


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
        self._blame: dict[str, list[str] | None] = {}
        self._predates: dict[str, bool] = {}
        self._parents: dict[str, list[str]] = {}
        # Looked up on the first failed reference, so a project whose
        # records all resolve runs no git for them (ADR 0002).
        self._looked_up = False
        self._adoption: str | None = None
        self._head: str | None = None

    def _look_up(self) -> None:
        if not self._looked_up:
            self._adoption = first_commit_adding(self._repo_root, CONFIG_FILENAME)
            self._head = head_commit(self._repo_root)
            self._looked_up = True

    def resolve(self, rel: str, line_no: int, held_at: Callable[[str], bool]) -> Resolution:
        """Whether `held_at` holds where line `line_no` of `rel` was
        written: at the line's own commit, or failing that at one of its
        parents, or for an uncommitted line at `HEAD`. Held, or on a line
        older than the adoption commit, the finding is demoted; otherwise
        it is a gate naming what was tested, or nothing in a repository
        with no `HEAD` yet, where there is nothing to test.
        """

        self._look_up()
        if rel not in self._blame:
            self._blame[rel] = blame_commits(self._repo_root, rel)
        blame = self._blame[rel]
        commit = UNCOMMITTED
        if blame is not None and line_no <= len(blame):
            commit = blame[line_no - 1]
        if commit == UNCOMMITTED:
            if self._head is None:
                return Resolution(True, "")
            if held_at(self._head):
                return Resolution(False, "; it held at HEAD")
            return Resolution(True, ", nor at HEAD")
        short = commit[:7]
        if held_at(commit):
            return Resolution(False, f"; it held at {short} where this line was written")
        if commit not in self._parents:
            self._parents[commit] = parent_commits(self._repo_root, commit)
        parents = self._parents[commit]
        for parent in parents:
            if held_at(parent):
                return Resolution(False, f"; it held at {parent[:7]}, just before {short} wrote this line")
        where = f"{short} where this line was written"
        suffix = f", nor at {where} or just before it" if parents else f", nor at {where}"
        if self._predates_adoption(commit):
            assert self._adoption is not None
            return Resolution(
                False, f"{suffix}; this line predates {CONFIG_FILENAME}'s adoption at {self._adoption[:7]}"
            )
        return Resolution(True, suffix)

    def _predates_adoption(self, commit: str) -> bool:
        if self._adoption is None:
            return False
        if commit not in self._predates:
            self._predates[commit] = commit != self._adoption and is_ancestor(
                self._repo_root, commit, self._adoption
            )
        return self._predates[commit]
