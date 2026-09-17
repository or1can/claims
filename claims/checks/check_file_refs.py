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

"""The `check-file-refs` check (ticket #16).

`stale-claims` already scans prose for path-shaped text (its own `PATH_RE`)
but only *keeps* a match that resolves to a tracked file — a match that
doesn't resolve is silently dropped, never reported anywhere. `check-links`
only validates real Markdown link syntax (`[text](path)`); a bare,
unmarked prose mention of a path is outside its regex entirely. Nothing
today reports "this prose names a file that isn't there" for that bare
case, which this check exists to close.

Registered as a **gate** check, matching `check-links`' own "does this
reference resolve" precedent — safe here specifically because the
extension check below is tightened, unlike `stale-claims`' own untightened
pattern (see below).

Sweeps every tracked `*.md` file unconditionally, not diff-scoped —
matching `check-links`/`stale-claims`/`executable-claims`'s "catches a
claim that's false right now" precedent, not `claim-words`/`restatement`'s
diff-scoped one.

A candidate is checked two ways before being reported: first as
repo-root-relative (`tracked_set` membership directly), then, only if that
fails to resolve, against the *citing file's own directory*
(`_citing_relative`, the same `dirname`/`join`/`normpath` approach
`check_links._resolve` already uses for a real Markdown link's own
destination) — ticket #32. A per-module or per-skill `references/*.md`
layout, cited from its own sibling doc as a bare `references/foo.md`,
resolves this way even though it was never a real path from the repo
root. A candidate with a leading `../` never reaches this fallback at
all — `_repo_relative` already ruled it out as not a candidate, unchanged
by this ticket (see its own docstring below). This does trade away some
precision for recall (CLAUDE.md's own stated preference): a genuinely
broken repo-root-relative reference now resolves silently instead of
being flagged, if a same-named file happens to also sit somewhere under
the citing file's own directory — accepted as the same "a missed claim
stays invisible forever" tradeoff, not an oversight.

Neither of those two resolution attempts helps a candidate that's real on
disk but deliberately never `git add`ed — a project's own gitignored,
per-machine file (`.claude/settings.local.json`, the same shape
`claims.local.toml` itself is) is indistinguishable from an outright typo
to `tracked_set` membership alone. A candidate matching this check's own
`known_untracked` glob list (`claims.toml`, same shape as `exclude`) is
exempted from that requirement — but still has to resolve to a real file
*inside the repo* (`Path.resolve()` confined via `is_relative_to`, the
same guard `check_links._target_slugs` already uses for the identical
reason: a lexical check alone would miss a symlink, and a candidate's own
embedded `..` isn't rejected the way a *leading* `../` is by
`_repo_relative`), so a genuine typo under an exempted pattern is still
caught, and a `known_untracked` pattern can't be walked outside the repo
via `../` or followed outside it via a symlink (ticket #33). A real
symlink pointing outside the repo (a `.claude/settings.local.json`
symlinked into a separate dotfiles checkout, say) is refused by this same
guard, not silently followed — stricter than this file's own `_read`
(which refuses *any* symlink outright), but consistent with
`check_links`' own choice to follow a symlink as long as where it leads
is still confined. Deliberately not real
`.gitignore`-status detection (`git check-ignore` or equivalent) — that
would conflate "gitignored" with "deliberately documented as untracked"
(a project can gitignore something for an unrelated reason, or leave
something untracked without gitignoring it at all) and adds a git
dependency this config-only approach doesn't need. Only ever checked
against the repo-root-relative candidate, not the citing-relative one
above — a gitignored file cited relative to the citing file's own
directory is `#32`'s and this ticket's shared, named, independently
shippable gap, not silently accepted as solved.

**The extension-tightening fix.** `stale-claims`' `PATH_RE` accepts any
alphanumeric run as a "extension" (`\\.[A-Za-z0-9]+`), which is harmless
for `stale-claims` (a false match just fails to resolve and silently drops
out of its ranking) but would not be harmless for a check whose entire job
is "reports when a match doesn't resolve": confirmed empirically that
`api/v2.0` and `getting-started/v1.2` both match that pattern, a trailing
`.0`/`.2` satisfying it same as a real extension would. This check reuses
the same path shape but only treats a match as a candidate at all when its
trailing extension is in a **recognized set** (`DEFAULT_EXTENSIONS`,
extendable per project via this check's own `extensions` config key —
additive, mirroring `restatement.extensions`' own behavior, not a
replacement for the built-in set). A version-number lookalike's `.0`/`.2`
"extension" isn't in that set, so it's never a candidate in the first
place — not flagged, not silently "maybe".

A mention already inside real Markdown link syntax (`[text](path)`) is
excluded from detection entirely — checked against the destination span a
`check-links`-shaped regex would itself validate, so a single broken
reference doesn't produce two separate gate findings from two different
checks under two different names. **Known, deliberate gap, not silently
accepted:** `check-links` itself only validates a destination naming
another `.md` file (with or without `#anchor`) or a bare `#anchor` — a
markdown-link destination naming some other recognized extension (e.g.
`[the script](scripts/foo.py)`, where `foo.py` doesn't exist) is excluded
from this check by the same "already inside link syntax" rule, but isn't
in `check-links`' own scope either, so a broken reference of that
particular shape currently goes unflagged by both checks. Narrowing this
would mean either broadening `check-links`' own scope past `.md`/anchors,
or excluding only the subset of link destinations `check-links` actually
validates — either is a bigger change than this ticket's own scope, so the
gap is named here rather than silently accepted.

**Known, deliberate gap shared with the out-of-scope list below:** a bare
filename with no directory separator (e.g. "see README") is not detected
at all — `PATH_RE` requires at least one `segment/` before the final
`segment.ext`, the same shape `stale-claims`' own bare-citation scoping
problem (`module_reference_scope`) already had to solve once for exactly
this false-positive-collision-with-ordinary-English-words risk; deserves
its own dedicated pass rather than folding in here.

**Known, deliberate gap:** `URL_RE` (below) only recognizes a URL with an
explicit `scheme://` — a scheme-less mention (`www.example.com/x.sh`)
isn't excluded, and unlike `check_links.py`'s own identical `SCHEME_RE`
blind spot (where a scheme-less host just falls outside that check's own
relevance filter), here it becomes a gate finding rather than merely
being skipped. Not solved here: recognizing a bare domain reliably
without a real URL grammar risks its own false-positive/negative
tradeoffs of a different kind, disproportionate for a shape rare enough
in practice. (A *protocol-relative* URL, `//cdn.example.com/x.js`, isn't
part of this gap — `_host_relative` below treats its leading `//` the
same as any other unconsumed `/`, so it's skipped as not a candidate
rather than becoming a false gate finding.)

An unconsumed leading `/` immediately before a match — `/` isn't in
`PATH_RE`'s own character class, so a match starts right after it with no
trace of it left in the captured text, and by the time `_repo_relative`
would see the plain candidate string the leading `/` is already gone —
is never treated as a repo-relative candidate (`_host_relative`, ticket
#38). This is what makes a host-absolute path (`/etc/docker/
daemon.json`) and a home-directory shorthand (`~/.docker/config.json` —
the `~` itself never survives into any match either way; it's the `/`
right after it doing the work here) both resolve correctly as "not a
repo-relative claim at all," the same "recognized as clearly-not-a-
candidate, skipped rather than resolved against the wrong base"
treatment `_repo_relative`'s own leading `../` handling already gets,
just checked at the call site instead of inside that function, since
`_repo_relative` only ever sees the stripped candidate string, not the
source line or the match's own position. **Known, deliberate gap this
also creates:** a genuinely broken *repo-root-anchored* mention written
Markdown-link-style (`/docs/agents/nonexistent.md`, the same leading-`/`
convention `check-links` uses for its own destinations) is now silently
skipped here too, rather than flagged — bare prose gives no reliable way
to tell "this leading `/` means host-absolute" from "this leading `/`
means repo-root," and #38's own motivating reports were all the
host-absolute shape, so that's the interpretation this check makes;
`check-links` keeps its own, different interpretation for real link
syntax, unaffected by this. `stale_claims.PATH_RE` and `check_links.py`'s
own destination resolution both share the same underlying blind spot in
their own copies — named in `TODO.md`, not fixed here.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from posixpath import dirname, join, normpath

from ..config import exclude_patterns, path_matches, string_list_config
from ..git import tracked_files
from ..runner import Finding, register_check

NAME = "check-file-refs"

# Same shape as `stale_claims.PATH_RE`, with one fix: a leading `\b` word
# boundary never matches between two non-word characters, so it silently
# drops the leading dot of a real hidden-directory path (a space then
# `.claude-plugin/plugin.json` — `\b` can't fire before the `.`, only
# before the `c` after it — reporting `claude-plugin/plugin.json` instead
# of the real path, which then never resolves). `stale-claims`' own copy
# has the same defect (noted in `TODO.md`) but it's harmless there — a
# wrong match just fails to resolve and drops out of its ranking, not true
# here. Replacing the leading `\b` with a negative lookbehind for "already
# inside a longer run of path-shaped characters" fixes it: it matches
# equally well before a word character or a literal leading dot, as long
# as neither is itself preceded by another path character.
#
# That same lookbehind also now captures a leading `./`/`../` whole
# (rather than `\b` incidentally skipping past it to start the match at
# the first real path segment) — `_repo_relative` below is what turns a
# captured `./x` back into the bare `x` a real check-out's `tracked_set`
# actually contains, and drops a `../x` match entirely rather than
# resolve it wrong.
PATH_RE = re.compile(r"(?<![\w.-])(?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]+\b")

# A destination inside real Markdown link syntax — reused only to find
# spans to *exclude* from this check's own detection, not to validate
# anything itself (that's `check_links.py`'s own job).
LINK_RE = re.compile(r"\]\(([^)]*)\)")

# A URL a path-shaped match might sit inside (`https://example.com/x.sh`) —
# `example.com/x.sh` alone is indistinguishable from a real relative path
# to `PATH_RE`, the same false-positive class `check_links.py`'s own
# `SCHEME_RE` exists to exclude from link-target checking.
URL_RE = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://\S+")

DEFAULT_EXTENSIONS = (
    ".py", ".rs", ".go", ".js", ".ts", ".rb", ".java", ".c", ".h", ".cpp",
    ".swift", ".sh", ".md", ".txt", ".yml", ".yaml", ".json", ".toml",
)


def _known_untracked(config: Mapping[str, object]) -> Sequence[str]:
    """This check's own `known_untracked` glob list (ticket #33) — same
    shape/coercion as `exclude` (`string_list_config`), but matched the
    opposite way: a candidate matching one of these patterns is exempted
    from the git-tracked-set requirement, not skipped outright like
    `exclude`. It still has to resolve to a real file confined to the repo
    (see `check()`'s own use of this list) — this names "deliberately
    untracked", not "never verify at all".
    """

    return string_list_config(config, "known_untracked")


def _extensions(config: Mapping[str, object]) -> tuple[str, ...]:
    """This check's own recognized-extension set — the built-in
    `DEFAULT_EXTENSIONS` plus a project's own `extensions` config,
    additive (mirroring `restatement.extensions`'s own behavior): a
    project adds a language/format its own docs reference, it never loses
    the built-in set by naming its own.
    """

    return DEFAULT_EXTENSIONS + tuple(string_list_config(config, "extensions"))


def _read(path: Path) -> str | None:
    """A file's text, or `None` for a symlink, missing file, or unreadable
    path — mirrors `check_links._read`/`check_citations._read_tracked`'s
    guard.
    """

    if path.is_symlink() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _excluded_spans(line: str) -> list[tuple[int, int]]:
    """Character ranges on `line` a path-shaped match must not start
    inside: a real Markdown link's own destination (`check_links.py`'s
    job to validate, not this check's), and a URL (not a relative path at
    all, however path-shaped its own trailing segment looks).
    """

    return [m.span(1) for m in LINK_RE.finditer(line)] + [
        m.span() for m in URL_RE.finditer(line)
    ]


def _excluded(start: int, spans: Sequence[tuple[int, int]]) -> bool:
    return any(span_start <= start < span_end for span_start, span_end in spans)


def _host_relative(line: str, start: int) -> bool:
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

    Neither shape is ever a repo-relative candidate, exactly like a
    leading `../` (ticket #38): unlike `../`, which `_repo_relative`
    already rejects because those two characters survive as part of the
    match itself, an unconsumed `/` is invisible to it by the time it
    receives the plain candidate string — so this has to be checked here,
    against the source line, at the one point that still has both `line`
    and the match's own start position in scope.
    """

    return start > 0 and line[start - 1] == "/"


def _repo_relative(candidate: str) -> str | None:
    """`candidate`, as written in prose, resolved to the repo-root-relative
    form `tracked_set` actually contains — or `None` if it can't be,
    without guessing.

    A leading `./` unambiguously means "from here" the same way it does
    in a shell command; stripped, since `tracked_set` never contains an
    entry with a `./` prefix of its own. A leading `../` is left alone —
    treated as not a candidate at all, never even reaching `check()`'s own
    citing-relative fallback below (`_citing_relative`, ticket #32) —
    deliberately, not because that fallback couldn't resolve it: extending
    `../` handling into that fallback was explicitly out of #32's own
    scope (a `../`-prefixed mention is common enough, and its correct
    resolution unambiguous enough, that it deserves its own dedicated
    pass rather than folding in here as a side effect).
    """

    if candidate.startswith("../"):
        return None
    if candidate.startswith("./"):
        return candidate[2:]
    return candidate


def _citing_relative(citing: str, candidate: str) -> str:
    """`candidate` resolved against `citing`'s own directory, as a
    repo-relative POSIX path — the same lexical join/normalize
    `check_links._resolve` already does for a real Markdown link's
    destination, applied here as a second try once `candidate` has
    already failed to resolve as repo-root-relative (ticket #32).

    Purely lexical, same as its model — may land outside the repo (e.g. a
    non-`../`-prefixed candidate whose own embedded `..` segments walk
    past the root once joined). Unlike `check_links._resolve`, whose
    result is opened and so needs `_target_slugs`' own real-path
    confinement, this result is only ever tested against `tracked_set`
    membership — nothing ever reads it, so an out-of-repo result is just
    another string that isn't in the set, not a path traversal risk.
    """

    return normpath(join(dirname(citing), candidate))


FENCE_RE = re.compile(r"^\s*(`{3,})")


def _fence_state(lines: Sequence[str]) -> list[bool]:
    """Whether each of `lines` should be excluded from detection because
    it's a fenced code block's own delimiter line or content.

    Same nesting rule as `executable_claims._fence_state` (a fence only
    closes on a same-or-longer run of backticks) — reused here so example
    code inside a fence (illustrative, not a claim that a named path is a
    real tracked file) isn't treated as a candidate at all. Unlike that
    function, this doesn't need to distinguish "the opening delimiter
    line" from "content" — a delimiter line's own info string (` ```json
    title="config/app.json" `, a real Docusaurus/MkDocs convention) is
    itself excluded too, not just the lines between the delimiters, so a
    fence-opener's own trailing text is never scanned either.

    A fence that's opened but never closed silences every line after it
    for the rest of the file — deliberately not treated as its own
    failure case here (unlike `executable_claims`'s own dangling-fence
    gate finding, which exists because a marker could be trapped inside
    one): `executable-claims` already reports that over the same tracked
    `*.md` sweep, so relying on it rather than duplicating the check is a
    real cross-check dependency, not an oversight — it only lapses if a
    project's `[executable-claims]` and `[check-file-refs]` `exclude`
    lists ever name different files for the same fence.
    """

    in_fence: list[bool] = []
    open_fence: int | None = None
    for line in lines:
        match = FENCE_RE.match(line)
        if match and (open_fence is None or len(match.group(1)) >= open_fence):
            open_fence = None if open_fence is not None else len(match.group(1))
            in_fence.append(True)
            continue
        in_fence.append(open_fence is not None)
    return in_fence


def _finding(rel: str, line_no: int, candidate: str) -> Finding:
    return Finding(
        file=rel,
        line=line_no,
        message=f"`{candidate}` does not resolve to a tracked file",
        mode=NAME,
        gate=True,
    )


def check(repo_root: Path, diff_range: str, config: Mapping[str, object]) -> list[Finding]:
    exclude = exclude_patterns(config)
    extensions = _extensions(config)
    known_untracked = _known_untracked(config)
    tracked_set = set(tracked_files(repo_root))
    repo_real = repo_root.resolve()
    findings: list[Finding] = []

    for rel in sorted(tracked_files(repo_root, "*.md")):
        if path_matches(rel, exclude):
            continue
        text = _read(repo_root / rel)
        if text is None:
            continue
        lines = text.splitlines()
        in_fence = _fence_state(lines)
        for line_no, line in enumerate(lines, 1):
            if in_fence[line_no - 1]:
                continue
            excluded = _excluded_spans(line)
            for match in PATH_RE.finditer(line):
                raw = match.group(0)
                if not raw.endswith(extensions):
                    continue
                if _excluded(match.start(), excluded):
                    continue
                if _host_relative(line, match.start()):
                    continue
                candidate = _repo_relative(raw)
                if candidate is None:
                    continue
                if candidate in tracked_set or _citing_relative(rel, candidate) in tracked_set:
                    continue
                if path_matches(candidate, known_untracked):
                    real = (repo_root / candidate).resolve()
                    if real.is_relative_to(repo_real) and real.is_file():
                        continue
                findings.append(_finding(rel, line_no, raw))

    return findings


register_check(NAME, check)
