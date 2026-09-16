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

"""The `check-cli-flags` check (ticket #19).

Nothing today verifies a claimed CLI flag against a script's real, current
argument surface. `check-citations` verifies backticked symbol citations
against declared source history — a CLI flag isn't a language-level
declaration at all, entirely outside its vocabulary.

**Detection** requires both a script/command identifier and a flag-shaped
token (`--word` or `-x`) backticked in the same claim (this check reads
"claim" as "line", matching #17/#18's own per-line precedent) — either as
one full invocation in a single backtick span (`` `tools/warm_cache.py
--normalize` ``), or as two separate backticked mentions on the same line
("the `` `tools/warm_cache.py` `` script supports `` `--normalize` ``").
A bare, standalone flag mention with no script context is never a
candidate — there's no reliable way to know which of a project's possibly
several CLI entry points it refers to without the claim stating it, and no
external mapping is used to resolve that ambiguity (unlike #17/#18's
project-supplied mappings, which map a *name* to a *verification
location*; here the claim itself already carries everything needed once
both parts are present).

Every tracked `*.md` file is swept unconditionally, matching #16/#17/#18's
own "catches a claim that's false right now" precedent — narrowed only by
this check's own `exclude` glob list (same shape/coercion as every
sibling check's own `exclude`), for a directory of historical or
illustrative prose that was never meant to name real, currently-runnable
scripts. A candidate inside a fenced code block is skipped, same as
#16/#18's own `_fence_state` precedent — illustrative example content, not
a claim.

**A "script" is deliberately narrow: a path-shaped token ending in a
recognized script extension** (`.py`, `.sh`, `.rb`, `.js`, `.ts`, `.pl`).
A bare command name with no extension (`docker`, `npm`, `git`) is never
detected — a known, deliberate gap, not silently accepted: there's no
reliable way to distinguish a real CLI tool name from any other
backticked word without a vocabulary of known tools, and guessing wrong
would mean running an arbitrary backticked word as a command. The
narrower, extension-anchored shape is also what keeps this check's own
command construction safe: the character class a script token must match
(`[\\w.-]` plus `/`) contains no shell metacharacter, so appending
`--help` to it can never smuggle a chained or substituted command the way
a fully free-form claim could.

**Verification extracts the script, runs `<script> --help`, and checks
whether the claimed flag token appears in the combined stdout+stderr
text.** `--help` is the near-universal introspection convention across
CLI frameworks (`argparse`, `click`, `clap`, cobra, commander.js) — good
enough for v1; a project whose CLI uses a nonstandard help flag is a
documented limitation, not something made configurable now. A script
token with no directory separator (`manage.py`, `setup.py` — a common
repo-root-script shape) is run as `./{script}`, not the bare name: a bare
name is a `$PATH` lookup, not "the script this repo tracks," and would
otherwise either fail outright or silently run some unrelated same-named
binary. The grant is keyed on this same, already-`./`-prefixed command —
what a human approves in `claims.local.toml` is exactly what runs, never
a different string. Matching is a **word/hyphen-boundary-anchored**
search for the flag token in that output, not a bare substring — `-n`
must not "match" merely because it's a substring of a real `--normalize`
flag, and `--norm` must not match as a prefix of `--normalize` either;
both are real flags this check would otherwise wrongly confirm as
supported. Still no language-aware parsing of the output's own structure,
the same "near-exact" philosophy #17/#18 already use — just anchored
enough that a substring/prefix collision can't manufacture a false
"supported" verdict.

**A failed, errored, or timed-out `--help` invocation is inconclusive,
not confirmed-false** — mirrors `executable-claims`' own "a timeout means
the check never got an answer, not that the claim is false" precedent
exactly, including that it still produces its own (advisory) finding
rather than staying silent, the same way `executable-claims` surfaces its
own timeout. Only a clean run whose output doesn't contain the flag is a
"confirmed missing" finding.

**This is `claims`' second execution-capable check, alongside
`executable-claims` (#15)** — the exact trigger condition #15's own brief
named for generalizing its local-permission-gate mechanism rather than
keeping it bespoke. `claims/execution_grants.py` now holds that mechanism
once, keyed by whichever check calls it; see that module and
`executable_claims.py`'s own module docstring for the full security
reasoning (committed config can't be the trust boundary; a tracked grant
file must not be honored either). The grant is keyed on the **exact
command this check will actually run** (`<script> --help`), not the bare
script name alone — auditable and consistent with `executable-claims`'
own exact-string philosophy.

**Severity is advisory, explicitly provisional, same as #17/#18** — with
one deliberate exception: a *tracked* `claims.local.toml` (see
`execution_grants.local_grants`) still produces its own **gate** finding,
matching #15's own precedent. That one case is a security compromise
indicator regardless of this check's own otherwise-advisory severity
policy; every other finding this check produces (ungranted, denied,
flag-not-found, inconclusive) is advisory.

**Known, deliberate gap, not silently accepted:** verification
completeness, same risk class as #18 — a flag consumed only via a build
tool's own config, or a `--help` invocation that succeeds but doesn't
enumerate every flag the script actually accepts (some frameworks
truncate long help text, or require a subcommand first), could go
unfound through no fault of the claim itself. A related, permanent case
rather than an occasional miss: a CLI convention where `--help` itself
exits non-zero (some `docopt`-based tools do this) makes that script's
own claims inconclusive on every single run, re-nagging without ever
resolving — the escape hatch is `denied` (silences it, with a reason
recorded), not a fix. Revisit once real usage gives an actual
false-positive/false-negative rate to argue from.

**Known, accepted trait:** a script token may itself contain `../`
segments and resolve outside the repo (`SCRIPT_RE` only restricts the
*character set*, not the resolved location) — not treated as its own
gate, since the exact-string local grant is already the human checkpoint
this whole mechanism relies on: a project reviewing
`allowed = ["../../../tmp/evil.py --help"]` before adding it has the same
opportunity to notice the escape as it does for any other suspicious
grant.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from ..config import exclude_patterns, numeric_config, path_matches
from ..execution_grants import local_grants, toml_string
from ..git import tracked_files
from ..runner import Finding, register_check

NAME = "check-cli-flags"
TIMEOUT_SECONDS = 10

BACKTICK_RE = re.compile(r"`([^`\n]+)`")

SCRIPT_EXTENSIONS = (".py", ".sh", ".rb", ".js", ".ts", ".pl")
# `\Z`, not `$`: `$` matches just before a trailing `\n`, which `BACKTICK_RE`
# can never actually hand this pattern (it excludes `\n` from a span) — but
# a regex guarding what gets fed to `shell=True` shouldn't rely on that,
# it should just not have the loophole.
SCRIPT_RE = re.compile(
    r"^(?:[\w.-]+/)*[\w.-]+(?:" + "|".join(re.escape(e) for e in SCRIPT_EXTENSIONS) + r")\Z"
)
FLAG_RE = re.compile(r"^(?:--[A-Za-z][\w-]*|-[A-Za-z])\Z")

FENCE_RE = re.compile(r"^\s*(`{3,})")


def _fence_state(lines: Sequence[str]) -> list[bool]:
    """Whether each of `lines` should be excluded from detection because
    it's a fenced code block's own delimiter line or content — same
    nesting rule and delimiter-line handling as
    `check_file_refs._fence_state`/`check_env_vars._fence_state`; see
    either for the full reasoning, not repeated a third time here.
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


