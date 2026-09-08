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

"""Tests for the `PreToolUse` hook adapter: `claims.hook`.

Feeds fixture stdin JSON matching Claude Code's hook contract and asserts on
the JSON emitted to stdout — no live Claude Code session required, per
spec.md's Testing Decisions for this adapter.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from claims.hook import main
from claims.runner import Finding, register_check

from support import RegistryClearingTestCase

PRE_TOOL_USE_PAYLOAD = {
    "session_id": "test-session",
    "transcript_path": "/tmp/transcript.jsonl",
    "hook_event_name": "PreToolUse",
    "tool_name": "Bash",
    "tool_input": {"command": "git commit -m test"},
}


class HookTests(RegistryClearingTestCase):
    def _run_main(self, repo_root: str) -> dict:
        stdin = io.StringIO(json.dumps({**PRE_TOOL_USE_PAYLOAD, "cwd": repo_root}))
        stdout = io.StringIO()
        code = main(stdin, stdout)
        self.assertEqual(code, 0)
        return json.loads(stdout.getvalue())

    def test_gate_finding_denies_with_a_human_readable_reason(self) -> None:
        register_check(
            "failing-gate",
            lambda repo_root, diff_range, config: [
                Finding(file="a.md", line=1, message="bad", mode="failing-gate", gate=True)
            ],
        )
        with tempfile.TemporaryDirectory() as repo_root:
            output = self._run_main(repo_root)

        hook_output = output["hookSpecificOutput"]
        self.assertEqual(hook_output["permissionDecision"], "deny")
        self.assertIn("a.md:1", hook_output["permissionDecisionReason"])
        self.assertIn("bad", hook_output["permissionDecisionReason"])

    def test_advisory_only_findings_allow_and_attach_additional_context(self) -> None:
        register_check(
            "advisory-check",
            lambda repo_root, diff_range, config: [
                Finding(file="a.md", line=1, message="fyi", mode="advisory-check", gate=False)
            ],
        )
        with tempfile.TemporaryDirectory() as repo_root:
            output = self._run_main(repo_root)

        hook_output = output["hookSpecificOutput"]
        self.assertEqual(hook_output["permissionDecision"], "allow")
        self.assertIn("a.md:1", hook_output["additionalContext"])
        self.assertIn("fyi", hook_output["additionalContext"])

    def test_disabled_toggle_is_a_noop_regardless_of_findings(self) -> None:
        register_check(
            "failing-gate",
            lambda repo_root, diff_range, config: [
                Finding(file="a.md", line=1, message="bad", mode="failing-gate", gate=True)
            ],
        )
        with tempfile.TemporaryDirectory() as repo_root:
            (Path(repo_root) / "claims.toml").write_text("[hook]\nenabled = false\n")
            output = self._run_main(repo_root)

        self.assertEqual(output, {})

    def test_zero_checks_registered_denies_never_a_silent_clean_pass(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            output = self._run_main(repo_root)

        hook_output = output["hookSpecificOutput"]
        self.assertEqual(hook_output["permissionDecision"], "deny")
        self.assertIn("0 checked", hook_output["permissionDecisionReason"])

    def test_gate_deny_reason_also_includes_advisory_findings(self) -> None:
        register_check(
            "failing-gate",
            lambda repo_root, diff_range, config: [
                Finding(file="a.md", line=1, message="bad", mode="failing-gate", gate=True)
            ],
        )
        register_check(
            "advisory-check",
            lambda repo_root, diff_range, config: [
                Finding(file="b.md", line=2, message="fyi", mode="advisory-check", gate=False)
            ],
        )
        with tempfile.TemporaryDirectory() as repo_root:
            output = self._run_main(repo_root)

        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("a.md:1", reason)
        self.assertIn("b.md:2", reason)

    def test_no_findings_is_a_noop(self) -> None:
        register_check("clean-check", lambda repo_root, diff_range, config: [])
        with tempfile.TemporaryDirectory() as repo_root:
            output = self._run_main(repo_root)

        self.assertEqual(output, {})

    def test_malformed_config_denies_rather_than_crashing(self) -> None:
        register_check("any-check", lambda repo_root, diff_range, config: [])
        with tempfile.TemporaryDirectory() as repo_root:
            (Path(repo_root) / "claims.toml").write_text("not valid toml [[[")
            output = self._run_main(repo_root)

        hook_output = output["hookSpecificOutput"]
        self.assertEqual(hook_output["permissionDecision"], "deny")
        self.assertIn("claims.toml", hook_output["permissionDecisionReason"])


if __name__ == "__main__":
    unittest.main()
