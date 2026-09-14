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

"""Tests for the `executable-claims` check: `claims.checks.executable_claims`.

Exercises the shared `run(repo_root, diff_range, config)` seam against a
fixture git repo, asserting on the returned `Finding` list — see spec.md's
Testing Decisions. Ported from `verify-docs.py`'s own test suite
(Apache-2.0 prior art), adapted for the new shell-execution and exit-code
requirements this check adds.
"""

from __future__ import annotations

import contextlib
import io
import os
import shlex
import subprocess
import sys
import unittest
from pathlib import Path

from claims.checks.executable_claims import NAME, check
from claims.cli import main
from claims.config import load_config
from claims.runner import Finding, register_check, run

from support import RegistryClearingTestCase, Repo


def marked(command: str, body: str) -> str:
    return f"<!-- verify: {command} -->\n```\n{body}\n```\n"


def nested_marker_example() -> str:
    """Documentation illustrating the marker syntax itself — the marker
    line is inside an already-open fence, not directly above one."""

    return (
        "Example of the marker syntax:\n"
        "\n"
        "```\n"
        "<!-- verify: some-command -->\n"
        "```\n"
        "\n"
        "```\n"
        "expected output shown here\n"
        "```\n"
    )


def python(source: str) -> str:
    return f"{shlex.quote(sys.executable)} -c {shlex.quote(source)}"


def echo(text: str) -> str:
    return python(f"import sys; sys.stdout.write({text!r})")


class ExecutableClaimsTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def _findings(self, repo_root: Path) -> list[Finding]:
        return list(run(repo_root, "HEAD", {}).findings)

    def _findings_with_config(self, repo_root: Path, claims_toml: str) -> list[Finding]:
        (repo_root / "claims.toml").write_text(claims_toml)
        config = load_config(repo_root)
        return list(run(repo_root, "HEAD", config).findings)

    def test_an_excluded_path_is_skipped_entirely(self) -> None:
        with Repo() as repo:
            repo.write("skip.md", "just prose, no markers here\n")
            findings = self._findings_with_config(
                repo.root, '[executable-claims]\nexclude = ["skip.md"]\n'
            )
        self.assertEqual(findings, [])

    def test_exclude_does_not_affect_a_non_matching_path(self) -> None:
        with Repo() as repo:
            repo.write("keep.md", marked(echo("hello\n"), "hello"))
            repo.write("skip.md", "just prose, no markers here\n")
            findings = self._findings_with_config(
                repo.root, '[executable-claims]\nexclude = ["skip.md"]\n'
            )
        self.assertEqual(findings, [])

    def test_excluding_one_alias_of_a_symlinked_pair_excludes_both(self) -> None:
        # AGENTS.md/CLAUDE.md is this file's own documented symlink
        # convention (the `seen`-by-real-path dedup exists because of it).
        # Naming only one alias in `exclude` must not leave its content
        # checked, and reported, under the other alias instead.
        with Repo() as repo:
            repo.write(
                "AGENTS.md", "<!-- verify: false -->\n```\nnever matches\n```\n"
            )
            os.symlink("AGENTS.md", repo.root / "CLAUDE.md")
            subprocess.run(
                ["git", "-C", str(repo.root), "add", "CLAUDE.md"], check=True
            )
            findings = self._findings_with_config(
                repo.root, '[executable-claims]\nexclude = ["AGENTS.md"]\n'
            )
        self.assertEqual(findings, [])

    def test_an_unrelated_exclusion_does_not_mask_a_real_zero_marker_failure(
        self,
    ) -> None:
        # `docs/history.md` opting out of the sweep must not be why the
        # gate goes quiet about `real.md` genuinely carrying no marker —
        # only excluding *everything* earns the exception.
        with Repo() as repo:
            repo.write("docs/history.md", "historical notes, no markers\n")
            repo.write("real.md", "no marker in this file either\n")
            findings = self._findings_with_config(
                repo.root, '[executable-claims]\nexclude = ["docs/history.md"]\n'
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("no verify markers found", findings[0].message)

    def test_a_true_claim_passes(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", marked(echo("hello\n"), "hello"))
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_false_claim_with_mismatched_output_fails(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", marked(echo("actual\n"), "documented"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "doc.md:1")
        self.assertTrue(findings[0].gate)

    def test_a_false_claim_with_matching_text_but_nonzero_exit_fails(self) -> None:
        command = python("import sys; sys.stdout.write('hello'); sys.exit(1)")
        with Repo() as repo:
            repo.write("doc.md", marked(command, "hello"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("exited 1", findings[0].message)

    def test_a_malformed_marker_not_above_a_fenced_block_fails(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", "<!-- verify: some-command -->\n\nordinary prose\n")
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("not above a fenced block", findings[0].message)

    def test_a_marker_shown_as_literal_text_inside_a_fence_is_not_live(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", nested_marker_example())
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("no verify markers found", findings[0].message)

    def test_a_nested_marker_example_does_not_interfere_with_a_real_marker(self) -> None:
        doc = nested_marker_example() + "\n" + marked(echo("hello\n"), "hello")
        with Repo() as repo:
            repo.write("doc.md", doc)
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_marker_example_nested_in_a_longer_outer_fence_is_not_live(self) -> None:
        # CommonMark's real nesting rule: a fence only closes on a
        # same-or-longer run of backticks. A 3-backtick example nested
        # inside a 4-backtick outer fence is the documented way to show
        # fence syntax itself — the inner ``` lines are literal content,
        # not real delimiters, so the marker between them must stay dead.
        doc = (
            "Example of the marker syntax, inside a longer outer fence so\n"
            "its own ``` lines aren't mistaken for real ones:\n"
            "\n"
            "````\n"
            "```\n"
            "<!-- verify: echo nested-should-not-run -->\n"
            "```\n"
            "\n"
            "```\n"
            "expected output shown here\n"
            "```\n"
            "````\n"
        )
        with Repo() as repo:
            repo.write("doc.md", doc)
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("no verify markers found", findings[0].message)

    def test_a_live_markers_own_block_may_nest_a_fenced_example(self) -> None:
        # The documented output legitimately contains a fenced block of
        # its own (e.g. output that is itself markdown) — wrapped in a
        # longer outer fence, per CommonMark's own nesting convention.
        # The nested lines must not truncate the captured expected block.
        command = echo("```\ninner\n```\n")
        doc = f"<!-- verify: {command} -->\n" "````\n" "```\n" "inner\n" "```\n" "````\n"
        with Repo() as repo:
            repo.write("doc.md", doc)
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_an_unclosed_fenced_block_is_reported_not_silently_mishandled(self) -> None:
        # A genuinely live marker (its own fence pair closes cleanly)
        # still runs and passes on its own merits; a separate, later,
        # never-closed fence elsewhere in the file must still be a loud
        # finding of its own, not silently swallow anything before it.
        doc = marked(echo("hello\n"), "hello") + "```\n"
        with Repo() as repo:
            repo.write("doc.md", doc)
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("never closed", findings[0].message)
        self.assertTrue(findings[0].gate)

    def test_a_sweep_finding_zero_markers_is_a_failure(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", "just prose, no markers here\n")
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].gate)

    def test_the_command_runs_through_a_shell_so_a_pipe_works(self) -> None:
        command = f"{python('import sys; sys.stdout.write(chr(10).join([\"a\", \"b\", \"c\"]) + chr(10))')} | tail -1"
        with Repo() as repo:
            repo.write("doc.md", marked(command, "c"))
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_the_prompt_line_of_a_transcript_is_not_compared(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", marked(echo("hello\n"), "$ some-command\nhello"))
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_tracked_filename_containing_a_space_is_still_swept(self) -> None:
        with Repo() as repo:
            repo.write("release notes.md", marked(echo("hello\n"), "hello"))
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])


class ExecutableClaimsCliTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def test_end_to_end_via_the_cli(self) -> None:
        with Repo() as repo:
            repo.write("true.md", marked(echo("hello\n"), "hello"))
            repo.write("false.md", marked(echo("actual\n"), "documented"))
            repo.write("malformed.md", "<!-- verify: some-command -->\n\nprose\n")

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(["--repo-root", str(repo.root)])
            output = out.getvalue()

        self.assertEqual(code, 1)
        self.assertIn("false.md:1", output)
        self.assertIn("malformed.md:1", output)
        self.assertNotIn("true.md", output)


if __name__ == "__main__":
    unittest.main()
