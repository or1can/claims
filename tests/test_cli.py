"""Tests for the CLI adapter: `claims.cli`."""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from claims import runner
from claims.cli import main, parse_args
from claims.runner import Finding, register_check


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        runner.clear_registry()
        self.addCleanup(runner.clear_registry)

    def _run_main(self, argv: list[str]) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(argv)
        return code, out.getvalue()

    def test_zero_checks_registered_fails_never_a_silent_clean_pass(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            code, output = self._run_main(["--repo-root", repo_root])

        self.assertEqual(code, 1)
        self.assertIn("0 checked", output)

    def test_gate_finding_fails_the_cli(self) -> None:
        register_check(
            "failing-gate",
            lambda repo_root, diff_range, config: [
                Finding(file="a.md", line=1, message="bad", mode="failing-gate", gate=True)
            ],
        )
        with tempfile.TemporaryDirectory() as repo_root:
            code, output = self._run_main(["--repo-root", repo_root])

        self.assertEqual(code, 1)
        self.assertIn("a.md:1", output)

    def test_advisory_only_finding_passes_the_cli(self) -> None:
        register_check(
            "advisory-check",
            lambda repo_root, diff_range, config: [
                Finding(file="a.md", line=1, message="fyi", mode="advisory-check", gate=False)
            ],
        )
        with tempfile.TemporaryDirectory() as repo_root:
            code, output = self._run_main(["--repo-root", repo_root])

        self.assertEqual(code, 0)
        self.assertIn("a.md:1", output)

    def test_repo_root_and_diff_range_reach_the_check_unchanged(self) -> None:
        seen = {}

        def spy_check(repo_root, diff_range, config):
            seen["repo_root"] = repo_root
            seen["diff_range"] = diff_range
            return []

        register_check("spy", spy_check)

        with tempfile.TemporaryDirectory() as repo_root:
            self._run_main(["--repo-root", repo_root, "--diff-range", "main..feature"])
            self.assertEqual(seen["repo_root"], Path(repo_root).resolve())

        self.assertEqual(seen["diff_range"], "main..feature")

    def test_malformed_config_fails_cleanly_not_a_traceback(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            (Path(repo_root) / "claims.toml").write_text("not valid toml [[[")
            code, _ = self._run_main(["--repo-root", repo_root])

        self.assertEqual(code, 2)

    def test_diff_range_defaults_to_working_tree_against_head(self) -> None:
        args = parse_args(["--repo-root", "."])
        self.assertEqual(args.diff_range, "HEAD")

    def test_repo_root_defaults_to_cwd(self) -> None:
        args = parse_args([])
        self.assertEqual(args.repo_root, Path.cwd())


if __name__ == "__main__":
    unittest.main()
