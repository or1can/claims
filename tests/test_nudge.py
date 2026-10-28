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

"""Tests for the `SessionStart`/`CwdChanged` nudge: `claims.nudge`.

Feeds fixture stdin JSON matching Claude Code's hook contract and asserts
on the JSON emitted to stdout (#128).
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from claims.nudge import main

from support import Repo


class NudgeTests(unittest.TestCase):
    def setUp(self) -> None:
        state = tempfile.TemporaryDirectory()
        self.addCleanup(state.cleanup)
        self.state_dir = Path(state.name)

    def _run(
        self, cwd: Path, event: str = "SessionStart", session_id: str = "s1"
    ) -> dict:
        payload = {
            "session_id": session_id,
            "transcript_path": "/tmp/transcript.jsonl",
            "cwd": str(cwd),
            "hook_event_name": event,
        }
        if event == "CwdChanged":
            payload["new_cwd"] = str(cwd)
        stdout = io.StringIO()
        code = main(io.StringIO(json.dumps(payload)), stdout, self.state_dir)
        self.assertEqual(code, 0)
        return json.loads(stdout.getvalue())

    def _assert_nudged_at_session_start(self, output: dict) -> None:
        hook_output = output["hookSpecificOutput"]
        self.assertEqual(hook_output["hookEventName"], "SessionStart")
        self.assertIn("not active", hook_output["additionalContext"])
        self.assertIn("installation", hook_output["additionalContext"])
        self.assertIn("not active", output["systemMessage"])
        self.assertNotIn("\n", output["systemMessage"])

    def test_an_opted_in_repo_with_no_hook_is_nudged(self) -> None:
        with Repo() as repo:
            (repo.root / "claims.toml").write_text("")
            self._assert_nudged_at_session_start(self._run(repo.root))

    def test_the_nudge_names_the_repository(self) -> None:
        # After a `cd` the agent can't otherwise tell which repository it
        # is about.
        with Repo() as repo:
            (repo.root / "claims.toml").write_text("")
            output = self._run(repo.root, event="UserPromptSubmit")
            root = str(repo.root.resolve())
        self.assertIn(root, output["hookSpecificOutput"]["additionalContext"])
        self.assertIn(root, output["systemMessage"])

    def test_a_subdirectory_of_an_opted_in_repo_is_nudged(self) -> None:
        with Repo() as repo:
            (repo.root / "claims.toml").write_text("")
            (repo.root / "sub").mkdir()
            self._assert_nudged_at_session_start(self._run(repo.root / "sub"))

    def test_a_cd_into_an_opted_in_repo_tells_the_user(self) -> None:
        # `CwdChanged` reads `systemMessage` alone from a hook's output.
        with Repo() as repo:
            (repo.root / "claims.toml").write_text("")
            output = self._run(repo.root, event="CwdChanged")
        self.assertNotIn("hookSpecificOutput", output)
        self.assertIn("not active", output["systemMessage"])

    _MANAGER_CONFIGS = {
        ".pre-commit-config.yaml": (
            "repos:\n  - repo: https://github.com/or1can/claims\n"
            "    rev: v0.16.0\n    hooks:\n      - id: claims\n"
        ),
        "lefthook.yml": "pre-commit:\n  commands:\n    claims:\n      run: claims-pre-commit\n",
        "lefthook.yaml": "pre-commit:\n  commands:\n    claims:\n      run: claims-pre-commit\n",
    }

    def test_a_hook_manager_installed_with_claims_configured_is_not_nudged(
        self,
    ) -> None:
        # The installed `pre-commit` script is the manager's own, and
        # names the manager, not `claims`.
        for name, text in self._MANAGER_CONFIGS.items():
            with self.subTest(name=name), Repo() as repo:
                (repo.root / "claims.toml").write_text("")
                (repo.root / name).write_text(text)
                (repo.root / ".git" / "hooks" / "pre-commit").write_text(
                    "#!/bin/sh\nexec manager run pre-commit\n"
                )
                self.assertEqual(self._run(repo.root), {})

    def test_a_hook_manager_configured_but_never_installed_is_nudged(self) -> None:
        # A fresh clone: the configuration is committed, the hook is not.
        for name, text in self._MANAGER_CONFIGS.items():
            with self.subTest(name=name), Repo() as repo:
                (repo.root / "claims.toml").write_text("")
                (repo.root / name).write_text(text)
                self._assert_nudged_at_session_start(self._run(repo.root))

    def test_every_lefthook_config_name_is_read(self) -> None:
        for name in (".lefthook.yml", ".config/lefthook.toml", "lefthook.jsonc"):
            with self.subTest(name=name), Repo() as repo:
                (repo.root / "claims.toml").write_text("")
                (repo.root / name).parent.mkdir(parents=True, exist_ok=True)
                (repo.root / name).write_text("claims-pre-commit\n")
                (repo.root / ".git" / "hooks" / "pre-commit").write_text(
                    "#!/bin/sh\nexec lefthook run pre-commit\n"
                )
                self.assertEqual(self._run(repo.root), {})

    def test_a_plain_hook_that_runs_claims_is_not_nudged(self) -> None:
        with Repo() as repo:
            (repo.root / "claims.toml").write_text("")
            (repo.root / ".git" / "hooks" / "pre-commit").write_text(
                "#!/bin/sh\nexec claims-pre-commit\n"
            )
            self.assertEqual(self._run(repo.root), {})

    def test_husky_with_claims_configured_is_not_nudged(self) -> None:
        # husky points `core.hooksPath` at `.husky/_`, whose scripts are
        # generic wrappers around the project's own `.husky/pre-commit`.
        with Repo() as repo:
            (repo.root / "claims.toml").write_text("")
            (repo.root / ".husky" / "_").mkdir(parents=True)
            (repo.root / ".husky" / "_" / "pre-commit").write_text(
                '#!/usr/bin/env sh\n. "$(dirname "$0")/h"\n'
            )
            (repo.root / ".husky" / "pre-commit").write_text(
                "uvx --from git+https://github.com/or1can/claims@v0.16.0 claims-pre-commit\n"
            )
            repo.config("core.hooksPath", ".husky/_")
            self.assertEqual(self._run(repo.root), {})

    def test_a_repo_that_switched_the_gate_off_is_not_nudged(self) -> None:
        for event in ("SessionStart", "CwdChanged"):
            with self.subTest(event=event), Repo() as repo:
                (repo.root / "claims.toml").write_text("[hook]\nenabled = false\n")
                self.assertEqual(self._run(repo.root, event=event), {})

    def test_a_claims_toml_that_cannot_say_the_gate_is_off_is_nudged(self) -> None:
        # Neither is `[hook] enabled = false`, so neither switched the gate
        # off on purpose.
        for text in ("[hook\nenabled = false\n", "hook = false\n"):
            with self.subTest(text=text), Repo() as repo:
                (repo.root / "claims.toml").write_text(text)
                self._assert_nudged_at_session_start(self._run(repo.root))

    def test_a_cd_payload_without_new_cwd_is_judged_by_cwd(self) -> None:
        with Repo() as repo:
            (repo.root / "claims.toml").write_text("")
            payload = {"session_id": "s1", "cwd": str(repo.root), "hook_event_name": "CwdChanged"}
            stdout = io.StringIO()
            main(io.StringIO(json.dumps(payload)), stdout, self.state_dir)
        self.assertIn("not active", json.loads(stdout.getvalue())["systemMessage"])

    def test_a_cd_is_judged_by_the_new_directory(self) -> None:
        with Repo() as before, Repo() as after:
            (after.root / "claims.toml").write_text("")
            payload = {
                "session_id": "s1",
                "cwd": str(before.root),
                "hook_event_name": "CwdChanged",
                "old_cwd": str(before.root),
                "new_cwd": str(after.root),
            }
            stdout = io.StringIO()
            main(io.StringIO(json.dumps(payload)), stdout, self.state_dir)
        self.assertIn("not active", json.loads(stdout.getvalue())["systemMessage"])

    def test_a_hook_in_core_hooks_path_is_found(self) -> None:
        with Repo() as repo:
            (repo.root / "claims.toml").write_text("")
            (repo.root / ".githooks").mkdir()
            (repo.root / ".githooks" / "pre-commit").write_text(
                "#!/bin/sh\nexec claims-pre-commit\n"
            )
            repo.config("core.hooksPath", ".githooks")
            self.assertEqual(self._run(repo.root), {})

    def test_a_hooks_directory_without_claims_is_still_nudged(self) -> None:
        with Repo() as repo:
            (repo.root / "claims.toml").write_text("")
            (repo.root / ".git" / "hooks" / "pre-commit").write_text(
                "#!/bin/sh\nexec make lint\n"
            )
            self._assert_nudged_at_session_start(self._run(repo.root))

    def test_a_repo_with_no_claims_toml_is_not_nudged(self) -> None:
        with Repo() as repo:
            self.assertEqual(self._run(repo.root), {})

    def test_a_directory_outside_any_git_repo_is_not_nudged(self) -> None:
        with tempfile.TemporaryDirectory() as cwd:
            (Path(cwd) / "claims.toml").write_text("")
            self.assertEqual(self._run(Path(cwd)), {})

    def test_a_cd_within_the_same_repo_is_not_nudged_twice(self) -> None:
        with Repo() as repo:
            (repo.root / "claims.toml").write_text("")
            (repo.root / "sub").mkdir()
            self._assert_nudged_at_session_start(self._run(repo.root))
            self.assertEqual(self._run(repo.root / "sub", event="CwdChanged"), {})
            self.assertEqual(self._run(repo.root, event="CwdChanged"), {})

    def test_a_cd_into_a_second_opted_in_repo_is_nudged(self) -> None:
        with Repo() as first, Repo() as second:
            for repo in (first, second):
                (repo.root / "claims.toml").write_text("")
            self._run(first.root)
            output = self._run(second.root, event="CwdChanged")
        self.assertIn("not active", output["systemMessage"])

    def test_a_prompt_in_an_opted_in_repo_tells_the_agent_and_the_user(self) -> None:
        # Claude Code doesn't fire a plugin's `CwdChanged` hook
        # (anthropics/claude-code#105625), so the next prompt is the first
        # chance to see a `cd`.
        with Repo() as repo:
            (repo.root / "claims.toml").write_text("")
            output = self._run(repo.root, event="UserPromptSubmit")
        hook_output = output["hookSpecificOutput"]
        self.assertEqual(hook_output["hookEventName"], "UserPromptSubmit")
        self.assertIn("not active", hook_output["additionalContext"])
        self.assertIn("not active", output["systemMessage"])

    def test_a_prompt_after_session_start_in_the_same_repo_is_not_nudged(self) -> None:
        with Repo() as repo:
            (repo.root / "claims.toml").write_text("")
            self._run(repo.root)
            self.assertEqual(self._run(repo.root, event="UserPromptSubmit"), {})

    def test_a_second_prompt_in_the_same_repo_is_not_nudged(self) -> None:
        with Repo() as repo:
            (repo.root / "claims.toml").write_text("")
            self._run(repo.root, event="UserPromptSubmit")
            self.assertEqual(self._run(repo.root, event="UserPromptSubmit"), {})
            self.assertEqual(self._run(repo.root, event="CwdChanged"), {})

    def test_a_prompt_after_a_cd_told_the_user_tells_only_the_agent(self) -> None:
        # `CwdChanged` reaches the user alone; the agent still needs telling.
        with Repo() as repo:
            (repo.root / "claims.toml").write_text("")
            self._run(repo.root, event="CwdChanged")
            output = self._run(repo.root, event="UserPromptSubmit")
        self.assertIn("not active", output["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("systemMessage", output)

    def test_another_session_in_the_same_repo_is_nudged(self) -> None:
        with Repo() as repo:
            (repo.root / "claims.toml").write_text("")
            self._run(repo.root, event="CwdChanged", session_id="s1")
            output = self._run(repo.root, event="CwdChanged", session_id="s2")
        self.assertIn("not active", output["systemMessage"])

    def test_a_new_session_start_nudges_again(self) -> None:
        # A resume, `/clear` or compaction starts the agent's context over,
        # so whatever it was told before is gone.
        with Repo() as repo:
            (repo.root / "claims.toml").write_text("")
            self._run(repo.root)
            self._assert_nudged_at_session_start(self._run(repo.root))

    def test_an_internal_error_outputs_nothing(self) -> None:
        with Repo() as repo, mock.patch(
            "claims.nudge.toplevel", side_effect=RuntimeError("boom")
        ):
            (repo.root / "claims.toml").write_text("")
            self.assertEqual(self._run(repo.root), {})

    def test_a_malformed_payload_outputs_nothing(self) -> None:
        for raw in ("not json", "null", "[]", '{"session_id": "s1"}'):
            with self.subTest(raw=raw):
                stdout = io.StringIO()
                self.assertEqual(main(io.StringIO(raw), stdout, self.state_dir), 0)
                self.assertEqual(json.loads(stdout.getvalue()), {})

    def test_an_unwritable_state_directory_still_nudges_at_session_start(
        self,
    ) -> None:
        # Only `CwdChanged` needs the record of what was already said.
        with Repo() as repo:
            (repo.root / "claims.toml").write_text("")
            self.state_dir = repo.root / "claims.toml" / "not-a-directory"
            self._assert_nudged_at_session_start(self._run(repo.root))
            self.assertEqual(self._run(repo.root, event="CwdChanged"), {})


if __name__ == "__main__":
    unittest.main()