def _runnable(script: str) -> str:
    """`script` as something the shell can actually run from `repo_root`.

    A token with no `/` (`manage.py`, `setup.py`) is a `$PATH` lookup, not
    "the script this repo tracks" — run bare, it either fails outright or
    silently executes some unrelated same-named binary. `./`-prefixing it
    pins the lookup to the repo root, matching what a human reading the
    claim actually means. A token that already contains `/` is left
    alone — it may already be relative (`tools/warm_cache.py`) or, if a
    claim names one with a leading `../`, that's a separate, accepted
    trait named in the module docstring, not something to paper over here.
    """

    return script if "/" in script else f"./{script}"


def _read(path: Path) -> str | None:
    """A file's text, or `None` for a symlink, missing file, or unreadable
    path — mirrors every sibling check's own guard.
    """

    if path.is_symlink() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _candidates(line: str) -> set[tuple[str, str]]:
    """Every `(script, flag)` pairing this line's backtick spans imply —
    both the single-span-invocation shape and the two-separate-mentions
    shape (see module docstring). A `set`: the same pairing named twice
    (or implied both ways at once) is one candidate, not a duplicate
    finding.
    """

    spans = BACKTICK_RE.findall(line)
    found: set[tuple[str, str]] = set()

    for span in spans:
        tokens = span.split()
        if not tokens or not SCRIPT_RE.match(tokens[0]):
            continue
        for token in tokens[1:]:
            if FLAG_RE.match(token):
                found.add((tokens[0], token))

    scripts = [s for s in spans if SCRIPT_RE.match(s)]
    flags = [s for s in spans if FLAG_RE.match(s)]
    for script in scripts:
        for flag in flags:
            found.add((script, flag))

    return found


