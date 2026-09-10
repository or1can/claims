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

"""The `check-citations` check.

A backticked name in tracked Markdown, or in a tracked Swift comment, that
cites a symbol this repository once declared (via full commit history) but
no longer has. Registered as a **gate** check — see spec.md's check
inventory — unlike this repo's other, advisory ports: a rename either left a
citation behind or it did not, so there is nothing here for a person to
weigh.

Ported from Project B's `scripts/check-citations` (Apache-2.0/relicensed
prior art, same author) — the only surveyed source tool with this check;
`ratect` has no equivalent (tool-survey.md). Scope is therefore kept as
narrow as the source tool's own: tracked `*.md` and comments in tracked
`*.swift`. A citation to a symbol some other language ever declared is
outside what `_declared_ever` can see and is never flagged — a conservative
gap (this check does nothing for it), not a false positive.

**Only names this repository once declared**, which is every name any
commit ever added — not the trees at the working copy and `HEAD` alone,
which miss anything renamed away before the current tip. Reading that
requires full history; a shallow clone (or any other git failure while
reading it) cannot answer honestly, so it is reported as a (gate) finding
of its own rather than a silent, false-clean pass — this repo's existing
`executable-claims` check established the same "say so, don't just report
zero" shape for its own "nothing to check" case.

Mark a deliberately historical reference with `was: <name>` — `<!-- was:
name -->` in Markdown, `// was: name` in Swift, the whole comment and
nothing else — which exempts citations on its own line and the next one,
and no further (Project B's own tuning: a wider scope, tried and reverted,
silenced real dead citations alongside the one it was meant to cover). The
marker is anchored to that syntax, not to the bare substring `was:`, so an
ordinary sentence that happens to use the word ("the old name was:
`loadWidget`") does not accidentally exempt a real dead citation.

The Swift declaration regex (`SWIFT_DECL_RE`) is imported from
`spliced_docs`, not redefined here: Project B's own `tools/claims.py` (this
check's and `spliced-docs`' shared prior art there) exists specifically
because two independently-written answers to "what does this repository
declare" once drifted apart; importing the one this consolidation already
ported for `spliced-docs` avoids reintroducing that exact drift.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path

from ..git import tracked_files
from ..runner import Finding, register_check
from .spliced_docs import SWIFT_DECL_RE

NAME = "check-citations"

# Qualified citations are common in prose (`Room.canRestore`), so the match
# is the *last* component rather than requiring a bare name.
CITATION_RE = re.compile(
    r"`(?:[A-Za-z_][A-Za-z_0-9]*\.)*([A-Za-z_][A-Za-z_0-9]*)(?:\([^`]*\))?`"
)
# `(?<!:)` so `https://example.com` in a string literal isn't read as a
# comment start. Anything subtler needs a Swift parser, which this is not.
COMMENT_RE = re.compile(r"(?<!:)//+\s?(.*)")
EXEMPT_RE = re.compile(r"was:\s*([A-Za-z_][A-Za-z_0-9]*)")
# The marker itself, per language — deliberately narrower than `EXEMPT_RE`
# alone: a bare `was:` substring turns up in ordinary prose ("the old name
# was: `loadWidget`"), so the exemption only applies inside an HTML comment
# in Markdown, or when a Swift comment *is* the marker start-to-end.
MARKDOWN_MARKER_RE = re.compile(r"<!--(.*?)-->")
# The whole Swift comment, start to end — not just a comment that *starts*
# with "was:", which would still let trailing prose ("was: loadWidget,
# replaced by loadGadget") ride along as if it were part of the marker.
SWIFT_MARKER_RE = re.compile(r"^was:\s*([A-Za-z_][A-Za-z_0-9]*)\s*$", re.IGNORECASE)


class _UnusableRepository(Exception):
    """The checkout can't answer whether a name is truly gone.

    Caught by `check`, which turns this into one gate finding — this repo's
    own "say so, don't just report zero" shape (see module docstring) —
    rather than either a crash or a silent, false-clean pass.
    """


def _git(repo_root: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if done.returncode != 0:
        raise _UnusableRepository(
            f"git {' '.join(args)} failed: {done.stderr.strip() or done.returncode}"
        )
    return done.stdout


def _is_shallow(repo_root: Path) -> bool:
    return _git(repo_root, "rev-parse", "--is-shallow-repository").strip() == "true"


def _read_tracked(path: Path) -> str | None:
    """A tracked file's text, or `None` for a symlink or since-removed file.

    A symlink is skipped outright rather than left to `OSError`: `read_text`
    follows it transparently, so an unguarded read would scan whatever it
    points at (a large file, or something outside the repo entirely).
    """

    if path.is_symlink():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _declared_now(repo_root: Path) -> set[str]:
    names: set[str] = set()
    for rel in tracked_files(repo_root, "*.swift"):
        text = _read_tracked(repo_root / rel)
        if text is None:
            continue
        for line in text.splitlines():
            match = SWIFT_DECL_RE.match(line)
            if match:
                names.add(match.group(1))
    return names


_CACHE_RELATIVE_PATH = Path("claims-cache") / "check-citations.json"


def _cache_path(repo_root: Path) -> Path:
    """Where this check's history-walk cache lives for `repo_root`.

    Under the real git dir (`git rev-parse --git-dir`, not an assumed
    `repo_root / ".git"`) so a worktree checkout resolves to its shared
    gitdir rather than a bare directory that isn't there. Living under the
    git dir at all means it's local to this checkout and never tracked —
    no `.gitignore` entry needed, and a fresh clone naturally starts cold.
    """

    git_dir = _git(repo_root, "rev-parse", "--git-dir").strip()
    return (repo_root / git_dir / _CACHE_RELATIVE_PATH).resolve()


def _load_cache(cache_path: Path) -> tuple[str, set[str]] | None:
    """The cached `(head sha, declared-ever names)`, or `None` on any miss.

    Any failure — missing file, corrupt JSON, wrong shape — is a cache
    miss, never an error: `_declared_ever` falls back to a full walk, which
    is slower but exactly as correct as if caching didn't exist at all.
    """

    try:
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
        return raw["head"], set(raw["names"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def _save_cache(cache_path: Path, head: str, names: set[str]) -> None:
    """Best-effort: a write failure (e.g. read-only checkout) is silently
    skipped, never raised — this cache is an optimization, not a
    correctness requirement, and the next run simply re-derives it."""

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps({"head": head, "names": sorted(names)}), encoding="utf-8"
        )
    except OSError:
        pass


def _is_ancestor(repo_root: Path, sha: str) -> bool:
    """Whether `sha` is reachable from `HEAD` — `False` (not just "no") for
    a `sha` that no longer resolves at all, e.g. after a history rewrite,
    so `_declared_ever` falls back to a full walk instead of erroring."""

    done = subprocess.run(
        ["git", "-C", str(repo_root), "merge-base", "--is-ancestor", sha, "HEAD"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    return done.returncode == 0


def _declared_in_range(repo_root: Path, rev_range: str) -> set[str]:
    """Every name tracked `*.swift` declares in `rev_range` (a single rev
    for "everything reachable from it", or `a..b` for "reachable from b,
    not from a").

    `--diff-merges=first-parent`: `git log -p` shows no diff at all for a
    merge commit, so a declaration first introduced by resolving a conflict
    would otherwise be invisible — the exact under-report this check exists
    to refuse.
    """

    log = _git(
        repo_root,
        "log",
        "--format=",
        "-p",
        "--diff-merges=first-parent",
        rev_range,
        "--",
        "*.swift",
    )
    names: set[str] = set()
    for line in log.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            match = SWIFT_DECL_RE.match(line[1:])
            if match:
                names.add(match.group(1))
    return names


def _declared_ever(repo_root: Path) -> set[str]:
    """Every name tracked `*.swift` has ever declared, across full history.

    Cached by `HEAD` sha so a repeated run on an unchanged history costs
    one `rev-parse` instead of re-walking every commit's diff. A `HEAD`
    that has moved on from the cached sha walks only the new commits
    (`cached..HEAD`) and unions them into the cached set, rather than
    redoing the full walk; a cached sha that `HEAD` can no longer reach
    (rewritten history) falls back to a full walk, same as a cold cache.
    """

    head = _git(repo_root, "rev-parse", "HEAD").strip()
    cache_path = _cache_path(repo_root)
    cached = _load_cache(cache_path)
    if cached is not None:
        cached_head, cached_names = cached
        if cached_head == head:
            return cached_names
        if _is_ancestor(repo_root, cached_head):
            names = cached_names | _declared_in_range(repo_root, f"{cached_head}..{head}")
            _save_cache(cache_path, head, names)
            return names

    names = _declared_in_range(repo_root, head)
    _save_cache(cache_path, head, names)
    return names


def _target_names(repo_root: Path) -> set[str]:
    """Directory components naming a test target, which prose cites like a
    declared symbol.

    Ported from Project B's `tools/claims.py::target_names`: a directory
    component ending in "Tests" (but not the bare, generic "Tests" itself)
    names a target, not a dead symbol.
    """

    names: set[str] = set()
    for rel in tracked_files(repo_root):
        for part in Path(rel).parent.parts:
            if part.endswith("Tests") and part != "Tests":
                names.add(part)
    return names


def _extract_markdown(line: str) -> str | None:
    return line


def _extract_swift_comment(line: str) -> str | None:
    match = COMMENT_RE.search(line)
    return match.group(1) if match else None


def _exempt_names(text: str, markdown: bool) -> set[str]:
    """Names a `was:` marker exempts in this line's citable text.

    Anchored to the documented marker syntax rather than the bare substring
    `was:` (see module docstring): a Markdown marker must sit inside an
    HTML comment; a Swift marker must be the whole comment, not a `was:`
    appearing mid-sentence in an unrelated one.
    """

    if markdown:
        comments = MARKDOWN_MARKER_RE.findall(text)
        return {name for comment in comments for name in EXEMPT_RE.findall(comment)}
    match = SWIFT_MARKER_RE.match(text.strip())
    return {match.group(1)} if match else set()


def _findings_in(rel: str, lines: list[str], current: set[str], gone: set[str], extract):
    """Dead citations in one file.

    `extract` returns the citable text of a line (the line itself for
    Markdown, the comment for Swift) or `None` for a line with no citable
    text at all, which also resets a carried `was:` marker.
    """

    markdown = rel.endswith(".md")
    found: list[Finding] = []
    carried: set[str] = set()
    for number, line in enumerate(lines, 1):
        text = extract(line)
        if text is None:
            carried = set()
            continue
        marked = _exempt_names(text, markdown)
        exempt = carried | marked
        carried = marked
        for name in dict.fromkeys(CITATION_RE.findall(text)):
            if name in current or name in exempt or name not in gone:
                continue
            found.append(
                Finding(
                    file=rel,
                    line=number,
                    message=f"`{name}` no longer exists: {line.strip()[:96]}",
                    mode=NAME,
                    gate=True,
                )
            )
    return found


def _unusable_finding(reason: str) -> Finding:
    return Finding(file=".", line=0, message=reason, mode=NAME, gate=True)


def check(
    repo_root: Path, diff_range: str, config: Mapping[str, object]
) -> list[Finding]:
    try:
        if _is_shallow(repo_root):
            raise _UnusableRepository(
                "shallow clone: history is truncated, so a name declared and "
                "later removed before the cut cannot be seen. Fetch full "
                "history (e.g. fetch-depth: 0) and re-run."
            )
        current = _declared_now(repo_root) | _target_names(repo_root)
        gone = _declared_ever(repo_root) - current
    except _UnusableRepository as why:
        return [_unusable_finding(f"check-citations cannot run here: {why}")]

    findings: list[Finding] = []
    for rel in sorted(tracked_files(repo_root, "*.md", "*.swift")):
        text = _read_tracked(repo_root / rel)
        if text is None:
            continue
        lines = text.splitlines()
        extract = _extract_markdown if rel.endswith(".md") else _extract_swift_comment
        findings.extend(_findings_in(rel, lines, current, gone, extract))
    return findings


register_check(NAME, check)
