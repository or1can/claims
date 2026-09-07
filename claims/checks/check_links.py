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

"""The `check-links` check.

Every internal Markdown link — a link to another tracked `*.md` file, or a
bare `#anchor` within the same file — resolves: the target file exists, and
if the link names a heading anchor, that anchor matches one of the target's
headings under GitHub's slug rule. Registered as a **gate** check — see
spec.md's check inventory — a broken relative link is inert now, not a
judgment call for later.

Ported from Project B's `scripts/check-links`, plus its shared
`scripts/slugs.sh` for the heading-slug rule (Apache-2.0/relicensed prior
art, same author); `ratect` has no equivalent (tool-survey.md). Scope
matches the source tool's own: a link is only checked here when its target
names another `.md` file (with or without `#anchor`) or is a bare `#anchor`
into the current file — an image, a source-file link, or an external URL is
out of scope, same as upstream. A scheme (`https://...`, `mailto:...`) is
excluded explicitly, since a URL that happens to end `.md` would otherwise
pass the source tool's own path-shaped filter.

The source tool's first version required a link to end in bare `.md)`, so a
link ending `...md#anchor)` — path *plus* anchor — silently never got
validated at all; this port checks the path-plus-anchor form from the start
(ticket 13's named regression case).

Heading slugs use the same rule as the source tool's `slugs_of`: lowercase,
strip anything outside `[a-z0-9 -]`, spaces to hyphens — no de-duplication
for repeated identical headings, matching upstream's own scope.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from posixpath import dirname, join, normpath

from ..git import tracked_files
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
SLUG_STRIP_RE = re.compile(r"[^a-z0-9 -]")


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
    """

    candidate = repo_root / resolved
    if candidate.is_symlink():
        return None
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
    for rel in sorted(tracked_files(repo_root, "*.md")):
        text = _read(repo_root / rel)
        if text is None:
            continue
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
                if slugs is None:
                    findings.append(_finding(rel, line_no, f"broken link: {target}"))
                elif anchor and anchor not in slugs:
                    findings.append(
                        _finding(
                            rel,
                            line_no,
                            f"broken anchor: {target} "
                            f"({resolved} has no heading with that slug)",
                        )
                    )
    return findings


register_check(NAME, check)
