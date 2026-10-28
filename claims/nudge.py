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

"""`SessionStart` and `CwdChanged` hook: a nudge when the repository the
session is in has opted in to the commit gate, with a root `claims.toml`,
but has no git hook installed that runs it (#128). Git decides when a
commit happens, through that hook, not the plugin
(`decisions/0007-git-decides-when-a-commit-happens.md`); the plugin only
says when the hook is missing.

"Installed" is a deliberately loose reading, erring toward silence:
`claims` anywhere in `.pre-commit-config.yaml`, `lefthook.yml`,
`lefthook.yaml` or a file in the effective hooks directory
(`git rev-parse --git-path hooks`, which honours `core.hooksPath`). A
mention that runs nothing still counts.

`SessionStart` tells the agent through `additionalContext` and the user
through a one-line `systemMessage`. `CwdChanged` reads `systemMessage`
alone from a hook's output, so after a `cd` only the user is told. A
repository root is nudged once per session on `CwdChanged`; each
`SessionStart` nudges again, since a resume, `/clear` or compaction
starts the agent's context over. The roots already nudged are kept in a
file per session under the system temporary directory.

Never blocks anything. Any error, a malformed payload included, outputs
`{}`.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import TextIO

from .config import has_config
from .git import toplevel

INSTALL_URL = "https://claims.apps.orican.eu/installation.html#the-git-pre-commit-hook"

CONTEXT = (
    "This repository opts in to the claims commit gate with a root "
    "claims.toml, but no git hook that runs claims is installed, so the "
    "claims commit gate is not active here: commits are not checked. "
    f"Installation: {INSTALL_URL}"
)

SYSTEM_MESSAGE = f"claims commit gate not active: no git hook runs claims. See {INSTALL_URL}"

_HOOK_CONFIGS = (".pre-commit-config.yaml", "lefthook.yml", "lefthook.yaml")


def _hooks_dir(root: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--git-path", "hooks"],
        capture_output=True,
        text=True,
        check=True,
    )
    return root / result.stdout.strip()


def _hook_installed(root: Path) -> bool:
    hooks_dir = _hooks_dir(root)
    candidates = [root / name for name in _HOOK_CONFIGS]
    if hooks_dir.is_dir():
        candidates.extend(hooks_dir.iterdir())
    return any(path.is_file() and b"claims" in path.read_bytes() for path in candidates)


def _first_nudge(state_dir: Path, session_id: str, root: Path) -> bool:
    """Records `root` as nudged in `session_id`, and whether it wasn't
    already."""

    digest = hashlib.sha256(session_id.encode()).hexdigest()[:32]
    state = state_dir / f"claims-nudge-{digest}"
    nudged = state.read_text().splitlines() if state.is_file() else []
    if str(root) in nudged:
        return False
    with state.open("a") as f:
        f.write(f"{root}\n")
    return True


def decide(event: str, session_id: str, cwd: Path, state_dir: Path) -> dict[str, object]:
    root = toplevel(cwd)
    if root is None or not has_config(root) or _hook_installed(root):
        return {}
    first = _first_nudge(state_dir, session_id, root)
    if event == "SessionStart":
        return {
            "hookSpecificOutput": {"hookEventName": event, "additionalContext": CONTEXT},
            "systemMessage": SYSTEM_MESSAGE,
        }
    return {"systemMessage": SYSTEM_MESSAGE} if first else {}


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
            Path(payload["cwd"]),
            state_dir or Path(tempfile.gettempdir()),
        )
    except Exception:
        output = {}
    json.dump(output, stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
