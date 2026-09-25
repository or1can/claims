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

"""`PreToolUse` hook adapter. Narrowing to a `git commit` is split across
two layers, deliberately: the plugin manifest's own `"if": "Bash(git *)"`
does the coarse filter — command name only, not `"Bash(git commit *)"`,
because Claude Code's own documented `if`-matching (code.claude.com/docs/en/
hooks, "Bash if matching") runs the hook anyway on *any* command containing
a `$()`/backtick/`$VAR` substitution once the pattern names more than the
bare command name, defeating a `commit`-specific pattern for exactly the
agent-authored commands (heredocs, command substitutions) this hook most
needs to filter correctly. `_is_git_commit` below does the fine-grained
"is it specifically a commit" narrowing in Python instead, over whatever
`tool_input.command` the manifest already let through. `if` holds one
rule only, so the manifest repeats the same handler once per command
name `_is_git_commit` looks inside — `bash`, `sh`, `zsh` and `eval`
besides `git` (ticket #85) — or `bash -c "git commit"` would never reach
it. Each rule names the bare command, so `/bin/zsh -c`, which
`_is_git_commit` itself handles, never reaches it; and a command
matching two of them (`bash x.sh && git commit`) runs the hook twice,
each running every check and reaching the same decision.

Reads Claude Code's hook-event JSON from stdin and writes its hook-output
JSON to stdout: `permissionDecision: deny` with a human-readable reason on a
gate finding, `additionalContext` for advisory-only findings, or `{}` when
the command isn't a `git commit`, the hook is disabled, or there is nothing
to report. See code.claude.com/docs/en/hooks for the contract this speaks.

Besides the plugin-wide `[hook] enabled = false`, a single check can be
silenced from this decision alone via its own `enabled = false`
(`_disabled_checks`, ticket #44) — e.g. `[stale-claims]\nenabled = false`.
Both flags only ever affect *this* commit-time decision: `python3 -m
claims.cli` and the `check-claims` skill both call `run()` directly and
never read `[hook]` or a check's own `enabled` key at all, so a check
silenced here is still fully visible on demand through either of those.
A check's own `enabled` key sitting alongside its other config (`exclude`,
`module_reference_scope`, ...) isn't itself an unrecognized table (ticket
#21's own gate) — it's a key inside an already-recognized table, a
different, unrelated check.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

from . import checks  # noqa: F401
from .config import ConfigError, load_config
from .runner import Finding, run

HOOK_EVENT_NAME = "PreToolUse"

# Global git options taking a separate value token, so `commit` right
# after one of these (`git -C <path> commit`) is still the subcommand,
# not `<path>` itself. The full documented set from `git help git`'s
# OPTIONS section that take a value — verified empirically (`git
# --git-dir <path> ...`, `git --config-env foo.bar=VAR ...` both parse
# the next token as the value), except `--exec-path`, deliberately
# excluded: unlike the others, it's bare-or-`=path`-only (confirmed: `git
# --exec-path /some/path status` does not consume `/some/path` as a
# value at all — it's read as `--exec-path` bare, per its own docs, "if
# no path is given, git will print the current setting and exit").
_VALUE_TAKING_GIT_OPTIONS = {
    "-C",
    "-c",
    "--config-env",
    "--git-dir",
    "--work-tree",
    "--namespace",
    "--list-cmds",
    "--attr-source",
}


# Shells whose `-c` script is searched too, matched on the token's own
# basename so `/bin/sh -c` counts, and their options taking a separate
# value token, so that value isn't mistaken for the script.
_SHELLS = {"bash", "sh", "zsh"}
_VALUE_TAKING_SHELL_OPTIONS = {"-o", "+o", "-O", "+O"}


def _git_subcommand(tokens: list[str], git_index: int) -> str | None:
    """The subcommand the `git` token at `tokens[git_index]` runs, or
    `None` if nothing follows it.

    Skips global options right after `git` — including one extra token
    for a value-taking option's own value — so `commit` in subcommand
    position is found correctly regardless of how many global options
    precede it, without matching `commit` as merely some later argument's
    *value* (`git tag -m commit`, `git branch commit`) the way "any
    `commit` token anywhere after `git`" would.
    """

    i = git_index + 1
    while i < len(tokens) and tokens[i].startswith("-"):
        option = tokens[i]
        i += 1
        if option in _VALUE_TAKING_GIT_OPTIONS and "=" not in option:
            i += 1
    return tokens[i] if i < len(tokens) else None


def _shell_script(tokens: list[str], shell_index: int) -> str | None:
    """The script the shell at `tokens[shell_index]` runs via `-c`, or
    `None` if it isn't given one — `-c` alone or inside a cluster (`-lc`),
    after any other options, skipping the value of one taking its own
    (`bash -o pipefail -c ...`)."""

    i = shell_index + 1
    has_c = False
    while i < len(tokens) and tokens[i][:1] in ("-", "+"):
        option = tokens[i]
        i += 1
        if option in _VALUE_TAKING_SHELL_OPTIONS:
            i += 1
        elif option.startswith("-") and not option.startswith("--") and "c" in option:
            has_c = True
    return tokens[i] if has_c and i < len(tokens) else None


def _git_alias(repo_root: Path, name: str) -> str | None:
    """`alias.<name>`'s value as `repo_root`'s git config resolves it, or
    `None` if it has none."""

    result = subprocess.run(
        ["git", "-C", str(repo_root), "config", "--get", f"alias.{name}"],
        capture_output=True,
        text=True,
        errors="replace",
    )
    return result.stdout.rstrip("\n") if result.returncode == 0 else None


def _is_git_builtin(name: str) -> bool:
    """Whether `name` is one of git's built-in commands, which git runs in
    preference to an alias of the same name."""

    result = subprocess.run(
        ["git", "--list-cmds=builtins"], capture_output=True, text=True, errors="replace"
    )
    return name in result.stdout.split()


def _runs_commit(
    tokens: list[str], git_index: int, repo_root: Path, seen: frozenset[str]
) -> bool:
    """Whether the `git` at `tokens[git_index]` runs `commit`, directly or
    through an alias.

    An alias is searched as the command it expands to — `git <expansion>`,
    or a `!` alias's shell command as-is — so an alias of an alias
    resolves too. `seen` holds the aliases already expanded on the way
    here, so one that refers back to itself (`!git loop` as `alias.loop`)
    ends rather than recursing forever. An alias named after a built-in
    is skipped, as git itself ignores it; asked only once an alias is
    found, so a plain `git status` costs one `git config` call, not two.
    """

    subcommand = _git_subcommand(tokens, git_index)
    if subcommand == "commit":
        return True
    if subcommand is None or subcommand in seen:
        return False
    expansion = _git_alias(repo_root, subcommand)
    if expansion is None or _is_git_builtin(subcommand):
        return False
    inner = expansion[1:] if expansion.startswith("!") else f"git {expansion}"
    return _is_git_commit(inner, repo_root, seen | {subcommand})


def _is_git_commit(
    command: object, repo_root: Path, seen: frozenset[str] = frozenset()
) -> bool:
    """Whether `command`, tokenized, runs `git commit` anywhere in it.

    Checks every `git` token in the whole tokenized command, not just one
    scoped to a shell-operator-bounded segment: `shlex` gives no reliable
    way to find every real statement boundary (`&&`/`;`/`|`/bare `&`, and
    a literal newline in a multi-line script, all either need whitespace
    around them to tokenize as their own token, or don't tokenize as one
    at all) without a real shell parser, so a segment-bounded search
    missed a genuine `git commit` sitting after an un-spaced operator, on
    a later line of a multi-line command, or after a backgrounding `&` —
    each verified directly, each landing an unchecked commit. Erring
    toward finding `git commit` too often (`grep git commit file.txt`
    reads as one) rather than too rarely: a false positive here costs one
    extra, harmless check run; a false negative lets a commit land with
    every check silently skipped, the exact failure this file exists to
    prevent. `_git_subcommand` still requires `commit` to be `git`'s own
    subcommand, not merely a later argument's *value* (`git tag -m
    commit`, `git branch commit`) — so this isn't a bare substring match
    either, just not bounded to one segment.

    A `command` that isn't a string, or that `shlex` can't tokenize at all
    (unbalanced quotes), is treated as not-a-commit rather than raised or
    assumed live — the one case still erring toward not gating, since
    there's no token stream to search at all.

    A commit one level removed is searched for too, with these same
    rules (ticket #85): the script a `bash`/`sh`/`zsh` runs via `-c`
    (`_shell_script`), everything after an `eval`, and a git alias
    (`_runs_commit`) — including a `!` shell alias, whose command is
    searched like any other rather than left as a gap, since `!git add -A
    && git commit` is exactly the shape a commit-wrapping alias takes.

    Residual accepted gaps, in the *missed* direction this function
    otherwise avoids: a compact, no-space operator (`cd /tmp&&git
    commit`) merges into the adjacent token (`/tmp&&git`), so `git` never
    appears as a token to find at all. Idiomatic shell style (this
    plugin's own commits included) always spaces these; fixing it would
    mean pre-splitting the raw string on operator characters, which needs
    to respect quoting to avoid corrupting an argument that legitimately
    contains one (`git commit -m "a|b"`) — the same class of parsing
    hazard this file's diff-parsing sibling module (`claims/git.py`)
    exists to avoid, not worth reintroducing for a rare, unidiomatic
    input shape. Aliases are looked up in `repo_root`'s own config only,
    so one defined inline (`git -c alias.ci=commit ci`) or only in the
    config of another repository named by `-C` is missed; so is a script
    run by any other shell (`dash -c`, `ssh host "git commit"`), or a
    `-c` script behind a value-taking long option (`bash --rcfile f -c`).
    """

    if not isinstance(command, str):
        return False
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False

    for i, token in enumerate(tokens):
        if token == "git":
            commits = _runs_commit(tokens, i, repo_root, seen)
        elif Path(token).name in _SHELLS:
            script = _shell_script(tokens, i)
            commits = script is not None and _is_git_commit(script, repo_root, seen)
        elif token == "eval":
            # `eval` joins its arguments with spaces and parses the result
            # as shell — exactly this re-join and re-tokenize.
            commits = _is_git_commit(" ".join(tokens[i + 1 :]), repo_root, seen)
        else:
            commits = False
        if commits:
            return True
    return False


def _summarize(findings: tuple[Finding, ...]) -> str:
    return "\n".join(str(f) for f in findings)


def _disabled_checks(
    config: Mapping[str, object], registered: Sequence[str]
) -> frozenset[str]:
    """Every name in `registered` whose own `claims.toml` section reads
    `enabled = false` (ticket #44) — hook-scoped, alongside the existing
    plugin-wide `[hook] enabled`: this only silences that one check's own
    findings from *this* commit-time decision, never from `python3 -m
    claims.cli`/the `check-claims` skill, both of which call `run()`
    directly and never consult either flag.

    Restricted to `registered` (`RunResult.checks_run`, not `config`'s own
    keys) for two reasons at once: a top-level `claims.toml` value isn't
    guaranteed to even be a table (`config.py`'s own `_load_toml` return
    type is a lie past the top level — a bare `enabled = false` with no
    `[section]` at all is a real, unvalidated `bool`, not a `Mapping`,
    and would otherwise crash this function, denying the hook process
    itself and letting the commit land completely unchecked); and an
    unrecognized name here — `"config"`, the fixed `mode`
    `_unrecognized_table_findings` reports its own findings under, or any
    other typo — must never silence anything, since `[config] enabled =
    false` would otherwise silence the exact gate finding meant to warn
    about a `claims.toml` mistake, including that very one (ticket #21).
    """

    return frozenset(
        name
        for name, section in config.items()
        if name != "hook"
        and name in registered
        and isinstance(section, Mapping)
        and not section.get("enabled", True)
    )


def _finding_check(finding: Finding, names: frozenset[str]) -> str | None:
    """Which of `names` produced `finding`, or `None` if it isn't any of
    them — `Finding.mode` is usually a check's own registered name, but a
    check reporting more than one matching strategy (`restatement`'s own
    `-ngram`/`-whole-line` split, and similarly for `claim-words`,
    `spliced-docs`, `judgment-agent`) instead uses `{name}-suffix`, a
    convention every current multi-mode check follows but nothing in
    `Finding`'s own contract guarantees. Checked here, not by adding a
    `check` field to `Finding` itself: that would need updating every
    existing test asserting a hand-built `Finding(...)` against a real
    check's own output, for one hook-local filter.
    """

    for name in names:
        if finding.mode == name or finding.mode.startswith(f"{name}-"):
            return name
    return None


def _deny(reason: str) -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def decide(repo_root: Path, command: str) -> dict[str, object]:
    """The hook-output JSON for `command` about to run in `repo_root`.

    `{}` immediately — before even `load_config` — when `command` isn't a
    `git commit`: the manifest's `matcher` catches every `Bash` call, not
    just commits, so this is the actual gate.
    """

    if not _is_git_commit(command, repo_root):
        return {}

    try:
        config = load_config(repo_root)
    except ConfigError as e:
        return _deny(f"claims.toml is invalid: {e}")

    if not config.get("hook", {}).get("enabled", True):
        return {}

    result = run(repo_root, "HEAD", config)

    if not result.checks_run:
        return _deny("0 checked — no checks registered (failure, not a clean pass)")

    disabled = _disabled_checks(config, result.checks_run)
    findings = tuple(
        f for f in result.findings if _finding_check(f, disabled) is None
    )

    gate_findings = tuple(f for f in findings if f.gate)
    if gate_findings:
        return _deny(_summarize(findings))

    if findings:
        return {
            "hookSpecificOutput": {
                "hookEventName": HOOK_EVENT_NAME,
                "permissionDecision": "allow",
                "additionalContext": _summarize(findings),
            }
        }

    return {}


def main(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    try:
        payload = json.load(stdin)
        repo_root = Path(payload["cwd"])
        command = payload.get("tool_input", {}).get("command", "")
    except (json.JSONDecodeError, KeyError, AttributeError, TypeError) as e:
        json.dump(_deny(f"malformed PreToolUse payload: {e!r}"), stdout)
        return 0
    json.dump(decide(repo_root, command), stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
