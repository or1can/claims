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
art, same author); `ratect` has no equivalent (tool-survey.md). The
source tool only read a destination naming another `.md` file or a bare
`#anchor`; #91 widened that to every destination without a scheme
(`https://...`, `mailto:...`), because `check-file-refs` leaves anything
inside link syntax to this check, so a broken `[x](scripts/foo.py)` was
reported by neither. Since this check now owns all link syntax, its
existence test is the one `check-file-refs` applies to a bare path:
tracked by git, not merely on disk, so a link to a gitignored file that
no other clone has is a finding. A directory counts when git tracks a
file under it. An anchor is held to headings only on a `.md` target; on
any other it's a line or viewer fragment (`foo.py#L10`), so only the path
is checked. `known_untracked` is `check-file-refs`' key of the same name
for the same reason (see its #33 paragraph), matched against the
resolved repo-relative path, and under the same real-path confinement.

Fenced blocks and inline code spans are skipped (`claims.markdown`), and
the wider scope is why: while only `.md` destinations were read, a code
sample's `handlers[k](event)` or a quoted `` `[text](path)` `` almost
never looked like a link; with every destination read, each is a gate
finding for text that was never a link at all.

A destination starting with `~` or `/` (ticket #88) is skipped too: a
home-directory or host-absolute path was never relative to the citing
file, so joining it to that file's directory could only ever report it as
an ordinary broken link, for the wrong reason. The shapes
`claims.paths.host_relative` skips, plus any leading `~`
(`~user/x.md`): that helper stops short of a bare `~` only to spare
Markdown strikethrough, which can't occur inside a link destination.
**Known, deliberate gap:** GitHub
renders a leading `/` in a link as repo-root-relative, so a broken
`[x](/docs/missing.md)` goes unreported rather than being resolved against
the repo root; nothing in the destination tells that convention from a
host path, and matching `check-file-refs`' reading keeps the two checks
from disagreeing about the same shape.

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
at the commit `git blame` attributes its line to, by the
`claims.historical` resolver `check-file-refs` shares (#57). A `.md`
target is read from that commit's blob for its headings; any other held
if that commit's tree had a file or directory at the path (#91).
`known_untracked` isn't consulted there, since no commit's tree ever
held a deliberately untracked file. See ADR 0002 for the reasoning and
the alternatives considered. The cutoff at the commit that
first added `claims.toml` is deliberate: a line older than that was
written before this plugin gated anything, may have been broken when
written, and can't be fixed under the same rule now; no tracked
`claims.toml` means no cutoff, and every line is checked.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from posixpath import dirname, join, normpath

from ..config import exclude_patterns, path_matches, string_list_config
from ..git import blob_text, exists_at, tracked_files
from ..historical import HistoricalResolver
from ..markdown import fence_state, mask_code_spans, slugs_of
from ..runner import Finding, register_check

NAME = "check-links"

# `]\(...\)` — every match on a line, not just the first, so a line with
# more than one link still gets each of them. `[^)]*` assumes a well-formed
# markdown link's destination never itself contains a literal `)`, the same
# assumption the source tool's line-based scan makes.
LINK_RE = re.compile(r"\]\(([^)]*)\)")
SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


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


def _resolve(citing: str, path: str) -> str:
    """`path` (empty for a bare `#anchor`) resolved against `citing`'s
    directory, as a repo-relative POSIX path.

    Purely lexical (`posixpath.normpath`) — may still land outside the repo
    (a leading `../..`) or reach it only via a symlinked ancestor directory;
    `_target` is what actually confines the target to `repo_root`.
    """

    if not path:
        return citing
    return normpath(join(dirname(citing), path))


def _tracked_dirs(tracked: set[str]) -> set[str]:
    """Every directory holding at least one tracked file, the repo root
    (`.`, what `_resolve` yields for it) included."""

    dirs = {"."}
    for rel in tracked:
        parent = dirname(rel)
        while parent and parent not in dirs:
            dirs.add(parent)
            parent = dirname(parent)
    return dirs


def _target(
    repo_root: Path,
    repo_real: Path,
    resolved: str,
    tracked: set[str],
    tracked_dirs: set[str],
    known_untracked: Sequence[str],
) -> set[str] | None:
    """Heading slugs for `resolved` if it's a `.md` file, an empty set for
    any other file or a directory, or `None` if the link is broken.

    Confines the target to `repo_root` via the fully-resolved real path,
    not just a string check on `resolved` — a lexical `../` guard alone
    would miss a tracked symlinked *directory* pointing outside the repo,
    which still produces a `resolved` string with no `..` or leading `/`
    in it at all. `candidate` itself may be a symlink (the `CLAUDE.md` ->
    `AGENTS.md` convention `executable_claims.py` names): it's followed,
    not refused outright, since the same real-path check confines where it
    may lead. Only a `.md` file is ever read; an image or source file
    needs nothing from its content.
    """

    candidate = repo_root / resolved
    real = candidate.resolve()
    if not real.is_relative_to(repo_real):
        return None
    if not real.is_file() and not real.is_dir():
        return None
    # `resolved` for a tracked symlink itself (`CLAUDE.md`), the real path
    # for one reached through a tracked symlinked directory, which `git
    # ls-files` lists as the symlink alone, never the paths beneath it.
    reached = (resolved, real.relative_to(repo_real).as_posix())
    if not any(path in tracked or path in tracked_dirs for path in reached) and not (
        path_matches(resolved, known_untracked)
    ):
        return None
    if not real.is_file() or not resolved.endswith(".md"):
        return set()
    try:
        text = real.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    return slugs_of(text)


def _holds(slugs: set[str] | None, resolved: str, anchor: str) -> bool:
    """Whether a link whose target yielded `slugs` resolves: the target
    exists, and an anchor names one of its headings — asked only of a
    `.md` target, since `foo.py#L10`'s anchor is a line, not a heading."""

    if slugs is None:
        return False
    return not anchor or not resolved.endswith(".md") or anchor in slugs


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
    known_untracked = string_list_config(config, "known_untracked")
    tracked = set(tracked_files(repo_root))
    tracked_dirs = _tracked_dirs(tracked)
    historical = string_list_config(config, "historical")
    resolver = HistoricalResolver(repo_root) if historical else None
    # Per (commit, path): the same target at the same commit is read once,
    # however many historical lines that commit wrote naming it.
    slugs_at: dict[tuple[str, str], set[str] | None] = {}

    def held_at(commit: str, resolved: str, anchor: str) -> bool:
        key = (commit, resolved)
        if key not in slugs_at:
            if resolved.endswith(".md"):
                text = blob_text(repo_root, commit, resolved)
                slugs_at[key] = None if text is None else slugs_of(text)
            else:
                slugs_at[key] = set() if exists_at(repo_root, commit, resolved) else None
        return _holds(slugs_at[key], resolved, anchor)

    for rel in sorted(tracked_files(repo_root, "*.md")):
        if path_matches(rel, exclude):
            continue
        text = _read(repo_root / rel)
        if text is None:
            continue
        file_resolver = resolver if path_matches(rel, historical) else None
        lines = text.splitlines()
        in_fence = fence_state(lines)
        for line_no, line in enumerate(lines, 1):
            if in_fence[line_no - 1]:
                continue
            for match in LINK_RE.finditer(mask_code_spans(line)):
                target = match.group(1).strip()
                if not target or SCHEME_RE.match(target):
                    continue
                path, _, anchor = target.partition("#")
                if path.startswith(("~", "/")):
                    continue
                resolved = _resolve(rel, path)
                if resolved not in slug_cache:
                    slug_cache[resolved] = _target(
                        repo_root, repo_real, resolved, tracked, tracked_dirs, known_untracked
                    )
                slugs = slug_cache[resolved]
                if _holds(slugs, resolved, anchor):
                    continue
                where = ""
                if file_resolver is not None:
                    verdict = file_resolver.held_when_written(
                        rel, line_no, lambda commit: held_at(commit, resolved, anchor)
                    )
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


register_check(NAME, check)
