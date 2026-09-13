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
`tool_input.command` the manifest already let through.

Reads Claude Code's hook-event JSON from stdin and writes its hook-output
JSON to stdout: `permissionDecision: deny` with a human-readable reason on a
gate finding, `additionalContext` for advisory-only findings, or `{}` when
the command isn't a `git commit`, the hook is disabled, or there is nothing
to report. See code.claude.com/docs/en/hooks for the contract this speaks.
"""

from __future__ import annotations

import json
import shlex
import sys
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


def _is_git_commit(command: object) -> bool:
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

    Residual accepted gap, in the *missed* direction this function
    otherwise avoids: a compact, no-space operator (`cd /tmp&&git
    commit`) merges into the adjacent token (`/tmp&&git`), so `git` never
    appears as a token to find at all. Idiomatic shell style (this
    plugin's own commits included) always spaces these; fixing it would
    mean pre-splitting the raw string on operator characters, which needs
    to respect quoting to avoid corrupting an argument that legitimately
    contains one (`git commit -m "a|b"`) — the same class of parsing
    hazard this file's diff-parsing sibling module (`claims/git.py`)
    exists to avoid, not worth reintroducing for a rare, unidiomatic
    input shape.
    """

    if not isinstance(command, str):
        return False
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False

    return any(
        _git_subcommand(tokens, i) == "commit"
        for i, token in enumerate(tokens)
        if token == "git"
    )


def _summarize(findings: tuple[Finding, ...]) -> str:
    return "\n".join(str(f) for f in findings)


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

    if not _is_git_commit(command):
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

    gate_findings = tuple(f for f in result.findings if f.gate)
    if gate_findings:
        return _deny(_summarize(result.findings))

    if result.findings:
        return {
            "hookSpecificOutput": {
                "hookEventName": HOOK_EVENT_NAME,
                "permissionDecision": "allow",
                "additionalContext": _summarize(result.findings),
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
