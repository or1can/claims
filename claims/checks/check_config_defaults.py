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

"""The `check-config-defaults` check (ticket #17): a stated default value,
held to the line of code a project maps the setting to.
`docs/checks/check-config-defaults.md` is the account of what it reads,
the mapping's shape and what it misses; this docstring is why the code is
shaped the way it is.

Its own check because nothing else verifies a stated default *value*
against code: `check-citations` verifies a backticked symbol's
*existence* in history, never a claimed value; nothing else comes close.

**Detection is deliberately narrow** — a fixed phrase anchor *and* both
the setting's name and its stated value backticked — because requiring
the claim itself to state the exact value is what makes the rest of this
check honest: the precision requirement lives in how the claim is
written, not in the checker trying to bridge a prose-vs-code gap it can't
reliably close without real language-aware parsing. That same requirement
is what makes the near-exact comparison affordable — a bare substring
test against the mapped line's raw text, with no normalization applied to
the code side at all; a checker trying to bridge a looser claim's wording
against arbitrary code would need real parsing this check deliberately
doesn't attempt.

**Where to verify against is explicit, per project.** This check's own
`claims.toml` section is itself the setting-name → file:line mapping,
matching the same "project states what it means, we don't guess your
structure" philosophy `claim-words`'s `files` and `stale-claims`'s
`module_reference_scope` already use. A setting name with no mapping
entry produces no finding: out of scope, not flagged as broken. A
malformed mapping value raises `ConfigError`, surfacing as `runner.run`'s
own gate crash finding — the same treatment every other check's own
malformed config gets.

No command is ever executed here — pure file-read and text comparison,
deliberately, to avoid entangling this with #15's permission-gate work
(execution-based verification is `cli_command`'s own territory, #19).

Findings are advisory, explicitly provisional pending real false-positive
data from actual use — not a permanent severity choice.

**Known, deliberate gap, not silently accepted:** a mapped file:line can
drift out of sync with the actual code over time — the default moves to a
different line, the mapping isn't updated — silently making this check
less useful without any signal that it's happened. Keeping the mapping
itself honest (an AST-fingerprint or drift-detection mechanism) is a real,
named adjacent problem (`fiberplane/drift`'s own territory), not pursued
here; v1 is the mapping plus a text comparison, nothing more.

**Second known, deliberate gap:** "near-exact substring" cuts both ways —
`claimed in actual` isn't anchored, so a short or common claimed value can
pass against a mapped line that states something else entirely. A claim
of `` `TIMEOUT` defaults to `30` `` against code reading `TIMEOUT = 300`
is a false clean pass (`"30"` is a substring of `"300"`); a claimed value
that happens to equal the setting's own name passes unconditionally,
since the mapped line always contains its own name; a claimed empty
string (`` `` ``, stripped from `''`/`""`) matches anything, since `""` is
a substring of everything. Tightening this — anchoring on word/token
boundaries, rejecting an empty claimed value outright — is deliberately
left for real usage data to motivate, the same "provisional severity"
reasoning above; a claim precise enough to name an exact value is exactly
the shape this check is built to trust literally.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from ..config import ConfigError
from ..git import tracked_files
from ..runner import Finding, register_check

NAME = "check-config-defaults"

# Fixed, not project-configurable — widening this list trades detection
# precision for recall in a way the module docstring's "deliberately
# narrow" design explicitly rejects; a project wanting a phrase not listed
# here should backtick its claim differently, not reconfigure the check.
DEFAULT_PHRASES = ("defaults to", "default is", "defaulting to", "default:")
_PHRASE_PATTERN = "|".join(re.escape(p) for p in DEFAULT_PHRASES)

# Both the setting's name and its stated value must be backticked, in that
# order, with the phrase anchor between them, on the same line — no
# cross-line claims, matching how simple this check's own detection is
# meant to stay.
CLAIM_RE = re.compile(
    rf"`([^`\n]+)`\s*(?:{_PHRASE_PATTERN})\s*`([^`\n]+)`", re.IGNORECASE
)

QUOTE_CHARS = "'\""


def _strip_quotes(value: str) -> str:
    return value.strip().strip(QUOTE_CHARS)


def _parse_target(name: str, spec: object) -> tuple[str, int, int]:
    """`spec` — this check's own `claims.toml` mapping value for `name` —
    as `(path, start_line, end_line)`, both 1-based and inclusive; a
    single-line spec (`"src/config.py:42"`) has `start_line == end_line`.

    Raises `ConfigError` naming `name` for anything not shaped `path:line`
    or `path:start-end` — a mapping entry a project wrote is either usable
    or a config mistake worth a loud crash finding, never silently
    ignored.
    """

    if not isinstance(spec, str):
        raise ConfigError(f"[{NAME}] {name!r} target must be a string, got {spec!r}")
    path, sep, lines = spec.rpartition(":")
    if not sep:
        raise ConfigError(
            f"[{NAME}] {name!r} target {spec!r} must be shaped "
            "'path:line' or 'path:start-end'"
        )
    start_str, dash, end_str = lines.partition("-")
    try:
        start = int(start_str)
        # `if dash`, not `if end_str`: a trailing dash with nothing after
        # it (`"path:1-"`) must still attempt `int("")` and raise, rather
        # than silently falling back to `start` because `end_str` alone
        # happens to be falsy.
        end = int(end_str) if dash else start
    except ValueError:
        raise ConfigError(
            f"[{NAME}] {name!r} target {spec!r} must be shaped "
            "'path:line' or 'path:start-end'"
        ) from None
    if start < 1 or end < start:
        raise ConfigError(
            f"[{NAME}] {name!r} target {spec!r} must name 1-based lines "
            "with start <= end"
        )
    return path, start, end


def _targets(config: Mapping[str, object]) -> dict[str, tuple[str, int, int]]:
    """Every configured setting name's own `(path, start, end)` target —
    validated eagerly, all of them, at `check()` entry, not lazily only
    for a name some claim happens to mention: a malformed entry is a
    config mistake regardless of whether this run's tracked tree cites it.
    """

    # `enabled` is the hook's own per-check switch (see `hook.py`), shared
    # by every check and documented as such — the one key of this section
    # that is not a setting name, so it is set aside rather than parsed as
    # a target and crashed on.
    return {
        name: _parse_target(name, spec)
        for name, spec in config.items()
        if name != "enabled"
    }


def _read_lines(path: Path) -> list[str] | None:
    """A file's lines, or `None` for a symlink, missing file, or unreadable
    path — mirrors `check_links._read`/`check_file_refs._read`'s guard.
    """

    if path.is_symlink() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None


def _target_text(repo_root: Path, path: str, start: int, end: int) -> str | None:
    """The mapped line range's own raw text, or `None` if the file doesn't
    exist or the range selects nothing (e.g. the file has since shrunk
    below `start`) — both cases the same "target not found" fact to the
    caller, not distinguished further.
    """

    lines = _read_lines(repo_root / path)
    if lines is None:
        return None
    selected = lines[start - 1 : end]
    return "\n".join(selected) if selected else None


def _finding(rel: str, line_no: int, message: str) -> Finding:
    return Finding(file=rel, line=line_no, message=message, mode=NAME, gate=False)


def check(repo_root: Path, diff_range: str, config: Mapping[str, object]) -> list[Finding]:
    targets = _targets(config)
    findings: list[Finding] = []

    for rel in sorted(tracked_files(repo_root, "*.md")):
        lines = _read_lines(repo_root / rel)
        if lines is None:
            continue
        for line_no, line in enumerate(lines, 1):
            for match in CLAIM_RE.finditer(line):
                name = match.group(1).strip()
                target = targets.get(name)
                if target is None:
                    continue
                claimed = _strip_quotes(match.group(2))
                path, start, end = target
                actual = _target_text(repo_root, path, start, end)
                if actual is not None and claimed in actual:
                    continue
                location = f"{path}:{start}" if start == end else f"{path}:{start}-{end}"
                found = "nothing (file or line range not found)" if actual is None else actual.strip()
                findings.append(
                    _finding(
                        rel,
                        line_no,
                        f"`{name}` claims default `{claimed}`, but {location} "
                        f"does not contain it — found: {found!r}",
                    )
                )

    return findings


register_check(NAME, check)
