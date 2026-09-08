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

"""`PreToolUse` hook adapter, matched (by the plugin manifest) on
`Bash(git commit *)`.

Reads Claude Code's hook-event JSON from stdin and writes its hook-output
JSON to stdout: `permissionDecision: deny` with a human-readable reason on a
gate finding, `additionalContext` for advisory-only findings, or `{}` when
the hook is disabled or there is nothing to report. See
code.claude.com/docs/en/hooks for the contract this speaks.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TextIO

from . import checks  # noqa: F401
from .config import ConfigError, load_config
from .runner import Finding, run

HOOK_EVENT_NAME = "PreToolUse"


def _summarize(findings: tuple[Finding, ...]) -> str:
    return "\n".join(
        f"[{'GATE' if f.gate else 'advisory'}] {f.citation} ({f.mode}) {f.message}"
        for f in findings
    )


def _deny(reason: str) -> dict[str, object]:
    return {
        "hookSpecificOutput": {
            "hookEventName": HOOK_EVENT_NAME,
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def decide(repo_root: Path) -> dict[str, object]:
    """The hook-output JSON for a `git commit` about to run in `repo_root`."""

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
    payload = json.load(stdin)
    repo_root = Path(payload["cwd"])
    json.dump(decide(repo_root), stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
