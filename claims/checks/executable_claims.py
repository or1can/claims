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

Before a live marker's command ever runs, it's checked against a fixed
blocklist — no `claims.toml` entry required, since this is true of *any*
project using the marker mechanism, not just one project's own naming
(ticket #11): a chaining/backgrounding operator (`;`, `&&`, `||`, `&`), a
redirect (`>`, `>>`, `<`, `<<`, `>&`, `<&` — a marker reading or writing an
arbitrary file is exactly the "more than the one thing pinned" this exists
to stop, not merely a chained command), or a command substitution
(`` ` ``, `$(`) lets a marker do more than the one thing being pinned, and
`sed`/`awk`/`grep` turn a marker into inline text logic that only ever
exists as a string in an HTML comment, with nothing able to unit-test it.
`tail`/`head` are deliberately not in this blocklist: trimming a suite's
last line or two is still the one thing being pinned, not extra untested
logic.

Quoting is respected two different ways, matching what the shell itself
does with each construct, not one blanket "ignore anything quoted" rule:

- An operator/pipe token is only real when the shell would treat it as
  one — `shlex`, in punctuation-aware mode (a stronger setting than
  `claims/hook.py`'s own `_is_git_commit` uses, which needs only
  whitespace/quote-aware splitting, not operator boundaries), tokenizes
  the command respecting quotes first, so a `;` sitting inside a quoted
  Python one-liner's own source, or a pipe inside a quoted regex
  alternation (`grep -E 'a|b'`), is part of one word token, never mistaken
  for a real chain or pipeline boundary. This also closes a quoted-name
  dodge naive splitting wouldn't: `` 'grep' ``/`` g'r'ep `` both still
  tokenize down to the bare word `grep`. A pipe segment's head is checked
  past a `(`/`)` subshell wrapper too, so `| (grep pattern)` doesn't dodge
  it either — and `|&` (bash's combined stdout+stderr pipe) is treated as
  the same kind of boundary as `|`, not missed as an unrecognized word. A backslash-escaped operator (`find ... -exec ... \\;`) is
  neutralized before tokenizing — replaced with a placeholder, not its own
  bare character, so it can't still tokenize as a real operator — but an
  escaped ordinary character (`` \\grep ``, a common way to bypass a shell
  alias of the same name) keeps its own identity, or `grep` piped through
  that way would silently stop matching `TEXT_PROCESSING_TOOLS`. Unlike
  `claims/hook.py`'s `_is_git_commit` — where "can't parse it" safely
  means "assume the risky case, keep gating" — unparseable input here
  (unbalanced quotes) is itself the rejection reason: this check's whole
  job is deciding whether a command is safe to run, so failing open on
  "couldn't tell" would be backwards.
- A command substitution is checked differently, because quoting doesn't
  neutralize it the same way: single quotes fully suppress `` ` ``/`$(`,
  but *double* quotes don't — `` echo "$(cat secrets)" `` still expands.
  So this half walks `command` tracking single-/double-quote state itself
  rather than reusing the tokenizer above, and only treats a `` ` ``/`$(`
  found while inside single quotes as inert. It never fails to run the way
  tokenizing can — there's no rejected-input case to fall back from.

A project may additionally narrow *which* commands a marker may name at
all — "only our own test suites, or a script under our own scripts
directory" — via this check's own `permitted_prefixes` list in
`claims.toml`: a literal string prefix (`command.startswith(...)`, no glob
expansion the way `exclude`'s globs get, and no word-boundary check after
the prefix — `permitted_prefixes = ["npm test"]` also permits
`npm test-anything-else`, so a project wanting an exact match includes its
own trailing boundary, e.g. `"npm test "`). The check has no way to know a
project's own suite-invocation or script-layout conventions, so this stays
opt-in: absent means the blocklist above is the only content check.

A command failing either check is reported as a gate finding and never
runs — the same failure class as a marker that isn't above a fenced block,
not a new one; content unfit to run isn't a different kind of malformed
from a marker that isn't there at all.

**Known, deliberate gaps, not silently accepted ones:** a tool named via a
wrapper or full path (`env grep`, `/usr/bin/sed`) evades the text-processing
blocklist, matching only the bare names `sed`/`awk`/`grep` — chasing every
way to spell "run grep" is an arms race against a heuristic meant to catch
plain, unobfuscated smuggling, not deliberate evasion. The substitution
scan matches `$(` literally, so `$((arithmetic))` (which expands nothing
external) is rejected too, the same as a real substitution — narrowing
that would mean parsing enough of the shell's own grammar to tell the two
apart, disproportionate for what a marker doing arithmetic can just as
well express as its own already-computed value.
"""

from __future__ import annotations

import re
import shlex
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from ..config import exclude_patterns, numeric_config, path_matches, string_list_config
from ..git import tracked_files
from ..runner import Finding, register_check

NAME = "executable-claims"
TIMEOUT_SECONDS = 30

MARKER_RE = re.compile(r"^\s*<!--\s*verify:\s*(.+?)\s*-->\s*$")
FENCE_RE = re.compile(r"^\s*(`{3,})")
PROMPT_RE = re.compile(r"^\s*\$ ")

# No config surface: true of any project using the marker mechanism, not
# just one project's own naming — see the module docstring.
CHAIN_OPERATOR_TOKENS = frozenset({";", "&&", "||", "&"})
REDIRECTION_TOKENS = frozenset({">", ">>", "<", "<<", ">&", "<&"})
TEXT_PROCESSING_TOOLS = frozenset({"sed", "awk", "grep"})

ESCAPED_CHAR_RE = re.compile(r"\\(.)")
# Escaping one of these strips its operator meaning — replaced with a
# placeholder rather than the bare character, so it can't tokenize as a
# real operator either. Escaping any other character is just the shell's
# own way of spelling that character literally (`\grep` runs `grep`,
# bypassing a shell alias/function of the same name) — kept as-is, or a
# tool name's own identity would be corrupted into something that no
# longer matches `TEXT_PROCESSING_TOOLS` at all.
NEUTRALIZED_WHEN_ESCAPED = frozenset(";&|`$")


def _shell_tokens(command: str) -> list[str] | None:
    """`command` split the way a shell would — respecting quotes — with an
    escaped operator character neutralized first, so `find ... -exec ...
    \\;`'s own escaped terminator doesn't tokenize identically to a real
    chain operator. `None` when `command` doesn't tokenize at all (e.g.
    unbalanced quotes).
    """

    neutralized = ESCAPED_CHAR_RE.sub(
        lambda m: "Q" if m.group(1) in NEUTRALIZED_WHEN_ESCAPED else m.group(1), command
    )
    lexer = shlex.shlex(neutralized, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def _substitutes_a_command(command: str) -> bool:
    """Whether `command` contains a command substitution (`` ` `` / `$(`)
    outside of single quotes. Double quotes don't suppress substitution
    the way single quotes do (`` echo "$(cat secrets)" `` still expands),
    so this walks `command` character by character tracking quote state
    itself, rather than a regex pairing-up quote characters — a
    `'[^']*'`-style regex mispairs on the three-quote cluster a
    shell-quoted argument containing its own `'` produces (`shlex.quote`'s
    `'"'"'` escaping, which any of this check's own Python-one-liner test
    fixtures trips), leaving real content between two of those quotes
    unmatched and exposed as if it were unquoted.
    """

    in_single = False
    in_double = False
    i = 0
    while i < len(command):
        c = command[i]
        if in_single:
            if c == "'":
                in_single = False
            i += 1
            continue
        if in_double:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                in_double = False
                i += 1
                continue
        else:
            if c == "\\":
                i += 2
                continue
            if c == "'":
                in_single = True
                i += 1
                continue
            if c == '"':
                in_double = True
                i += 1
                continue
        if c == "`" or (c == "$" and command[i + 1 : i + 2] == "("):
            return True
        i += 1
    return False


def _forbidden_construct(command: str) -> str | None:
    """Why `command` may not run as a marker, or `None` if it's fine."""

    if _substitutes_a_command(command):
        return "substitutes a command (`` ` `` or `$(`) — a marker may only pin one command"

    tokens = _shell_tokens(command)
    if tokens is None:
        return "could not be parsed as a shell command"
    for token in tokens:
        if token in CHAIN_OPERATOR_TOKENS:
            return f"chains commands via `{token}` — a marker may only pin one command"
        if token in REDIRECTION_TOKENS:
            return (
                f"redirects file I/O via `{token}` — a marker may only pin one "
                "command's own output, not read or write an arbitrary file"
            )

    segment: list[str] = []
    for token in [*tokens, "|"]:
        if token not in ("|", "|&"):
            segment.append(token)
            continue
        # A leading `(`/`)` subshell wrapper (`(grep pattern)`) still runs
        # the wrapped command; stripped so the segment's real head is what
        # gets checked, not the parenthesis around it.
        head = next((t for t in segment if t not in ("(", ")")), None)
        if head in TEXT_PROCESSING_TOOLS:
            return (
                f"pipes through `{head}` — text-processing logic must live in a "
                "testable script, not a marker"
            )
        segment = []
    return None


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


def _permitted_prefixes(config: Mapping[str, object]) -> Sequence[str]:
    """This check's own `permitted_prefixes`, from its `claims.toml`
    section — empty (no additional restriction) when unset. See the
    module docstring: this narrows *which* commands a marker may name,
    layered on top of the fixed blocklist, not a replacement for it.
    """

    return string_list_config(config, "permitted_prefixes")


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
    permitted_prefixes = _permitted_prefixes(config)
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
            reason = _forbidden_construct(command)
            if reason is None and permitted_prefixes and not any(
                command.startswith(prefix) for prefix in permitted_prefixes
            ):
                reason = "does not match a configured permitted_prefixes entry"
            if reason is not None:
                findings.append(_finding(rel, line_no, f"`{command}` {reason}"))
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
