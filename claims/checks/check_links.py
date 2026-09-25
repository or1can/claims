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

"""The `check-links` check: every internal Markdown link resolves to the
file and heading it names. `docs/checks/check-links.md` is the account of
what is in scope, which keys it takes and how `historical` resolves; this
docstring is why the code is shaped the way it is.

Gate (spec.md's check inventory): a broken relative link is inert now,
not a judgment call for later.

Ported from Project B's `scripts/check-links`, plus its shared
`scripts/slugs.sh` for the heading-slug rule (Apache-2.0/relicensed prior
art, same author); `ratect` has no equivalent (tool-survey.md). Scope
matches the source tool's own — another `.md` file, with or without
`#anchor`, or a bare `#anchor` into the current file — with a scheme
(`https://...`, `mailto:...`) excluded explicitly, since a URL that
happens to end `.md` would otherwise pass the source tool's own
path-shaped filter.

Two departures from the source tool, both fixes rather than ports. Its
first version required a link to end in bare `.md)`, so a link ending
`...md#anchor)` — path *plus* anchor — silently never got validated at
all; this port checks the path-plus-anchor form from the start (ticket
13's named regression case). And its `slugs_of` stripped underscores,
which GitHub's slugger does not (ticket 26); no de-duplication for
repeated identical headings, matching upstream's own scope.

`historical` (ticket #50) exists for an append-only record like a
changelog, whose shipped entries a project's rules forbid editing: the
link was a true claim when written, and the record's job is to stay what
it was — so a page rename elsewhere in the tree shouldn't turn every old
entry naming it into a gate finding nothing is allowed to fix. Hence a
link that fails against the working tree is re-resolved against the tree
at the commit `git blame` attributes its line to. See ADR 0002 for the
reasoning and the alternatives considered. The cutoff at the commit that
first added `claims.toml` is deliberate: a line older than that was
written before this plugin gated anything, may have been broken when
written, and can't be fixed under the same rule now; no tracked
`claims.toml` means no cutoff, and every line is checked.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from posixpath import dirname, join, normpath

from ..config import (
    CONFIG_FILENAME,
    exclude_patterns,
    path_matches,
    string_list_config,
)
from ..git import (
    UNCOMMITTED,
    blame_commits,
    blob_text,
    first_commit_adding,
    is_ancestor,
    tracked_files,
)
from ..runner import Finding, register_check

NAME = "check-links"

# `]\(...\)` — every match on a line, not just the first, so a line with
# more than one link still gets each of them. `[^)]*` assumes a well-formed
# markdown link's destination never itself contains a literal `)`, the same
# assumption the source tool's line-based scan makes.
LINK_RE = re.compile(r"\]\(([^)]*)\)")
# Only a target naming another `.md` file (with or without `#anchor`), or a
# bare `#anchor`, is in scope — this is what excludes images, source-file
# links, and external URLs, without a special case for any of them
# (matches the source tool's own filter).
RELEVANT_RE = re.compile(r"\.md(?:$|#)|^#")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
HEADING_RE = re.compile(r"^#{1,6} (.*)$")
SLUG_STRIP_RE = re.compile(r"[^a-z0-9 _-]")


def _read(path: Path) -> str | None:
    """A file's text, or `None` for a symlink, missing file, or unreadable path.

    Mirrors `check_citations._read_tracked`'s guard: a dangling or
    arbitrary-target symlink must not crash the check.
    """

    if path.is_symlink() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _slug(heading: str) -> str:
    return SLUG_STRIP_RE.sub("", heading.lower()).replace(" ", "-")


def _slugs_of(text: str) -> set[str]:
    return {_slug(m.group(1)) for line in text.splitlines() if (m := HEADING_RE.match(line))}


def _resolve(citing: str, path: str) -> str:
    """`path` (empty for a bare `#anchor`) resolved against `citing`'s
    directory, as a repo-relative POSIX path.

    Purely lexical (`posixpath.normpath`) — may still land outside the repo
    (a leading `../..`) or reach it only via a symlinked ancestor directory;
    `_target_slugs` is what actually confines the read to `repo_root`.
    """

    if not path:
        return citing
    return normpath(join(dirname(citing), path))


def _target_slugs(repo_root: Path, repo_real: Path, resolved: str) -> set[str] | None:
    """Heading slugs for `resolved`, or `None` if it can't be read as an
    ordinary file inside the repo.

    Used both to test whether the link's path resolves at all (`None` means
    broken link) and, when there's an anchor, against its headings. Confines
    the read to `repo_root` via the fully-resolved real path, not just a
    string check on `resolved` — a lexical `../` guard alone would miss a
    tracked symlinked *directory* pointing outside the repo, which still
    produces a `resolved` string with no `..` or leading `/` in it at all.
    `candidate` itself may be a symlink (the `CLAUDE.md` -> `AGENTS.md`
    convention `executable_claims.py` names): it's followed, not refused
    outright, since the same real-path check confines where it may lead.
    """

    candidate = repo_root / resolved
    real = candidate.resolve()
    if not real.is_relative_to(repo_real) or not real.is_file():
        return None
    try:
        text = real.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return _slugs_of(text)


def _finding(rel: str, line_no: int, message: str) -> Finding:
    return Finding(file=rel, line=line_no, message=message, mode=NAME, gate=True)


def check(repo_root: Path, diff_range: str, config: Mapping[str, object]) -> list[Finding]:
    repo_real = repo_root.resolve()
    # Keyed on the resolved target path, not per link: a heavily cross-linked
    # doc would otherwise be re-read and re-scanned for headings once per
    # referencing link rather than once per target file.
    slug_cache: dict[str, set[str] | None] = {}
    findings: list[Finding] = []
    exclude = exclude_patterns(config)
    historical = string_list_config(config, "historical")
    resolver = _HistoricalResolver(repo_root) if historical else None
    for rel in sorted(tracked_files(repo_root, "*.md")):
        if path_matches(rel, exclude):
            continue
        text = _read(repo_root / rel)
        if text is None:
            continue
        file_resolver = resolver if path_matches(rel, historical) else None
        for line_no, line in enumerate(text.splitlines(), 1):
            for match in LINK_RE.finditer(line):
                target = match.group(1).strip()
                if SCHEME_RE.match(target) or not RELEVANT_RE.search(target):
                    continue
                path, _, anchor = target.partition("#")
                resolved = _resolve(rel, path)
                if resolved not in slug_cache:
                    slug_cache[resolved] = _target_slugs(repo_root, repo_real, resolved)
                slugs = slug_cache[resolved]
                if slugs is not None and (not anchor or anchor in slugs):
                    continue
                where = ""
                if file_resolver is not None:
                    verdict = file_resolver.held_when_written(rel, line_no, resolved, anchor)
                    if verdict is True:
                        continue
                    if isinstance(verdict, str):
                        where = f", nor at {verdict[:7]} where this line was written"
                if slugs is None:
                    message = f"broken link: {target}"
                    if where:
                        message += f" (not in the working tree{where})"
                    findings.append(_finding(rel, line_no, message))
                else:
                    findings.append(
                        _finding(
                            rel,
                            line_no,
                            f"broken anchor: {target} "
                            f"({resolved} has no heading with that slug{where})",
                        )
                    )
    return findings


class _HistoricalResolver:
    """Re-resolves a failed link against the commit that wrote its line.

    Only consulted for a link that already failed against the working tree
    — a link that resolves today is fine by any reading, and blaming a file
    is the expensive part, so it's done lazily, once per file, and only for
    a file that actually needs it.
    """

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = repo_root
        self._adoption = first_commit_adding(repo_root, CONFIG_FILENAME)
        self._blame: dict[str, list[str] | None] = {}
        self._predates: dict[str, bool] = {}
        self._slugs: dict[tuple[str, str], set[str] | None] = {}

    def held_when_written(
        self, rel: str, line_no: int, resolved: str, anchor: str
    ) -> bool | str | None:
        """`True` if the link held at the line's own commit, or that line
        predates the plugin and is skipped; the commit's SHA if it didn't
        hold there either; `None` for an uncommitted line, which has no
        history to consult."""

        if rel not in self._blame:
            self._blame[rel] = blame_commits(self._repo_root, rel)
        blame = self._blame[rel]
        if blame is None or line_no > len(blame):
            return None
        commit = blame[line_no - 1]
        if commit == UNCOMMITTED:
            return None
        if self._predates_adoption(commit):
            return True
        key = (commit, resolved)
        if key not in self._slugs:
            text = blob_text(self._repo_root, commit, resolved)
            self._slugs[key] = None if text is None else _slugs_of(text)
        slugs = self._slugs[key]
        if slugs is not None and (not anchor or anchor in slugs):
            return True
        return commit

    def _predates_adoption(self, commit: str) -> bool:
        if self._adoption is None:
            return False
        if commit not in self._predates:
            self._predates[commit] = commit != self._adoption and is_ancestor(
                self._repo_root, commit, self._adoption
            )
        return self._predates[commit]


register_check(NAME, check)
