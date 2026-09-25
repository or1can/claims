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
from claims.runner import Finding, clear_registry, register_check

from support import RegistryClearingTestCase, Repo

PRE_TOOL_USE_PAYLOAD = {
    "session_id": "test-session",
    "transcript_path": "/tmp/transcript.jsonl",
    "hook_event_name": "PreToolUse",
    "tool_name": "Bash",
    "tool_input": {"command": "git commit -m test"},
}


class HookTests(RegistryClearingTestCase):
    def _run_main(self, repo_root: str, command: str | None = None) -> dict:
        payload = {**PRE_TOOL_USE_PAYLOAD, "cwd": repo_root}
        if command is not None:
            payload["tool_input"] = {"command": command}
        stdin = io.StringIO(json.dumps(payload))
        stdout = io.StringIO()
        code = main(stdin, stdout)
        self.assertEqual(code, 0)
        return json.loads(stdout.getvalue())

    def _ran_checks(self, repo_root: str, command: str) -> bool:
        clear_registry()
        ran: list[bool] = []
        register_check(
            "spy-check",
            lambda repo_root, diff_range, config: (ran.append(True), [])[1],
        )
        self._run_main(repo_root, command=command)
        return bool(ran)

    def test_a_non_git_commit_bash_command_never_runs_the_checks(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            self.assertFalse(self._ran_checks(repo_root, "echo hello"))

    def test_commands_that_are_not_a_git_commit_despite_looking_close(self) -> None:
        # Tokenized, not a bare substring match: a git plumbing subcommand
        # whose name starts with "commit", and prose that merely mentions
        # "git commit" inside a quoted string, must not false-trigger.
        # (An *unquoted* "git"/"commit" belonging to some other command —
        # `grep git commit file.txt` — is a deliberately accepted false
        # positive; see test_a_false_positive_this_deliberately_accepts.)
        not_commits = [
            "git commit-graph verify",
            'echo "remember to git commit later"',
            'git tag -a v1.0 -m "commit"',
            "git branch commit",
            'git log --grep "commit"',
        ]
        for command in not_commits:
            with self.subTest(command=command):
                with tempfile.TemporaryDirectory() as repo_root:
                    self.assertFalse(self._ran_checks(repo_root, command))

    def test_a_false_positive_this_deliberately_accepts(self) -> None:
        # "git"/"commit" as some *other* command's own unquoted arguments
        # false-trigger — accepted, since the alternative (bounding the
        # search to a shell-operator segment) misses a real commit after
        # an un-spaced operator, a later line of a multi-line command, or
        # a backgrounding `&`, none of which `shlex` reliably marks as a
        # boundary — see test_git_commit_variants_all_run_the_checks.
        # Firing here costs one harmless extra check run; missing there
        # lets a commit land completely unchecked.
        false_positives = ["grep git commit test.txt", "history | grep git commit"]
        for command in false_positives:
            with self.subTest(command=command):
                with tempfile.TemporaryDirectory() as repo_root:
                    self.assertTrue(self._ran_checks(repo_root, command))

    def test_a_non_string_command_is_treated_as_not_a_commit(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            self.assertFalse(self._ran_checks(repo_root, 123))  # type: ignore[arg-type]

    def test_git_commit_variants_all_run_the_checks(self) -> None:
        commits = [
            # A global option between `git` and `commit` (taking its own
            # value or not) must not be missed.
            'git add -A && git commit -m "message"',
            'git -C /tmp commit -m "message"',
            'git -c user.name=x commit -m "message"',
            "git --no-pager commit --amend",
            "git --config-env foo.bar=SOME_VAR commit -m x",
            'GIT_AUTHOR_DATE="2026-01-01" git commit -m "message"',
            # Real commits with no reliable shell-operator boundary for
            # `shlex` to mark — must still be found, not missed by luck.
            "echo hi\ngit commit -m test",
            "long_task & git commit -m wip",
        ]
        for command in commits:
            with self.subTest(command=command):
                with tempfile.TemporaryDirectory() as repo_root:
                    self.assertTrue(self._ran_checks(repo_root, command))

    def _denied(self, repo_root: str, command: str) -> bool:
        clear_registry()
        register_check(
            "failing-gate",
            lambda repo_root, diff_range, config: [
                Finding(file="a.md", line=1, message="bad", mode="failing-gate", gate=True)
            ],
        )
        output = self._run_main(repo_root, command=command)
        return output.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_a_commit_inside_a_nested_shell_is_denied(self) -> None:
        commits = [
            'bash -c "git commit -m x"',
            "sh -c 'git add . && git commit -m x'",
            'eval "git commit -m x"',
            '/bin/zsh -lc "git commit -m x"',
            "bash -o pipefail -c 'git commit -m x'",
            'bash -c "sh -c \\"git commit -m x\\""',
        ]
        for command in commits:
            with self.subTest(command=command):
                with tempfile.TemporaryDirectory() as repo_root:
                    self.assertTrue(self._denied(repo_root, command))

    def test_a_nested_shell_that_does_not_commit_is_not_a_commit(self) -> None:
        not_commits = [
            'bash -c "git status"',
            "bash -c \"echo 'remember to git commit later'\"",
            'eval "git log --grep commit"',
            "bash script.sh",
        ]
        for command in not_commits:
            with self.subTest(command=command):
                with tempfile.TemporaryDirectory() as repo_root:
                    self.assertFalse(self._ran_checks(repo_root, command))

    def test_a_git_alias_resolving_to_commit_is_denied(self) -> None:
        aliases = {
            "ci": ("commit", "git ci -m x"),
            "cm": ("commit -m", "git cm x"),
            "c": ("ci", "git c -m x"),
            "ac": ("!git add -A && git commit", "git ac -m x"),
        }
        for name, (expansion, command) in aliases.items():
            with self.subTest(alias=name):
                with Repo() as repo:
                    repo.config("alias.ci", "commit")
                    repo.config(f"alias.{name}", expansion)
                    self.assertTrue(self._denied(str(repo.root), command))

    def test_a_git_alias_not_resolving_to_commit_is_not_a_commit(self) -> None:
        with Repo() as repo:
            repo.config("alias.st", "status")
            # Git ignores an alias that shadows a built-in command.
            repo.config("alias.tag", "commit")
            # A self-referencing shell alias must not recurse forever.
            repo.config("alias.loop", "!git loop")
            for command in ["git st", "git tag -m commit v1", "git loop"]:
                with self.subTest(command=command):
                    self.assertFalse(self._ran_checks(str(repo.root), command))

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

    def test_a_per_check_enabled_false_silences_that_checks_gate_finding(self) -> None:
        register_check(
            "failing-gate",
            lambda repo_root, diff_range, config: [
                Finding(file="a.md", line=1, message="bad", mode="failing-gate", gate=True)
            ],
        )
        with tempfile.TemporaryDirectory() as repo_root:
            (Path(repo_root) / "claims.toml").write_text("[failing-gate]\nenabled = false\n")
            output = self._run_main(repo_root)

        self.assertEqual(output, {})

    def test_a_per_check_enabled_false_silences_that_checks_advisory_finding(
        self,
    ) -> None:
        register_check(
            "advisory-check",
            lambda repo_root, diff_range, config: [
                Finding(file="a.md", line=1, message="fyi", mode="advisory-check", gate=False)
            ],
        )
        with tempfile.TemporaryDirectory() as repo_root:
            (Path(repo_root) / "claims.toml").write_text(
                "[advisory-check]\nenabled = false\n"
            )
            output = self._run_main(repo_root)

        self.assertEqual(output, {})

    def test_a_per_check_enabled_false_does_not_affect_other_checks(self) -> None:
        register_check(
            "failing-gate",
            lambda repo_root, diff_range, config: [
                Finding(file="a.md", line=1, message="bad", mode="failing-gate", gate=True)
            ],
        )
        register_check("clean-check", lambda repo_root, diff_range, config: [])
        with tempfile.TemporaryDirectory() as repo_root:
            (Path(repo_root) / "claims.toml").write_text("[clean-check]\nenabled = false\n")
            output = self._run_main(repo_root)

        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_a_per_check_enabled_false_silences_a_multi_mode_findings_own_suffix(
        self,
    ) -> None:
        # Some checks report findings under a `{name}-suffix` mode rather
        # than the bare registered name (`restatement`'s own `-ngram`/
        # `-whole-line` split, `claim-words`'/`spliced-docs`'/
        # `judgment-agent`'s own multi-mode splits) — a per-check
        # `enabled` has to still catch these, not just an exact `mode ==
        # name` match, or it would silently no-op for every check that
        # happens to report more than one mode.
        register_check(
            "multi-mode-check",
            lambda repo_root, diff_range, config: [
                Finding(
                    file="a.md",
                    line=1,
                    message="fyi",
                    mode="multi-mode-check-some-suffix",
                    gate=True,
                )
            ],
        )
        with tempfile.TemporaryDirectory() as repo_root:
            (Path(repo_root) / "claims.toml").write_text(
                "[multi-mode-check]\nenabled = false\n"
            )
            output = self._run_main(repo_root)

        self.assertEqual(output, {})

    def test_a_top_level_non_table_value_does_not_crash_the_hook(self) -> None:
        # `claims.toml`'s own top level isn't guaranteed to be all tables —
        # a bare `enabled = false` with no `[section]` around it at all is
        # a real, valid TOML document whose value for that key is a plain
        # bool, not a table. Crashing here would deny the hook *process*
        # itself (no JSON at all on stdout, a non-blocking hook error),
        # letting the commit land completely unchecked — worse than the
        # correct outcome, a loud gate finding via the ticket-#21 gate on
        # a top-level name naming no registered check.
        register_check("any-check", lambda repo_root, diff_range, config: [])
        with tempfile.TemporaryDirectory() as repo_root:
            (Path(repo_root) / "claims.toml").write_text("enabled = false\n")
            output = self._run_main(repo_root)

        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_disabling_the_fixed_config_mode_name_does_not_silence_it(self) -> None:
        # `"config"` is `_unrecognized_table_findings`'s own fixed `mode`
        # (ticket #21) for a claims.toml table naming no registered check
        # — `[config]\nenabled = false` must not silence that exact
        # warning, including a warning about `[config]` itself being
        # unrecognized, or this becomes a self-silencing escape hatch from
        # the one whole-config safety net this plugin has.
        register_check("any-check", lambda repo_root, diff_range, config: [])
        with tempfile.TemporaryDirectory() as repo_root:
            (Path(repo_root) / "claims.toml").write_text(
                "[config]\nenabled = false\n[not-a-real-check]\nx = 1\n"
            )
            output = self._run_main(repo_root)

        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")
        reason = output["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("not-a-real-check", reason)

    def test_an_unregistered_name_does_not_wildcard_match_real_checks(self) -> None:
        # `[check]\nenabled = false` must not silence `check-links`,
        # `check-file-refs`, and every other real `check-*` check at once
        # just because their own modes happen to start with `check-` too
        # — only a name that's actually in the live registry may disable
        # anything.
        register_check(
            "check-something",
            lambda repo_root, diff_range, config: [
                Finding(file="a.md", line=1, message="bad", mode="check-something", gate=True)
            ],
        )
        with tempfile.TemporaryDirectory() as repo_root:
            (Path(repo_root) / "claims.toml").write_text("[check]\nenabled = false\n")
            output = self._run_main(repo_root)

        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

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

    def test_malformed_stdin_payload_denies_rather_than_crashing(self) -> None:
        stdin = io.StringIO("not valid json")
        stdout = io.StringIO()
        code = main(stdin, stdout)
        self.assertEqual(code, 0)

        output = json.loads(stdout.getvalue())
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_a_null_tool_input_denies_rather_than_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            payload = {**PRE_TOOL_USE_PAYLOAD, "cwd": repo_root, "tool_input": None}
            stdin = io.StringIO(json.dumps(payload))
            stdout = io.StringIO()
            code = main(stdin, stdout)

        self.assertEqual(code, 0)
        output = json.loads(stdout.getvalue())
        self.assertEqual(output["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_a_non_object_top_level_payload_denies_rather_than_crashing(self) -> None:
        for raw in ("null", "[]", "42"):
            with self.subTest(raw=raw):
                stdin = io.StringIO(raw)
                stdout = io.StringIO()
                code = main(stdin, stdout)

                self.assertEqual(code, 0)
                output = json.loads(stdout.getvalue())
                self.assertEqual(
                    output["hookSpecificOutput"]["permissionDecision"], "deny"
                )


if __name__ == "__main__":
    unittest.main()
