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

"""Tests for the `check-config-defaults` check: `claims.checks.check_config_defaults`.

Exercises the shared `run(repo_root, diff_range, config)` seam against
fixture git repos — see spec.md's Testing Decisions.
"""

from __future__ import annotations

from pathlib import Path

from claims.checks.check_config_defaults import NAME, check
from claims.config import load_config
from claims.runner import Finding, register_check, run

from support import RegistryClearingTestCase, Repo


class CheckConfigDefaultsTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def _findings(self, repo_root: Path) -> list[Finding]:
        return list(run(repo_root, "HEAD", {}).findings)

    def _findings_with_config(self, repo_root: Path, claims_toml: str) -> list[Finding]:
        (repo_root / "claims.toml").write_text(claims_toml)
        config = load_config(repo_root)
        return list(run(repo_root, "HEAD", config).findings)

    def test_a_matching_default_produces_no_finding(self) -> None:
        with Repo() as repo:
            repo.write("src/config.py", "STATION_NAME = 'ai_radio'\n")
            repo.write(
                "README.md", "`STATION_NAME` defaults to `ai_radio`.\n"
            )
            repo.commit()
            findings = self._findings_with_config(
                repo.root,
                '[check-config-defaults]\nSTATION_NAME = "src/config.py:1"\n',
            )
        self.assertEqual(findings, [])

    def test_a_mismatched_default_produces_an_advisory_finding(self) -> None:
        with Repo() as repo:
            repo.write("src/config.py", "STATION_NAME = 'talk_radio'\n")
            repo.write(
                "README.md", "`STATION_NAME` defaults to `ai_radio`.\n"
            )
            repo.commit()
            findings = self._findings_with_config(
                repo.root,
                '[check-config-defaults]\nSTATION_NAME = "src/config.py:1"\n',
            )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "README.md:1")
        self.assertFalse(findings[0].gate)
        self.assertIn("STATION_NAME", findings[0].message)
        self.assertIn("ai_radio", findings[0].message)
        self.assertIn("src/config.py:1", findings[0].message)

    def test_a_setting_with_no_mapping_entry_produces_no_finding(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "`UNMAPPED` defaults to `whatever`.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_the_shared_enabled_key_is_not_read_as_a_setting_mapping(self) -> None:
        # `enabled = false` is the hook's own per-check switch, documented as
        # shared by every check; here every other key of the section is a
        # setting name, so this one must be set aside rather than parsed
        # as a target and crashed on.
        with Repo() as repo:
            repo.write("src/config.py", "STATION_NAME = 'talk_radio'\n")
            repo.write("README.md", "`STATION_NAME` defaults to `ai_radio`.\n")
            repo.commit()
            findings = self._findings_with_config(
                repo.root,
                '[check-config-defaults]\nenabled = false\n'
                'STATION_NAME = "src/config.py:1"\n',
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("`STATION_NAME` claims default `ai_radio`", findings[0].message)

    def test_a_claim_without_both_backticks_is_not_detected(self) -> None:
        with Repo() as repo:
            repo.write("src/config.py", "STATION_NAME = 'ai_radio'\n")
            repo.write("README.md", "STATION_NAME defaults to the AI Radio station.\n")
            repo.commit()
            findings = self._findings_with_config(
                repo.root,
                '[check-config-defaults]\nSTATION_NAME = "src/config.py:1"\n',
            )
        self.assertEqual(findings, [])

    def test_quote_stripping_normalizes_the_claimed_value(self) -> None:
        with Repo() as repo:
            repo.write("src/config.py", "STATION_NAME = ai_radio\n")
            repo.write(
                "README.md", "`STATION_NAME` defaults to `'ai_radio'`.\n"
            )
            repo.commit()
            findings = self._findings_with_config(
                repo.root,
                '[check-config-defaults]\nSTATION_NAME = "src/config.py:1"\n',
            )
        self.assertEqual(findings, [])

    def test_a_range_target_is_supported(self) -> None:
        with Repo() as repo:
            repo.write(
                "src/config.py",
                "class Config:\n    STATION_NAME = (\n        'ai_radio'\n    )\n",
            )
            repo.write(
                "README.md", "`STATION_NAME` defaults to `ai_radio`.\n"
            )
            repo.commit()
            findings = self._findings_with_config(
                repo.root,
                '[check-config-defaults]\nSTATION_NAME = "src/config.py:2-4"\n',
            )
        self.assertEqual(findings, [])

    def test_a_missing_mapped_file_produces_a_finding_not_a_crash(self) -> None:
        with Repo() as repo:
            repo.write(
                "README.md", "`STATION_NAME` defaults to `ai_radio`.\n"
            )
            repo.commit()
            findings = self._findings_with_config(
                repo.root,
                '[check-config-defaults]\nSTATION_NAME = "src/nonexistent.py:1"\n',
            )
        self.assertEqual(len(findings), 1)
        self.assertFalse(findings[0].gate)

    def test_a_malformed_target_spec_is_a_clear_crash_finding(self) -> None:
        with Repo() as repo:
            repo.write(
                "README.md", "`STATION_NAME` defaults to `ai_radio`.\n"
            )
            repo.commit()
            findings = self._findings_with_config(
                repo.root,
                '[check-config-defaults]\nSTATION_NAME = "no-colon-here"\n',
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("ConfigError", findings[0].message)

    def test_a_zero_line_number_is_a_clear_crash_finding_not_a_false_report(
        self,
    ) -> None:
        # `lines[start - 1 : end]` on `start = 0` silently slices from the
        # *last* line (Python's negative-index wraparound) rather than
        # raising — a config mistake must not surface as a false "this
        # doc claim is wrong" finding against an innocent line.
        with Repo() as repo:
            repo.write("src/config.py", "TIMEOUT = 30\n")
            repo.write("README.md", "`TIMEOUT` defaults to `30`.\n")
            repo.commit()
            findings = self._findings_with_config(
                repo.root, '[check-config-defaults]\nTIMEOUT = "src/config.py:0"\n'
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("ConfigError", findings[0].message)
        self.assertTrue(findings[0].gate)

    def test_a_reversed_range_is_a_clear_crash_finding(self) -> None:
        with Repo() as repo:
            repo.write("src/config.py", "TIMEOUT = 30\n")
            repo.write("README.md", "`TIMEOUT` defaults to `30`.\n")
            repo.commit()
            findings = self._findings_with_config(
                repo.root, '[check-config-defaults]\nTIMEOUT = "src/config.py:10-5"\n'
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("ConfigError", findings[0].message)
        self.assertTrue(findings[0].gate)

    def test_a_trailing_dash_with_no_end_is_a_clear_crash_finding(self) -> None:
        with Repo() as repo:
            repo.write("src/config.py", "TIMEOUT = 30\n")
            repo.write("README.md", "`TIMEOUT` defaults to `30`.\n")
            repo.commit()
            findings = self._findings_with_config(
                repo.root, '[check-config-defaults]\nTIMEOUT = "src/config.py:1-"\n'
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("ConfigError", findings[0].message)
        self.assertTrue(findings[0].gate)
        self.assertTrue(findings[0].gate)

    def test_default_colon_phrase_is_detected(self) -> None:
        with Repo() as repo:
            repo.write("src/config.py", "TIMEOUT = 30\n")
            repo.write("README.md", "`TIMEOUT` default: `30`\n")
            repo.commit()
            findings = self._findings_with_config(
                repo.root, '[check-config-defaults]\nTIMEOUT = "src/config.py:1"\n'
            )
        self.assertEqual(findings, [])

    def test_defaulting_to_phrase_is_detected(self) -> None:
        with Repo() as repo:
            repo.write("src/config.py", "TIMEOUT = 99\n")
            repo.write("README.md", "`TIMEOUT` defaulting to `30`\n")
            repo.commit()
            findings = self._findings_with_config(
                repo.root, '[check-config-defaults]\nTIMEOUT = "src/config.py:1"\n'
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("30", findings[0].message)

    def test_a_claim_inside_a_fenced_code_block_is_not_detected(self) -> None:
        with Repo() as repo:
            repo.write("src/config.py", "TIMEOUT = 99\n")
            repo.write(
                "README.md",
                "Example:\n\n```markdown\n`TIMEOUT` defaults to `30`.\n```\n",
            )
            repo.commit()
            findings = self._findings_with_config(
                repo.root, '[check-config-defaults]\nTIMEOUT = "src/config.py:1"\n'
            )
        self.assertEqual(findings, [])

    def test_a_claim_outside_a_fence_is_still_flagged(self) -> None:
        with Repo() as repo:
            repo.write("src/config.py", "TIMEOUT = 99\n")
            repo.write(
                "README.md",
                "```markdown\n`TIMEOUT` defaults to `99`.\n```\n\n"
                "`TIMEOUT` defaults to `30`.\n",
            )
            repo.commit()
            findings = self._findings_with_config(
                repo.root, '[check-config-defaults]\nTIMEOUT = "src/config.py:1"\n'
            )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "README.md:5")


if __name__ == "__main__":
    import unittest

    unittest.main()
