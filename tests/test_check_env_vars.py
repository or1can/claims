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

"""Tests for the `check-env-vars` check: `claims.checks.check_env_vars`.

Exercises the shared `run(repo_root, diff_range, config)` seam against
fixture git repos — see spec.md's Testing Decisions.
"""

from __future__ import annotations

from pathlib import Path

from claims.checks.check_env_vars import NAME, check
from claims.config import load_config
from claims.runner import Finding, register_check, run

from support import RegistryClearingTestCase, Repo


class CheckEnvVarsTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def _findings(self, repo_root: Path) -> list[Finding]:
        return list(run(repo_root, "HEAD", {}).findings)

    def _findings_with_config(self, repo_root: Path, claims_toml: str) -> list[Finding]:
        (repo_root / "claims.toml").write_text(claims_toml)
        config = load_config(repo_root)
        return list(run(repo_root, "HEAD", config).findings)

    def test_a_var_present_in_env_example_produces_no_finding(self) -> None:
        with Repo() as repo:
            repo.write(".env.example", "STATION_NAME=ai_radio\n")
            repo.write("README.md", "Set `STATION_NAME` to configure the station.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_var_absent_from_env_example_produces_an_advisory_finding(self) -> None:
        with Repo() as repo:
            repo.write(".env.example", "OTHER_VAR=1\n")
            repo.write("README.md", "Set `STATION_NAME` to configure the station.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "README.md:1")
        self.assertFalse(findings[0].gate)
        self.assertIn("STATION_NAME", findings[0].message)

    def test_a_bare_all_caps_mention_is_not_detected(self) -> None:
        with Repo() as repo:
            repo.write(".env.example", "OTHER_VAR=1\n")
            repo.write("README.md", "Set STATION_NAME to configure the station.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_an_all_caps_word_with_no_underscore_is_not_a_candidate(self) -> None:
        with Repo() as repo:
            repo.write(".env.example", "OTHER_VAR=1\n")
            repo.write("README.md", "Uses `HTTP` and `TLS` under the hood.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_no_env_example_and_no_configured_scope_is_genuinely_inert(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "Set `STATION_NAME` to configure the station.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_configured_source_file_is_searched_too(self) -> None:
        with Repo() as repo:
            repo.write("src/config.py", "STATION_NAME = os.environ['STATION_NAME']\n")
            repo.write("README.md", "Set `STATION_NAME` to configure the station.\n")
            repo.commit()
            findings = self._findings_with_config(
                repo.root, '[check-env-vars]\ndefinition_files = ["src/*.py"]\n'
            )
        self.assertEqual(findings, [])

    def test_configured_files_are_additive_to_the_env_example_default(self) -> None:
        with Repo() as repo:
            repo.write(".env.example", "STATION_NAME=ai_radio\n")
            repo.write("src/config.py", "TIMEOUT = os.environ['TIMEOUT']\n")
            repo.write(
                "README.md",
                "Set `STATION_NAME` and `TIMEOUT` to configure the station.\n",
            )
            repo.commit()
            findings = self._findings_with_config(
                repo.root, '[check-env-vars]\ndefinition_files = ["src/*.py"]\n'
            )
        self.assertEqual(findings, [])

    def test_a_bare_string_definition_files_value_is_coerced_to_one_element(self) -> None:
        with Repo() as repo:
            repo.write("src/config.py", "STATION_NAME = os.environ['STATION_NAME']\n")
            repo.write("README.md", "Set `STATION_NAME` to configure the station.\n")
            repo.commit()
            findings = self._findings_with_config(
                repo.root, '[check-env-vars]\ndefinition_files = "src/config.py"\n'
            )
        self.assertEqual(findings, [])

    def test_word_boundary_safe_match_does_not_false_positive_on_a_substring(self) -> None:
        with Repo() as repo:
            repo.write(".env.example", "OLD_STATION_NAME=ai_radio\n")
            repo.write("README.md", "Set `STATION_NAME` to configure the station.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("STATION_NAME", findings[0].message)

    def test_multiple_candidates_on_one_line_are_each_checked(self) -> None:
        with Repo() as repo:
            repo.write(".env.example", "STATION_NAME=ai_radio\n")
            repo.write(
                "README.md", "Set `STATION_NAME` and `MISSING_VAR` together.\n"
            )
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("MISSING_VAR", findings[0].message)

    def test_a_tracked_but_empty_env_example_is_a_found_scope_not_no_scope(
        self,
    ) -> None:
        # A found scope file with empty text is still "the check has a
        # scope" (every mention is, correctly, unresolved) — not the same
        # case as zero scope files existing at all (genuinely inert).
        with Repo() as repo:
            repo.write(".env.example", "")
            repo.write("README.md", "Set `STATION_NAME` to configure the station.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("STATION_NAME", findings[0].message)

    def test_a_candidate_inside_a_fenced_code_block_is_not_detected(self) -> None:
        with Repo() as repo:
            repo.write(".env.example", "OTHER_VAR=1\n")
            repo.write(
                "README.md",
                "Example:\n\n```markdown\nSet `STATION_NAME` in your config.\n```\n",
            )
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_candidate_outside_a_fence_is_still_flagged(self) -> None:
        with Repo() as repo:
            repo.write(".env.example", "OTHER_VAR=1\n")
            repo.write(
                "README.md",
                "```markdown\nSet `STATION_NAME` in your config.\n```\n\n"
                "Also set `MISSING_VAR`.\n",
            )
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("MISSING_VAR", findings[0].message)

    def test_an_excluded_path_is_not_swept_for_candidates(self) -> None:
        with Repo() as repo:
            repo.write(".env.example", "OTHER_VAR=1\n")
            repo.write(
                "notes/history.md", "Old note: `STATION_NAME` used to exist.\n"
            )
            repo.commit()
            findings = self._findings_with_config(
                repo.root, '[check-env-vars]\nexclude = ["notes/*.md"]\n'
            )
        self.assertEqual(findings, [])

    def test_exclude_does_not_affect_a_non_matching_path(self) -> None:
        with Repo() as repo:
            repo.write(".env.example", "OTHER_VAR=1\n")
            repo.write("README.md", "Set `STATION_NAME` to configure the station.\n")
            repo.commit()
            findings = self._findings_with_config(
                repo.root, '[check-env-vars]\nexclude = ["notes/*.md"]\n'
            )
        self.assertEqual(len(findings), 1)


if __name__ == "__main__":
    import unittest

    unittest.main()
