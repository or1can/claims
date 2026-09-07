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
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from claims.checks.executable_claims import NAME, check
from claims.cli import main
from claims.runner import Finding, register_check, run

from support import RegistryClearingTestCase


class Repo:
    """A throwaway git repository — the check finds files with `git
    ls-files`, so an unversioned directory has nothing to check."""

    def __enter__(self) -> "Repo":
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        return self

    def __exit__(self, *_exc: object) -> None:
        self._temp.cleanup()

    def write(self, name: str, text: str) -> None:
        (self.root / name).write_text(text, encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", name], check=True)


def marked(command: str, body: str) -> str:
    return f"<!-- verify: {command} -->\n```\n{body}\n```\n"


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
