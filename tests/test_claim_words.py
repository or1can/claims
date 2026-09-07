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

"""Tests for the `claim-words` check: `claims.checks.claim_words`.

Exercises the shared `run(repo_root, diff_range, config)` seam — see
spec.md's Testing Decisions, which name this check's fixtures as confirming
a quoted/retired false claim in a record-like file does not fire, per the
"house style for retiring a sentence" suppression rule. Ported from
Project B's `tools/claim-words.py` (same author, relicensed).
"""

from __future__ import annotations

from pathlib import Path

from claims.checks.claim_words import (
    MODE_ABOUT_ELSEWHERE,
    MODE_COUNTS,
    MODE_TOTALISING,
    NAME,
    check,
)
from claims.runner import Finding, register_check, run

from support import RegistryClearingTestCase, Repo


class ClaimWordsTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def _findings(self, repo_root: Path, files: list[str]) -> list[Finding]:
        return list(run(repo_root, "HEAD", {NAME: {"files": files}}).findings)

    def test_a_totalising_claim_past_a_table_is_flagged(self) -> None:
        with Repo() as repo:
            repo.write("record.md", "# record\n\nseed\n")
            repo.commit()
            repo.write(
                "record.md",
                "# record\n\n"
                "| host | status |\n"
                "|------|--------|\n"
                "| a    | up     |\n"
                "| b    | down   |\n\n"
                "Every host in the fleet reports up.\n",
            )

            findings = self._findings(repo.root, ["record.md"])

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "record.md:8")
        self.assertEqual(findings[0].mode, MODE_TOTALISING)

    def test_a_spelled_out_count_beyond_the_old_twelve_word_ceiling_is_flagged(self) -> None:
        with Repo() as repo:
            repo.write("record.md", "# record\n\nseed\n")
            repo.commit()
            repo.write("record.md", "# record\n\nFifty incidents were logged this quarter.\n")

            findings = self._findings(repo.root, ["record.md"])

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].mode, MODE_COUNTS)

    def test_a_digit_count_of_any_magnitude_is_flagged(self) -> None:
        with Repo() as repo:
            repo.write("record.md", "# record\n\nseed\n")
            repo.commit()
            repo.write("record.md", "# record\n\n1200 requests failed overnight.\n")

            findings = self._findings(repo.root, ["record.md"])

        self.assertEqual(len(findings), 1)
        self.assertIn("counts", findings[0].message)

    def test_a_byte_measurement_is_not_treated_as_a_tree_count(self) -> None:
        with Repo() as repo:
            repo.write("record.md", "# record\n\nseed\n")
            repo.commit()
            repo.write("record.md", "# record\n\nThe export grew to twelve megabytes overnight.\n")

            findings = self._findings(repo.root, ["record.md"])

        self.assertEqual(findings, [])

    def test_a_blockquoted_retired_claim_does_not_fire(self) -> None:
        with Repo() as repo:
            repo.write("record.md", "# record\n\nseed\n")
            repo.commit()
            repo.write(
                "record.md",
                "# record\n\n"
                "We used to write:\n\n"
                "> Every host in the fleet reports up.\n\n"
                "That was wrong; see the table above instead.\n",
            )

            findings = self._findings(repo.root, ["record.md"])

        self.assertFalse(any("totalising" in f.message for f in findings))

    def test_an_italicised_retired_claim_does_not_fire(self) -> None:
        with Repo() as repo:
            repo.write("record.md", "# record\n\nseed\n")
            repo.commit()
            repo.write(
                "record.md",
                "# record\n\n*Every host in the fleet reports up.* That was wrong.\n",
            )

            findings = self._findings(repo.root, ["record.md"])

        self.assertFalse(any("totalising" in f.message for f in findings))

    def test_a_lead_in_phrase_retired_claim_does_not_fire(self) -> None:
        with Repo() as repo:
            repo.write("record.md", "# record\n\nseed\n")
            repo.commit()
            repo.write(
                "record.md",
                "# record\n\nPreviously said: every host in the fleet reports up.\n",
            )

            findings = self._findings(repo.root, ["record.md"])

        self.assertFalse(any("totalising" in f.message for f in findings))

    def test_an_unmarked_quotation_of_a_retired_claim_still_fires(self) -> None:
        with Repo() as repo:
            repo.write("record.md", "# record\n\nseed\n")
            repo.commit()
            repo.write(
                "record.md",
                "# record\n\nWe used to write: every host in the fleet reports up.\n",
            )

            findings = self._findings(repo.root, ["record.md"])

        self.assertTrue(any("totalising" in f.message for f in findings))

    def test_a_file_not_designated_is_not_swept(self) -> None:
        with Repo() as repo:
            repo.write("notes.md", "seed\n")
            repo.commit()
            repo.write("notes.md", "Every host in the fleet reports up.\n")

            findings = self._findings(repo.root, ["record.md"])

        self.assertEqual(findings, [])

    def test_no_files_configured_returns_no_findings(self) -> None:
        with Repo() as repo:
            repo.write("record.md", "seed\n")
            repo.commit()
            repo.write("record.md", "Every host in the fleet reports up.\n")

            findings = list(run(repo.root, "HEAD", {NAME: {}}).findings)

        self.assertEqual(findings, [])

    def test_about_elsewhere_only_fires_beside_a_backticked_citation(self) -> None:
        with Repo() as repo:
            repo.write("record.md", "# record\n\nseed\n")
            repo.commit()
            repo.write(
                "record.md",
                "# record\n\n"
                "It would otherwise fail without a network path.\n\n"
                "`connect()` would otherwise fail without a network path.\n",
            )

            findings = self._findings(repo.root, ["record.md"])

        elsewhere = [f for f in findings if f.mode == MODE_ABOUT_ELSEWHERE]
        self.assertEqual(len(elsewhere), 1)
        self.assertIn("connect()", elsewhere[0].message)

    def test_a_sentence_matching_multiple_classes_gets_one_finding_per_mode(self) -> None:
        with Repo() as repo:
            repo.write("record.md", "# record\n\nseed\n")
            repo.commit()
            repo.write("record.md", "# record\n\nOnly twelve configs remain.\n")

            findings = self._findings(repo.root, ["record.md"])

        self.assertEqual({f.mode for f in findings}, {MODE_TOTALISING, MODE_COUNTS})
        self.assertTrue(all(f.citation == "record.md:3" for f in findings))

    def test_a_decade_measurement_is_not_treated_as_a_tree_count(self) -> None:
        with Repo() as repo:
            repo.write("record.md", "# record\n\nseed\n")
            repo.commit()
            repo.write("record.md", "# record\n\nThe design has held for three decades.\n")

            findings = self._findings(repo.root, ["record.md"])

        self.assertEqual(findings, [])

    def test_a_totalising_word_inside_a_hyphenated_identifier_is_not_flagged(self) -> None:
        with Repo() as repo:
            repo.write("record.md", "# record\n\nseed\n")
            repo.commit()
            repo.write(
                "record.md", "# record\n\nRun it with `--always-verify` enabled.\n"
            )

            findings = self._findings(repo.root, ["record.md"])

        self.assertEqual(findings, [])

    def test_a_no_space_threshold_marker_is_not_mistaken_for_a_blockquote(self) -> None:
        with Repo() as repo:
            repo.write("record.md", "# record\n\nseed\n")
            repo.commit()
            repo.write("record.md", "# record\n\n>5 hosts always fail the check.\n")

            findings = self._findings(repo.root, ["record.md"])

        self.assertTrue(any("totalising" in f.message for f in findings))

    def test_a_bare_string_files_config_is_one_pattern_not_every_character(self) -> None:
        with Repo() as repo:
            repo.write("record.md", "seed\n")
            repo.write("other.py", "seed\n")
            repo.commit()
            repo.write("record.md", "Every host in the fleet reports up.\n")
            repo.write("other.py", "# Every host in the fleet reports up.\n")

            findings = list(
                run(repo.root, "HEAD", {NAME: {"files": "record.md"}}).findings
            )

        self.assertTrue(all(f.file == "record.md" for f in findings))

    def test_findings_are_advisory_not_gating(self) -> None:
        with Repo() as repo:
            repo.write("record.md", "# record\n\nseed\n")
            repo.commit()
            repo.write("record.md", "# record\n\nEvery host in the fleet reports up.\n")

            findings = self._findings(repo.root, ["record.md"])

        self.assertTrue(findings)
        self.assertTrue(all(not f.gate for f in findings))


if __name__ == "__main__":
    import unittest

    unittest.main()
