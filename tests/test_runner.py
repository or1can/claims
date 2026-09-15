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

    def test_a_check_that_raises_does_not_crash_the_run(self) -> None:
        def boom(repo_root, diff_range, config):
            raise ValueError("kaboom")

        def ok(repo_root, diff_range, config):
            return [Finding(file="a.md", line=1, message="hi", mode="ok", gate=False)]

        register_check("boom", boom)
        register_check("ok", ok)

        result = run(Path("/repo"), "HEAD", {})

        self.assertEqual(result.checks_run, ("boom", "ok"))
        ok_findings = [f for f in result.findings if f.mode == "ok"]
        self.assertEqual(len(ok_findings), 1)

    def test_a_check_that_raises_produces_a_gate_finding_naming_it(self) -> None:
        def boom(repo_root, diff_range, config):
            raise ValueError("kaboom")

        register_check("boom", boom)

        result = run(Path("/repo"), "HEAD", {})

        crash_findings = [f for f in result.findings if f.gate and f.mode == "boom"]
        self.assertEqual(len(crash_findings), 1)
        self.assertIn("kaboom", crash_findings[0].message)

    def test_an_unrecognized_table_name_is_a_gate_finding(self) -> None:
        register_check("check-a", lambda repo_root, diff_range, config: [])

        result = run(Path("/repo"), "HEAD", {"check-a": {}, "typo-check": {}})

        unrecognized = [f for f in result.findings if "typo-check" in f.message]
        self.assertEqual(len(unrecognized), 1)
        finding = unrecognized[0]
        self.assertTrue(finding.gate)
        self.assertEqual(finding.file, "claims.toml")
        self.assertEqual(finding.line, 0)
        self.assertEqual(finding.mode, "config")

    def test_a_hook_table_typo_is_told_it_is_not_a_check_name_or_hook(self) -> None:
        result = run(Path("/repo"), "HEAD", {"hooks": {"enabled": False}})

        self.assertEqual(len(result.findings), 1)
        self.assertIn("not a registered check name or [hook]", result.findings[0].message)

    def test_every_table_matching_a_registered_check_produces_no_finding(self) -> None:
        register_check("check-a", lambda repo_root, diff_range, config: [])
        register_check("check-b", lambda repo_root, diff_range, config: [])

        result = run(
            Path("/repo"), "HEAD", {"check-a": {"x": 1}, "check-b": {"y": 2}}
        )

        self.assertEqual(result.findings, ())

    def test_the_hook_table_is_not_flagged_as_unrecognized(self) -> None:
        result = run(Path("/repo"), "HEAD", {"hook": {"enabled": False}})

        self.assertEqual(result.findings, ())

    def test_an_empty_config_produces_no_unrecognized_table_finding(self) -> None:
        register_check("check-a", lambda repo_root, diff_range, config: [])

        result = run(Path("/repo"), "HEAD", {})

        self.assertEqual(result.findings, ())

    def test_an_unrecognized_table_suggests_the_hyphen_normalized_match(self) -> None:
        register_check("executable-claims", lambda repo_root, diff_range, config: [])

        result = run(Path("/repo"), "HEAD", {"executable_claims": {}})

        self.assertEqual(len(result.findings), 1)
        self.assertIn("executable_claims", result.findings[0].message)
        self.assertIn("executable-claims", result.findings[0].message)

    def test_an_unrecognized_table_with_no_close_match_has_no_suggestion(self) -> None:
        register_check("check-a", lambda repo_root, diff_range, config: [])

        result = run(Path("/repo"), "HEAD", {"nonsense": {}})

        self.assertEqual(len(result.findings), 1)
        self.assertIn("nonsense", result.findings[0].message)
        self.assertNotIn("did you mean", result.findings[0].message)

    def test_multiple_unrecognized_tables_each_get_their_own_finding(self) -> None:
        result = run(Path("/repo"), "HEAD", {"typo-one": {}, "typo-two": {}})

        messages = [f.message for f in result.findings]
        self.assertTrue(any("typo-one" in m for m in messages))
        self.assertTrue(any("typo-two" in m for m in messages))
        self.assertEqual(len(result.findings), 2)


if __name__ == "__main__":
    unittest.main()