def _timeout(config: Mapping[str, object]) -> float:
    return numeric_config(config, NAME, "timeout", TIMEOUT_SECONDS, allow_float=True)


def _flag_supported(flag: str, output: str) -> bool:
    """Whether `flag` genuinely appears in `output`, not merely as a
    substring or prefix of some other, longer flag — a bare `flag in
    output` check would wrongly confirm `-n` as "supported" merely
    because it's a substring of a real `--normalize`, and `--norm` merely
    because it's a prefix of it. Anchored on both sides against `[\\w-]`
    (word characters or a hyphen), the same characters `FLAG_RE` itself
    allows a flag to contain, so a real boundary — punctuation, brackets,
    whitespace — is what has to appear around a genuine match.
    """

    pattern = rf"(?<![\w-]){re.escape(flag)}(?![\w-])"
    return re.search(pattern, output) is not None


def _finding(rel: str, line_no: int, message: str) -> Finding:
    return Finding(file=rel, line=line_no, message=message, mode=NAME, gate=False)


def _ungranted_message(command: str) -> str:
    literal = toml_string(command)
    return (
        f"`{command}` has no local grant in claims.local.toml — under "
        f"`[{NAME}]`, add {literal} to an existing `allowed` list or start "
        f"one with `allowed = [{literal}]`, or the same into `denied` to "
        "skip it and record that choice"
    )


def _help_outcome(
    command: str, repo_root: Path, timeout: float, cache: dict[str, tuple[str, str]]
) -> tuple[str, str]:
    """`(kind, detail)` for running `command` as this repo's `--help`
    invocation — `kind` is `"timeout"`, `"exit"` (`detail` the exit code
    as a string), or `"output"` (`detail` the combined stdout+stderr).
    Cached per exact `command` string across the whole `check()` run: two
    different claims (or the same claim on two different lines) naming
    the same script and flag must each still get their own finding, but
    there's no reason to actually re-run the same subprocess twice for it.
    """

    if command in cache:
        return cache[command]
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
        outcome = ("timeout", "")
    else:
        outcome = (
            ("exit", str(done.returncode))
            if done.returncode != 0
            else ("output", done.stdout + done.stderr)
        )
    cache[command] = outcome
    return outcome


def check(repo_root: Path, diff_range: str, config: Mapping[str, object]) -> list[Finding]:
    allowed, denied, grant_warning = local_grants(repo_root, NAME)
    findings: list[Finding] = []
    if grant_warning is not None:
        findings.append(grant_warning)

    timeout = _timeout(config)
    exclude = exclude_patterns(config)
    help_cache: dict[str, tuple[str, str]] = {}

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
            for script, flag in sorted(_candidates(line)):
                command = f"{_runnable(script)} --help"

                if command in denied:
                    findings.append(
                        _finding(
                            rel,
                            line_no,
                            f"`{command}` is denied in claims.local.toml — skipped",
                        )
                    )
                    continue
                if command not in allowed:
                    findings.append(_finding(rel, line_no, _ungranted_message(command)))
                    continue

                kind, detail = _help_outcome(command, repo_root, timeout, help_cache)
                if kind == "timeout":
                    findings.append(
                        _finding(
                            rel,
                            line_no,
                            f"`{command}` timed out after {timeout}s — could not be "
                            f"verified whether `{script}` supports `{flag}`",
                        )
                    )
                    continue
                if kind == "exit":
                    findings.append(
                        _finding(
                            rel,
                            line_no,
                            f"`{command}` exited {detail} — could not be verified "
                            f"whether `{script}` supports `{flag}`",
                        )
                    )
                    continue

                if _flag_supported(flag, detail):
                    continue
                findings.append(
                    _finding(
                        rel,
                        line_no,
                        f"`{script}` does not appear to support `{flag}` — "
                        f"`{command}` succeeded but didn't mention it",
                    )
                )

    return findings


register_check(NAME, check)
