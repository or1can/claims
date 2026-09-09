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

"""Tests for the `restatement` check: `claims.checks.restatement`.

Exercises the shared `run(repo_root, diff_range, config)` seam against a
fixture git repo, asserting on the returned `Finding` list — see spec.md's
Testing Decisions, which name this check's fixtures as exercising both
matching modes independently and confirming a paraphrase is correctly not
flagged. Ported from `ratect`'s `test_echoed_claims.py` (Apache-2.0 prior
art, same author) for the n-gram half.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from claims.checks.restatement import MODE_NGRAM, MODE_WHOLE_LINE, NAME, check
from claims.runner import Finding, register_check, run

from support import RegistryClearingTestCase, Repo


class RestatementTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def _findings(self, repo_root: Path, config: dict[str, object] | None = None) -> list[Finding]:
        return list(run(repo_root, "HEAD", {NAME: config or {}}).findings)

    def test_a_short_phrase_surviving_elsewhere_is_flagged_as_ngram(self) -> None:
        with Repo() as repo:
            repo.write("a.md", "the bridge interface differs for every network it creates\n")
            repo.write("b.md", "the bridge interface differs for every network Ratect creates\n")
            repo.commit()
            repo.write("a.md", "unrelated wording entirely\n")

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "b.md:1")
        self.assertEqual(findings[0].mode, MODE_NGRAM)

    def test_a_whole_line_surviving_elsewhere_is_flagged_as_whole_line(self) -> None:
        sentence = "binding a proxy to zero dot zero dot zero dot zero exposes it to everything\n"
        with Repo() as repo:
            repo.write("a.md", sentence)
            repo.write("b.md", sentence)
            repo.commit()
            repo.write("a.md", "an entirely different sentence about something else\n")

            findings = self._findings(repo.root)

        whole_line = [f for f in findings if f.mode == MODE_WHOLE_LINE]
        self.assertEqual(len(whole_line), 1)
        self.assertEqual(whole_line[0].citation, "b.md:1")

    def test_a_paraphrase_is_not_flagged(self) -> None:
        """The documented boundary: same fact, different wording, no
        verbatim overlap long enough for either mode to match."""
        with Repo() as repo:
            repo.write(
                "a.md",
                "the proxy rewrite only works on macOS and Windows today for every host\n",
            )
            repo.write(
                "b.md",
                "on macOS and on Windows the localhost rewriting feature is functional\n",
            )
            repo.commit()
            repo.write("a.md", "an entirely different sentence about something else\n")

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_text_the_diff_also_re_added_is_not_reported(self) -> None:
        """Reflow noise: rewrapping a paragraph removes and re-adds most of
        it, and a thing still said is not a thing retracted — for either
        mode."""
        kept = "binding a proxy to zero dot zero dot zero dot zero exposes it to everything\n"
        with Repo() as repo:
            repo.write("a.md", kept)
            repo.write("b.md", kept)
            repo.commit()
            repo.write(
                "a.md",
                "binding a proxy to zero dot zero dot zero dot zero\nexposes it to everything\n",
            )

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_an_unrelated_files_incidental_addition_does_not_cancel_a_real_retraction(
        self,
    ) -> None:
        """Regression: subtraction must happen per file, not across the
        whole diff — otherwise an unrelated file adding the same words in
        the same commit hides a genuine retraction elsewhere."""
        phrase = "the bridge interface differs for every network it creates\n"
        with Repo() as repo:
            repo.write("a.md", phrase)
            repo.write("c.md", phrase)
            repo.commit()
            repo.write("a.md", "unrelated wording entirely\n")
            # b.md incidentally adds the same words in the same commit —
            # must not cancel a.md's genuine retraction against c.md.
            repo.write("b.md", phrase)

            findings = self._findings(repo.root)

        self.assertTrue(
            any(f.citation == "c.md:1" for f in findings),
            f"c.md's surviving copy must still be flagged: {findings}",
        )

    def test_findings_are_advisory_not_gating(self) -> None:
        with Repo() as repo:
            repo.write("a.md", "the bridge interface differs for every network it creates\n")
            repo.write("b.md", "the bridge interface differs for every network Ratect creates\n")
            repo.commit()
            repo.write("a.md", "unrelated wording entirely\n")

            findings = self._findings(repo.root)

        self.assertTrue(findings)
        self.assertTrue(all(not f.gate for f in findings))

    def test_default_scope_covers_the_documented_union(self) -> None:
        phrase = "the bridge interface differs for every network it creates today\n"
        with Repo() as repo:
            repo.write("a.md", phrase)
            repo.write("b.swift", phrase)
            repo.write("c.py", phrase)
            repo.write("d.sh", phrase)
            repo.write("e.yml", phrase)
            repo.commit()
            repo.write("a.md", "unrelated wording entirely\n")

            findings = self._findings(repo.root)

        self.assertEqual(
            {f.file for f in findings}, {"b.swift", "c.py", "d.sh", "e.yml"}
        )

    def test_scope_outside_the_default_union_is_not_read(self) -> None:
        phrase = "the bridge interface differs for every network it creates today\n"
        with Repo() as repo:
            repo.write("a.md", phrase)
            repo.write("b.rs", phrase)
            repo.commit()
            repo.write("a.md", "unrelated wording entirely\n")

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_configured_extensions_add_to_the_default_union(self) -> None:
        phrase = "the bridge interface differs for every network it creates today\n"
        with Repo() as repo:
            repo.write("a.md", phrase)
            repo.write("b.rs", phrase)
            repo.commit()
            repo.write("a.md", "unrelated wording entirely\n")

            findings = self._findings(repo.root, config={"extensions": [".rs"]})

        self.assertTrue(findings)
        self.assertEqual({f.file for f in findings}, {"b.rs"})


if __name__ == "__main__":
    unittest.main()
