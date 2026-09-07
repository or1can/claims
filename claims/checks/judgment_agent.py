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

"""The `judgment-agent` check — the deterministic candidate-list half.

Registered as an **advisory** check — see spec.md's check inventory — this
is the mechanism ticket 15's subagent reads candidates from; it never itself
judges a claim true or false, and it never blocks a commit.

Not a port: ticket 04's research
(`.scratch/claims-consolidation/issues/04-judgment-agent-candidate-list.md`)
surveyed six tools (`doc-accuracy`, `documentation-audit`, both
`stale-claims.py`s, `check-citations`/`claims.py`) and found none of them
compute what this check needs — a diff-scoped *touched-subject delta*, as
opposed to "exists in the current tree" or "has ever existed, full stop".
Two failure modes this exists to avoid, both demonstrated in that research:

- **Diff-scoping by file under-selects.** A rename falsifies prose in a file
  the diff never touched; scoping the candidate search to changed *files*
  (as `doc-accuracy --diff-base` does) misses it structurally.
- **Churn-ranking reads zero on a same-commit move.** `stale-claims.py`
  scores a claim's subject by commits *since* the claim's last touch; when
  claim and subject move in the same commit, that count is zero by
  construction. This check computes a binary before/after set membership
  instead, so a same-commit move is still caught.

Three operations, run in order:

1. **Subject index.** A name this repo's tracked `*.swift`/`*.rs` declares,
   at a given tree — reusing `spliced_docs.SWIFT_DECL_RE` and
   `spliced_docs.RUST_ITEM_RE`, the same "what does this repo declare"
   answer `check-citations` and `spliced-docs` already share (this
   consolidation's own precedent for not letting that answer drift twice).
2. **Touched-subject delta.** The subject index is built once at
   `diff_range`'s base revision and once at its head (the working tree, for
   a plain `diff_range` naming one revision — matching every other check's
   convention in this codebase). `A..B`/`A...B` is split into two revisions
   at the separator instead — a deliberate simplification, not a real
   merge-base resolution for the three-dot form (that would need an extra
   `git merge-base` call this check doesn't make; no fixture here needs it).
   The symmetric difference of the two name sets is the delta: a name only
   in the base tree was removed by this diff, a name only in the head tree
   was added. A rename is therefore an unpaired remove-and-add, not a
   matched pair — ticket 04's research found no surveyed tool pairs renames
   either, and called pairing "a refinement, not solved by any tool
   surveyed"; the same is true here.
3. **Citation match.** Every backtick-delimited citation
   (`check_citations.CITATION_RE`) in tracked `*.md` text is tested for exact
   membership in the delta from (2) — a closed, code-derived vocabulary, not
   an open keyword search, which is what keeps this within "never grep the
   prose" (ticket 04's research works through why a closed, citation-shaped
   match is a different operation in kind from the transcript-grep failure
   that constraint was written against, not just a narrower version of it).
   Scope is Markdown only, narrower than `check-citations`' md-plus-Swift-
   comments: this check's job is prose citing code, and every one of this
   consolidation's user stories about "architecture or intent" claims names
   documentation, not source comments.

Each candidate carries the citing `file:line` (the `Finding`'s own
`file`/`line`) and, in its message, the diff evidence: the subject's own
declaration site and the commit(s) — if any are already committed — that
changed it. A `PreToolUse` hook runs before `git commit` completes, so the
common case is an uncommitted working-tree change with no commit yet to
name; that's reported as exactly that; never as an empty-looking omission.

**Known imprecision, not a silently accepted gap:** the subject index keeps
only a name's *first* declaration, by sorted file path — a name declared in
more than one tracked file cites whichever file sorts first, which can be a
file the diff never touched. And a subject's "commit(s) that touched it" is
every commit touching its *declaration file* in range, not one isolated to
its declaration *line* (a `git log -L` per subject would fix this at a cost
this check doesn't pay). Both bias toward more evidence shown, never toward
hiding a real candidate — a citation is never dropped for either reason.

Ranked, not filtered: every citation of a touched subject becomes a
candidate. There is no scoring step that could discard one as "probably
fine" — the ticket this implements is explicit that a candidate list must
never collapse into a clean "nothing to review" verdict, and a per-check
verdict isn't this check's job in the first place (ticket 15's subagent's).
Removed-subject candidates sort first (a citation of a now-gone name is the
more urgent read), then by how many commits already evidence the change.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

from ..git import tracked_files
from ..runner import Finding, register_check
from .check_citations import CITATION_RE
from .spliced_docs import RUST_ITEM_RE, SWIFT_DECL_RE

NAME = "judgment-agent"

MODE_REMOVED = "judgment-agent-removed"
MODE_ADDED = "judgment-agent-added"

_SUBJECT_PATTERNS = ("*.swift", "*.rs")


class _Subject(NamedTuple):
    file: str
    line: int


class _Endpoints(NamedTuple):
    """`diff_range` split in two — `head` is `None` for "the working tree"."""

    base: str
    head: str | None


def _git(repo_root: Path, *args: str) -> str | None:
    """`None` on any git failure — this check is advisory: best effort, never a crash."""

    done = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        errors="replace",
    )
    return done.stdout if done.returncode == 0 else None


def _split_diff_range(diff_range: str) -> _Endpoints:
    dr = diff_range or "HEAD"
    for sep in ("...", ".."):
        if sep in dr:
            base, _, head = dr.partition(sep)
            return _Endpoints(base or "HEAD", head or None)
    return _Endpoints(dr, None)


def _declared_name(rel: str, line: str) -> str | None:
    if rel.endswith(".swift"):
        match = SWIFT_DECL_RE.match(line)
        return match.group(1) if match else None
    if rel.endswith(".rs"):
        match = RUST_ITEM_RE.match(line)
        return match.group(2) if match else None
    return None


def _subject_index(files: Mapping[str, str]) -> dict[str, _Subject]:
    """`name -> (file, line)` of its first declaration across `files`."""

    index: dict[str, _Subject] = {}
    for rel, text in sorted(files.items()):
        for number, line in enumerate(text.splitlines(), 1):
            name = _declared_name(rel, line)
            if name and name not in index:
                index[name] = _Subject(rel, number)
    return index


def _read_tracked(path: Path) -> str | None:
    if path.is_symlink():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _files_working_tree(repo_root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for rel in tracked_files(repo_root, *_SUBJECT_PATTERNS):
        text = _read_tracked(repo_root / rel)
        if text is not None:
            files[rel] = text
    return files


def _files_at_ref(repo_root: Path, ref: str) -> dict[str, str]:
    # `git ls-tree` doesn't support the wildcard pathspecs `git ls-files`/
    # `git diff` do (its magic set has no `glob`) — list every path and
    # filter in Python instead of passing `_SUBJECT_PATTERNS` as a pathspec.
    listing = _git(repo_root, "ls-tree", "-r", "--name-only", ref)
    if listing is None:
        return {}
    files: dict[str, str] = {}
    for rel in listing.splitlines():
        if not rel.endswith((".swift", ".rs")):
            continue
        text = _git(repo_root, "show", f"{ref}:{rel}")
        if text is not None:
            files[rel] = text
    return files


def _commits_touching(repo_root: Path, endpoints: _Endpoints, rel: str) -> list[str]:
    head = endpoints.head or "HEAD"
    log = _git(repo_root, "log", "--format=%h", f"{endpoints.base}..{head}", "--", rel)
    return log.split() if log else []


def _evidence(endpoints: _Endpoints, subject: _Subject, commits: list[str]) -> str:
    if commits:
        return f"declared at {subject.file}:{subject.line} (touched in {', '.join(commits)})"
    if endpoints.head is None:
        return f"declared at {subject.file}:{subject.line} (uncommitted working-tree change)"
    return f"declared at {subject.file}:{subject.line}"


class _Candidate(NamedTuple):
    rank: tuple[int, int]
    finding: Finding


def _citations(repo_root: Path) -> list[tuple[str, int, str]]:
    found: list[tuple[str, int, str]] = []
    for rel in sorted(tracked_files(repo_root, "*.md")):
        text = _read_tracked(repo_root / rel)
        if text is None:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for match in CITATION_RE.finditer(line):
                found.append((rel, number, match.group(1)))
    return found


def check(
    repo_root: Path, diff_range: str, config: Mapping[str, object]
) -> list[Finding]:
    endpoints = _split_diff_range(diff_range)

    base_index = _subject_index(_files_at_ref(repo_root, endpoints.base))
    head_files = (
        _files_at_ref(repo_root, endpoints.head)
        if endpoints.head
        else _files_working_tree(repo_root)
    )
    head_index = _subject_index(head_files)

    removed = base_index.keys() - head_index.keys()
    added = head_index.keys() - base_index.keys()
    if not removed and not added:
        return []

    candidates: list[_Candidate] = []
    for rel, line, name in _citations(repo_root):
        if name in removed:
            subject, mode, direction = base_index[name], MODE_REMOVED, "removed"
        elif name in added:
            subject, mode, direction = head_index[name], MODE_ADDED, "added"
        else:
            continue

        commits = _commits_touching(repo_root, endpoints, subject.file)
        evidence = _evidence(endpoints, subject, commits)
        message = f"cites `{name}`, {direction} by this diff — {evidence}"
        candidates.append(
            _Candidate(
                rank=(0 if direction == "removed" else 1, -len(commits)),
                finding=Finding(file=rel, line=line, message=message, mode=mode, gate=False),
            )
        )

    candidates.sort(key=lambda c: (c.rank, c.finding.file, c.finding.line))
    return [c.finding for c in candidates]


register_check(NAME, check)
