"""Tests for the core runner seam: `claims.runner`.

Exercises `run(repo_root, diff_range, config)` against registered checks,
never internal helpers in isolation — see spec.md's Testing Decisions.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from claims.runner import Finding, register_check, run

from support import RegistryClearingTestCase


class RunnerTests(RegistryClearingTestCase):
    def test_zero_checks_registered_reports_zero_checked(self) -> None:
        result = run(Path("/repo"), "HEAD", {})
        self.assertEqual(result.checks_run, ())
        self.assertEqual(result.findings, ())

    def test_a_check_registers_without_the_runner_knowing_in_advance(self) -> None:
        def my_check(repo_root, diff_range, config):
            return [Finding(file="a.md", line=1, message="hi", mode="my-check", gate=False)]

        register_check("my-check", my_check)

        result = run(Path("/repo"), "HEAD", {})

        self.assertEqual(result.checks_run, ("my-check",))
        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].citation, "a.md:1")

    def test_registering_the_same_name_twice_raises(self) -> None:
        register_check("dup", lambda repo_root, diff_range, config: [])
        with self.assertRaises(ValueError):
            register_check("dup", lambda repo_root, diff_range, config: [])

    def test_repo_root_and_diff_range_pass_through_unchanged(self) -> None:
        seen = {}

        def spy_check(repo_root, diff_range, config):
            seen["repo_root"] = repo_root
            seen["diff_range"] = diff_range
            return []

        register_check("spy", spy_check)

        repo_root = Path("/some/repo")
        run(repo_root, "main..feature", {})

        self.assertEqual(seen["repo_root"], repo_root)
        self.assertEqual(seen["diff_range"], "main..feature")

    def test_a_check_only_sees_its_own_config_section(self) -> None:
        seen_configs = {}

        def check_a(repo_root, diff_range, config):
            seen_configs["a"] = config
            return []

        def check_b(repo_root, diff_range, config):
            seen_configs["b"] = config
            return []

        register_check("check-a", check_a)
        register_check("check-b", check_b)

        run(
            Path("/repo"),
            "HEAD",
            {"check-a": {"threshold": 5}, "check-b": {"pattern": "*.md"}},
        )

        self.assertEqual(seen_configs["a"], {"threshold": 5})
        self.assertEqual(seen_configs["b"], {"pattern": "*.md"})

    def test_a_check_with_no_config_section_gets_an_empty_mapping(self) -> None:
        seen_configs = {}

        def check_a(repo_root, diff_range, config):
            seen_configs["a"] = config
            return []

        register_check("check-a", check_a)

        run(Path("/repo"), "HEAD", {"check-b": {"pattern": "*.md"}})

        self.assertEqual(seen_configs["a"], {})


if __name__ == "__main__":
    unittest.main()
