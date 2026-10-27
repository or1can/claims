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
needs to filter correctly. `_commit_dirs` below does the fine-grained
"is it specifically a commit" narrowing in Python instead, over whatever
`tool_input.command` the manifest already let through. `if` holds one
rule only, so the manifest repeats the same handler once per command
name `_commit_dirs` looks inside — `bash`, `sh`, `zsh` and `eval`
besides `git` (ticket #85) — or `bash -c "git commit"` would never reach
it. Each rule names the bare command, so `/bin/zsh -c`, which
`_commit_dirs` itself handles, never reaches it; and a command
matching two of them (`bash x.sh && git commit`) runs the hook twice,
each running every check and reaching the same decision.

Reads Claude Code's hook-event JSON from stdin and writes its hook-output
JSON to stdout: `permissionDecision: deny` with a human-readable reason on a
gate finding, `additionalContext` for advisory-only findings, or `{}` when
the command isn't a `git commit`, the hook is disabled, or there is nothing
to report. See code.claude.com/docs/en/hooks for the contract this speaks.

The plugin's hook follows the session, not the repository being committed
to, so a repository opts in by having a root `claims.toml` (ticket #118,
`decisions/0006-claims-toml-opts-in-to-the-commit-hook.md`): a commit
anywhere else gets `{}` with no check run. Each commit is decided in the
repository it targets — `cwd` with that `git`'s own `-C` paths applied,
resolved to its top level — so a session sitting in a subdirectory, or
committing elsewhere through `git -C`, is decided against the right root
`claims.toml` and tree.

The decision for each repository — `[hook] enabled = false`, a check's
own `enabled = false` — is `claims.gate`'s, shared with the git
`pre-commit` command (`claims.pre_commit`).
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import TextIO

from .gate import decide_repo
from .git import toplevel

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


def _git_subcommand(
    tokens: list[str], git_index: int
) -> tuple[str | None, list[str]]:
    """The subcommand the `git` token at `tokens[git_index]` runs, or
    `None` if nothing follows it, and the `-C` paths given before it, in
    order.

    Skips global options right after `git` — including one extra token
    for a value-taking option's own value — so `commit` in subcommand
    position is found correctly regardless of how many global options
    precede it, without matching `commit` as merely some later argument's
    *value* (`git tag -m commit`, `git branch commit`) the way "any
    `commit` token anywhere after `git`" would.
    """

    i = git_index + 1
    chdirs: list[str] = []
    while i < len(tokens) and tokens[i].startswith("-"):
        option = tokens[i]
        i += 1
        if option in _VALUE_TAKING_GIT_OPTIONS and "=" not in option:
            if option == "-C" and i < len(tokens):
                chdirs.append(tokens[i])
            i += 1
    return (tokens[i] if i < len(tokens) else None), chdirs


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


def _git_alias(directory: Path, name: str) -> str | None:
    """`alias.<name>`'s value as git config resolves it in `directory`, or
    `None` if it has none."""

    result = subprocess.run(
        ["git", "-C", str(directory), "config", "--get", f"alias.{name}"],
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


def _git_commit_dirs(
    tokens: list[str], git_index: int, cwd: Path, seen: frozenset[str]
) -> list[Path]:
    """The directory each `commit` the `git` at `tokens[git_index]` runs
    is made from, directly or through an alias: `cwd` with its `-C` paths
    applied in order, a relative one resolving against the directory so
    far, as git does.

    An alias is searched as the command it expands to — `git <expansion>`,
    or a `!` alias's shell command as-is — so an alias of an alias
    resolves too. `seen` holds the aliases already expanded on the way
    here, so one that refers back to itself (`!git loop` as `alias.loop`)
    ends rather than recursing forever. An alias named after a built-in
    is skipped, as git itself ignores it; asked only once an alias is
    found, so a plain `git status` costs one `git config` call, not two.
    """

    subcommand, chdirs = _git_subcommand(tokens, git_index)
    directory = cwd.joinpath(*chdirs)
    if subcommand == "commit":
        return [directory]
    if subcommand is None or subcommand in seen:
        return []
    expansion = _git_alias(directory, subcommand)
    if expansion is None or _is_git_builtin(subcommand):
        return []
    if expansion.startswith("!"):
        # Git runs a shell alias from the work tree's top level.
        shell_cwd = toplevel(directory) or directory
        return _commit_dirs(expansion[1:], shell_cwd, seen | {subcommand})
    return _commit_dirs(f"git {expansion}", directory, seen | {subcommand})


def _commit_dirs(
    command: object, cwd: Path, seen: frozenset[str] = frozenset()
) -> list[Path]:
    """The directory each `git commit` in `command`, tokenized, is made
    from — empty when it runs none.

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
    (`_git_commit_dirs`) — including a `!` shell alias, whose command is
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
    input shape. Aliases are looked up in the config git reads from the
    `git`'s own directory, so one defined inline (`git -c alias.ci=commit
    ci`) is missed; so is a script run by any other shell (`dash -c`, `ssh
    host "git commit"`), or a `-c` script behind a value-taking long
    option (`bash --rcfile f -c`).

    The directory follows `-C` only. A `cd` earlier in the command, or
    `--git-dir`/`--work-tree`, isn't followed, so such a commit is decided
    in `cwd`'s repository instead of the one it lands in.
    """

    if not isinstance(command, str):
        return []
    try:
        tokens = shlex.split(command)
    except ValueError:
        return []

    dirs: list[Path] = []
    for i, token in enumerate(tokens):
        if token == "git":
            dirs.extend(_git_commit_dirs(tokens, i, cwd, seen))
        elif Path(token).name in _SHELLS:
            script = _shell_script(tokens, i)
            if script is not None:
                dirs.extend(_commit_dirs(script, cwd, seen))
        elif token == "eval":
            # `eval` joins its arguments with spaces and parses the result
            # as shell — exactly this re-join and re-tokenize.
            dirs.extend(_commit_dirs(" ".join(tokens[i + 1 :]), cwd, seen))
    return dirs


def _deny(reason: str) -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _advise(context: str) -> dict[str, object]:
    # No `permissionDecision`: `allow` would skip the user's own permission
    # prompt for the command, and an advisory finding only adds context.
    return {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "additionalContext": context,
        }
    }


def decide(cwd: Path, command: str) -> dict[str, object]:
    """The hook-output JSON for `command` about to run in `cwd`.

    `{}` immediately — before even `load_config` — when `command` isn't a
    `git commit`: the manifest's `matcher` catches every `Bash` call, not
    just commits, so this is the actual gate. Otherwise each repository
    the command commits to is decided on its own (`_decide_repo`); the
    command is denied if any one of them denies it, and advisory findings
    from all of them are joined.
    """

    roots = dict.fromkeys(filter(None, map(toplevel, _commit_dirs(command, cwd))))
    contexts: list[str] = []
    for root in roots:
        output = _decide_repo(root)
        hook_output = output.get("hookSpecificOutput")
        if not isinstance(hook_output, dict):
            continue
        if hook_output.get("permissionDecision") == "deny":
            return output
        contexts.append(hook_output["additionalContext"])
    return _advise("\n".join(contexts)) if contexts else {}


def _decide_repo(repo_root: Path) -> dict[str, object]:
    """The hook-output JSON for a commit to the repository at `repo_root`
    (`claims.gate.decide_repo`)."""

    decision = decide_repo(repo_root)
    if decision is None:
        return {}
    return _deny(decision.message) if decision.block else _advise(decision.message)


def main(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> int:
    try:
        payload = json.load(stdin)
        cwd = Path(payload["cwd"])
        command = payload.get("tool_input", {}).get("command", "")
    except (json.JSONDecodeError, KeyError, AttributeError, TypeError) as e:
        json.dump(_deny(f"malformed PreToolUse payload: {e!r}"), stdout)
        return 0
    json.dump(decide(cwd, command), stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
