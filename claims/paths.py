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

"""The path primitives more than one check reads prose with.

`check-file-refs` owned these until `stale-claims` came to read paths
the same way (#87); generalized here (#108) so that neither check reaches
into the other's private names. Nothing here decides which paths a check
keeps — in particular a leading `../`, which `check-file-refs` skips and
`stale-claims` resolves from the citing file's directory, is each
check's own call, stated in its own module.
"""

from __future__ import annotations

import re
from posixpath import dirname, join, normpath

# A leading `\b` word boundary never matches between two non-word
# characters, so it silently drops the leading dot of a real
# hidden-directory path (a space then `.claude-plugin/plugin.json` — `\b`
# can't fire before the `.`, only before the `c` after it — reporting
# `claude-plugin/plugin.json` instead of the real path, which then never
# resolves). Replacing the leading `\b` with a negative lookbehind for
# "already inside a longer run of path-shaped characters" fixes it: it
# matches equally well before a word character or a literal leading dot,
# as long as neither is itself preceded by another path character.
#
# That same lookbehind also now captures a leading `./`/`../` whole
# (rather than `\b` incidentally skipping past it to start the match at
# the first real path segment) — `repo_relative` below is what turns a
# captured `./x` back into the bare `x` a real check-out's `tracked_set`
# actually contains, and each check decides for itself what a `../x`
# match means.
PATH_RE = re.compile(r"(?<![\w.-])(?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]+\b")


def host_relative(line: str, start: int) -> bool:
    """Whether `line[start:]`'s own match was immediately preceded by an
    unconsumed `/` — `/` isn't in `PATH_RE`'s own character class, so a
    match starts right after it with no trace of it left in the captured
    text. Catches a host-absolute path (`/etc/docker/daemon.json`) and,
    since `~` itself never survives into a match either way, a bare
    `~/`-prefixed home-directory shorthand too (`~/.docker/config.json` —
    the character actually inspected here is the `/` right after the
    `~`, not the `~` itself; deliberately not extended to also check for a
    bare `~` immediately before the match, which would additionally catch
    the rarer `~username/` shell convention at the cost of also matching
    the second `~` of Markdown strikethrough, `~~docs/removed.md~~`, and
    wrongly skipping it).

    Neither shape is ever a repo-relative candidate (ticket #38): unlike
    a leading `../`, whose two characters survive as part of the match
    itself, an unconsumed `/` is invisible by the time a caller holds the
    plain candidate string — so this has to be checked against the source
    line, at the one point that still has both `line` and the match's own
    start position in scope.
    """

    return start > 0 and line[start - 1] == "/"


def repo_relative(candidate: str) -> str:
    """`candidate`, as written in prose, in the repo-root-relative form
    `tracked_set` actually contains.

    A leading `./` unambiguously means "from here" the same way it does
    in a shell command; stripped, since `tracked_set` never contains an
    entry with a `./` prefix of its own. A leading `../` is not resolved
    here: `check_file_refs.check` skips such a candidate outright and
    `stale_claims.check` tries it from the citing file's directory alone,
    each for its own stated reason.
    """

    if candidate.startswith("./"):
        return candidate[2:]
    return candidate


def citing_relative(citing: str, candidate: str) -> str:
    """`candidate` resolved against `citing`'s own directory, as a
    repo-relative POSIX path — the same lexical join/normalize
    `check_links._resolve` already does for a real Markdown link's
    destination, applied as a second try once `candidate` has already
    failed to resolve as repo-root-relative (ticket #32).

    Purely lexical, same as its model — may land outside the repo (e.g. a
    candidate whose own embedded `..` segments walk past the root once
    joined). Against `tracked_set` an out-of-repo result is just another
    string that isn't in the set; the one place it touches disk,
    `check_file_refs.check`'s `known_untracked` test (#89), puts it
    through the same real-path confinement `check_links._target` uses, so
    it isn't a path traversal risk there either.
    """

    return normpath(join(dirname(citing), candidate))
