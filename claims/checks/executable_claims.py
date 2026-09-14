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

"""The `executable-claims` check.

A `<!-- verify: cmd -->` marker directly above a fenced block runs `cmd`
through the shell and diffs its combined stdout+stderr, and its exit code,
against the block. Registered as a **gate** check — see spec.md's check
inventory — except a `cmd` that exceeds its timeout (`TIMEOUT_SECONDS`,
overridable via this check's `claims.toml` `timeout` key): that's reported
advisory, not gate, since a timeout means the check never got an answer,
not that the claim was proven false.

The command runs through a shell rather than `shlex.split`, so a marker
needing a pipe works; that also means it runs exactly what it says, with the
same trust boundary as running the repo's own tests.

Not diff-scoped: every tracked `*.md` file is swept, matching the check's
job of catching a claim that's false right now, not just one a diff just
introduced.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from ..config import exclude_patterns, numeric_config, path_matches
from ..git import tracked_files
from ..runner import Finding, register_check

NAME = "executable-claims"
TIMEOUT_SECONDS = 30

MARKER_RE = re.compile(r"^\s*<!--\s*verify:\s*(.+?)\s*-->\s*$")
FENCE_RE = re.compile(r"^\s*(`{3,})")
PROMPT_RE = re.compile(r"^\s*\$ ")


def _fence_state(lines: Sequence[str]) -> tuple[list[bool], int | None]:
    """`(in_fence, dangling_open_line)` for `lines`.

    `in_fence[i]` is `True` when line `i` sits inside a still-open fence —
    including a fence-looking line whose backtick run is *shorter* than
    the one it's nested inside, which CommonMark treats as literal content
    rather than a real delimiter. That's the documented way to show a
    fenced-code example inside a fence, using a longer outer delimiter —
    exactly this check's own "marker syntax" documentation case, so a
    plain "any 3+ backticks toggles it" parity count would misread the
    inner example's own closing fence as closing the outer one instead,
    one nesting level deeper than `_blocks()` alone accounts for.

    `dangling_open_line` is the 1-based line of a fence still open at EOF
    (also detected this way — nothing before EOF closed it with a
    long-enough run), or `None`.

    Deliberately accepted narrowing: a stray, self-closed fence pair with
    nothing but a real marker inside it looks structurally identical to a
    genuine nested documentation example — both are "a fence opened, then
    closed, around some lines" — so a marker caught in one is silently
    treated as not-live, the same as this function's own intended case,
    with no way to tell accidental pairing from deliberate nesting short
    of guessing at the author's intent. Not treated as a dangling fence
    either, since nothing about it is left open. Rare enough (an isolated,
    self-contained stray pair immediately around an otherwise-unrelated
    marker) not to be worth a heuristic that would only be guessing.
    """

    in_fence: list[bool] = []
    open_fence: tuple[int, int] | None = None  # (backtick count, 1-based line)
    for i, line in enumerate(lines):
        match = FENCE_RE.match(line)
        if match and (open_fence is None or len(match.group(1)) >= open_fence[0]):
            open_fence = None if open_fence is not None else (len(match.group(1)), i + 1)
            in_fence.append(False)
            continue
        in_fence.append(open_fence is not None)
    return in_fence, open_fence[1] if open_fence is not None else None


def _blocks(lines: Sequence[str], in_fence: Sequence[bool]):
    """Yields `(line_no, command, expected_lines)` for every live marker in `lines`.

    `in_fence` is `_fence_state(lines)`'s own array — computed once by
    `check()` and shared with its dangling-fence check, rather than each
    re-deriving it from `lines`.

    A marker matched while already inside an open fence isn't live — shown
    as literal text in a documentation example of the marker syntax
    itself, not a real one — since a marker's contract is "directly above
    a fence," which a line already inside one can never satisfy. See
    `_fence_state()` for how "inside a fence" is decided.

    The same `in_fence` array also bounds a live marker's *own* expected
    block: reusing it (rather than stopping at the first `FENCE_RE` match
    after the opening fence) means a block legitimately containing a
    nested fenced example — showing this very marker syntax, say — is
    captured whole instead of truncated at that nested example's own
    first line.

    `expected_lines` is `None` when a live marker isn't followed (allowing
    blank lines) by a fenced block — a malformed marker.
    """

    for i, line in enumerate(lines):
        if in_fence[i]:
            continue
        marker = MARKER_RE.match(line)
        if not marker:
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines) or not FENCE_RE.match(lines[j]):
            yield i + 1, marker.group(1), None
            continue
        end = j + 1
        while end < len(lines) and in_fence[end]:
            end += 1
        yield i + 1, marker.group(1), lines[j + 1 : end]


def _dedent(lines: Sequence[str]) -> list[str]:
    body = [line for line in lines if line.strip()]
    common = min((len(l) - len(l.lstrip()) for l in body), default=0)
    return [line[common:] if line.strip() else line for line in lines]


def _trim(lines: Sequence[str]) -> str:
    return "\n".join(line.rstrip() for line in lines).strip("\n")


def _finding(file: str, line: int, message: str, *, gate: bool = True) -> Finding:
    return Finding(file=file, line=line, message=message, mode=NAME, gate=gate)


def _timeout(config: Mapping[str, object]) -> float:
    """This check's own `timeout` (seconds), from its `claims.toml` section —
    `TIMEOUT_SECONDS` when unset. No per-marker override: a marker line is
    already a verbatim shell command, and a second argument on it would need
    its own syntax and clash with a command that legitimately takes `--`
    itself; project-wide, alongside `exclude`, covers the motivating case
    (a slow integration or cold-build command) without that.
    """

    return numeric_config(config, NAME, "timeout", TIMEOUT_SECONDS, allow_float=True)


def check(
    repo_root: Path, diff_range: str, config: Mapping[str, object]
) -> list[Finding]:
    findings: list[Finding] = []
    checked = 0
    # A repo's CLAUDE.md is conventionally a symlink to AGENTS.md (both
    # tracked), so without this a marker in one would be swept, and any
    # failure reported, twice.
    seen: set[Path] = set()

    exclude = exclude_patterns(config)
    timeout = _timeout(config)
    tracked = tracked_files(repo_root, "*.md")
    # Keyed by real path, not name: naming just one alias of a symlinked
    # pair (this file's own CLAUDE.md/AGENTS.md convention, above) must
    # exclude the content under both, not leave it checked again — and
    # reported — under whichever alias wasn't named.
    excluded_reals = {
        (repo_root / rel).resolve() for rel in tracked if path_matches(rel, exclude)
    }

    swept_any = False
    for rel in tracked:
        real = (repo_root / rel).resolve()
        if real in excluded_reals:
            continue
        if real in seen:
            continue
        seen.add(real)
        swept_any = True
        lines = (repo_root / rel).read_text(encoding="utf-8").splitlines()
        in_fence, opened_at = _fence_state(lines)
        if opened_at is not None:
            findings.append(_finding(rel, opened_at, "fenced code block is never closed"))
        for line_no, command, expected in _blocks(lines, in_fence):
            if expected is None:
                findings.append(
                    _finding(rel, line_no, "verify marker is not above a fenced block")
                )
                continue
            checked += 1
            try:
                done = subprocess.run(
                    command,
                    shell=True,
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
            except subprocess.TimeoutExpired:
                # Advisory, not gate: a timeout means the check never got an
                # answer, not that the claim is proven false — a loaded
                # machine or a genuinely slow (cold-build, real-subprocess)
                # command shouldn't block a commit the same way a real
                # mismatch does.
                findings.append(
                    _finding(
                        rel,
                        line_no,
                        f"`{command}` timed out after {timeout}s",
                        gate=False,
                    )
                )
                continue
            if done.returncode != 0:
                findings.append(
                    _finding(rel, line_no, f"`{command}` exited {done.returncode}")
                )
                continue
            # Kept apart: concatenated, a stdout not ending in a newline
            # would weld its last line onto stderr's first and report the
            # seam as drift.
            actual = _trim(done.stdout.splitlines() + done.stderr.splitlines())
            want = _trim([l for l in _dedent(expected) if not PROMPT_RE.match(l)])
            if actual != want:
                findings.append(
                    _finding(
                        rel,
                        line_no,
                        f"output of `{command}` no longer matches the documented block",
                    )
                )

    # Suppressed only when exclusion is *why* nothing was swept at all:
    # something was swept, or nothing was excluded to begin with. A
    # project's `exclude` config choosing to skip the only file that would
    # otherwise have carried a marker is a deliberate opt-out, not the
    # "markers silently vanished" case this gate exists to catch. An
    # unrelated exclusion alongside a real, swept file that itself carries
    # no marker must still fire this gate as before — exclusion existing
    # at all can't be the guard, or a config excluding some unrelated path
    # would silently mask a marker that genuinely vanished elsewhere.
    if checked == 0 and not findings and (swept_any or not excluded_reals):
        findings.append(_finding(".", 0, "no verify markers found in repo"))

    return findings


register_check(NAME, check)
