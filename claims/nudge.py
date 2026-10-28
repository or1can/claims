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

"""`SessionStart`, `CwdChanged` and `UserPromptSubmit` hook: a nudge when the repository the
session is in has opted in to the commit gate, with a root `claims.toml`
that doesn't read `[hook] enabled = false`, but has no git hook installed
that runs it (#128). A `claims.toml` that doesn't parse is nudged too: it
switched nothing off. Git decides when a
commit happens, through that hook, not the plugin
(`decisions/0007-git-decides-when-a-commit-happens.md`); the plugin only
says when the hook is missing.

"Installed" is a deliberately loose reading, erring toward silence:
`claims` anywhere in a file in the effective hooks directory (`git
rev-parse --git-path hooks`, which honours `core.hooksPath`), or in a hook
manager's configuration — `.pre-commit-config.yaml`, any of the names
lefthook reads, husky's `.husky/pre-commit` — once that hooks directory
holds a `pre-commit` hook at all. A manager installs a script of its own
there that names the manager, not `claims`; a committed configuration
with no hook installed is a fresh clone, which is gated by nothing. A
mention that runs nothing still counts.

The agent is told through `additionalContext`, the user through a
one-line `systemMessage`. `SessionStart` tells both, every time, since a
resume, `/clear` or compaction starts the agent's context over.
`CwdChanged` reads `systemMessage` alone from a hook's output, so it tells
only the user, once per repository root per session. `UserPromptSubmit`
tells the agent, and the user if a `cd` hasn't already, once per
repository root per session: Claude Code doesn't fire a plugin's
`CwdChanged` hook at all (anthropics/claude-code#105625), so the next
prompt is where a `cd` is first seen. Who has been told about which root
is kept in a file per session under the system temporary directory;
`SessionStart` nudges even when it can't be written.

Never blocks anything. Any error, a malformed payload included, outputs
`{}`.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import TextIO

from .config import ConfigError, has_config, load_config
from .git import toplevel

INSTALL_URL = "https://claims.apps.orican.eu/installation.html#the-git-pre-commit-hook"


def _context(root: Path) -> str:
    return (
        f"The repository at {root} opts in to the claims commit gate with a "
        "root claims.toml, but no git hook that runs claims is installed, so "
        "the claims commit gate is not active there: its commits are not "
        f"checked. Installation: {INSTALL_URL}"
    )


def _system_message(root: Path) -> str:
    return f"claims commit gate not active in {root}: no git hook runs claims. See {INSTALL_URL}"

_MANAGER_CONFIGS = (
    ".pre-commit-config.yaml",
    ".husky/pre-commit",
    *(
        f"{stem}.{extension}"
        for stem in ("lefthook", ".lefthook", ".config/lefthook")
        for extension in ("yml", "yaml", "toml", "json", "jsonc")
    ),
)


def _hooks_dir(root: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--git-path", "hooks"],
        capture_output=True,
        text=True,
        check=True,
    )
    return root / result.stdout.strip()


def _switched_off(root: Path) -> bool:
    """Whether `root`'s `claims.toml` reads `[hook] enabled = false`; not
    when it doesn't parse, or `hook` isn't a table, since neither turned
    the gate off on purpose."""

    try:
        hook = load_config(root).get("hook", {})
    except ConfigError:
        return False
    return isinstance(hook, Mapping) and not hook.get("enabled", True)


def _mentions_claims(path: Path) -> bool:
    return path.is_file() and b"claims" in path.read_bytes()


def _hook_installed(root: Path) -> bool:
    hooks_dir = _hooks_dir(root)
    if not hooks_dir.is_dir():
        return False
    if any(map(_mentions_claims, hooks_dir.iterdir())):
        return True
    return (hooks_dir / "pre-commit").is_file() and any(
        _mentions_claims(root / name) for name in _MANAGER_CONFIGS
    )


def _state_file(state_dir: Path, session_id: str) -> Path:
    digest = hashlib.sha256(session_id.encode()).hexdigest()[:32]
    return state_dir / f"claims-nudge-{digest}"


def _told(state: Path, root: Path) -> set[str]:
    """Who, of `agent` and `user`, has been told about `root`."""

    if not state.is_file():
        return set()
    lines = state.read_text().splitlines()
    return {who for who in ("agent", "user") if f"{who} {root}" in lines}


def _record(state: Path, root: Path, told: set[str]) -> None:
    with state.open("a") as f:
        f.writelines(f"{who} {root}\n" for who in sorted(told))


def decide(event: str, session_id: str, cwd: Path, state_dir: Path) -> dict[str, object]:
    """The hook-output JSON for `event` — `SessionStart`, `CwdChanged` or
    `UserPromptSubmit` — in `cwd`: the nudge, or `{}` when there is nothing
    to say."""

    root = toplevel(cwd)
    if root is None or not has_config(root):
        return {}
    state = _state_file(state_dir, session_id)
    told = _told(state, root)
    if event == "SessionStart":
        tell = {"agent", "user"}
    elif event == "CwdChanged":
        tell = {"user"} - told
    elif event == "UserPromptSubmit" and "agent" not in told:
        tell = {"agent", "user"} - told
    else:
        return {}
    if not tell or _switched_off(root) or _hook_installed(root):
        return {}
    if event == "SessionStart":
        # The agent is told whether or not the record can be written.
        with contextlib.suppress(OSError):
            _record(state, root, tell - told)
    else:
        _record(state, root, tell)
    output: dict[str, object] = {}
    if "agent" in tell:
        output["hookSpecificOutput"] = {
            "hookEventName": event,
            "additionalContext": _context(root),
        }
    if "user" in tell:
        output["systemMessage"] = _system_message(root)
    return output


def main(
    stdin: TextIO = sys.stdin,
    stdout: TextIO = sys.stdout,
    state_dir: Path | None = None,
) -> int:
    try:
        payload = json.load(stdin)
        output = decide(
            payload["hook_event_name"],
            payload["session_id"],
            Path(payload.get("new_cwd") or payload["cwd"]),
            state_dir or Path(tempfile.gettempdir()),
        )
    except Exception:
        output = {}
    json.dump(output, stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
