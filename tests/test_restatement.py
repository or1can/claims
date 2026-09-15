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
from claims.config import load_config
from claims.runner import Finding, register_check, run

from support import RegistryClearingTestCase, Repo


class RestatementTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def _findings(self, repo_root: Path, config: dict[str, object] | None = None) -> list[Finding]:
        return list(run(repo_root, "HEAD", {NAME: config or {}}).findings)

    def _findings_with_toml(self, repo_root: Path, claims_toml: str) -> list[Finding]:
        (repo_root / "claims.toml").write_text(claims_toml)
        config = load_config(repo_root)
        return list(run(repo_root, "HEAD", config).findings)

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

    def test_a_non_default_diff_header_prefix_still_flags_a_retraction(self) -> None:
        # _diff_by_file goes through iter_diff, which pins --src-prefix/
        # --dst-prefix — this check's own coverage of that immunity, not
        # just relying on iter_diff's.
        sentence = "binding a proxy to zero dot zero dot zero dot zero exposes it to everything\n"
        for config_key in ("diff.mnemonicPrefix", "diff.noprefix"):
            with self.subTest(config_key=config_key):
                with Repo() as repo:
                    repo.config(config_key, "true")
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

            # duplication_threshold isn't under test here — b.md's own
            # survival alongside c.md would otherwise trip the default
            # threshold of 1 and suppress the very finding this test checks.
            findings = self._findings(
                repo.root, config={"duplication_threshold": 10}
            )

        self.assertTrue(
            any(f.citation == "c.md:1" for f in findings),
            f"c.md's surviving copy must still be flagged: {findings}",
        )

    def test_a_quotable_filenames_retraction_is_still_flagged(self) -> None:
        sentence = "binding a proxy to zero dot zero dot zero dot zero exposes it to everything\n"
        with Repo() as repo:
            repo.write("café.md", sentence)
            repo.write("b.md", sentence)
            repo.commit()
            repo.write("café.md", "an entirely different sentence about something else\n")

            findings = self._findings(repo.root)

        whole_line = [f for f in findings if f.mode == MODE_WHOLE_LINE]
        self.assertEqual(len(whole_line), 1)
        self.assertEqual(whole_line[0].citation, "b.md:1")

    def test_a_quotable_filenames_surviving_copy_is_still_flagged(self) -> None:
        """The other direction from `..._retraction_is_still_flagged`: the
        non-ASCII name is the file that keeps the sentence, not the one
        that drops it — `tracked_files` (used to read survivors, not the
        diff) must also see its real name, not a C-quoted string."""
        sentence = "binding a proxy to zero dot zero dot zero dot zero exposes it to everything\n"
        with Repo() as repo:
            repo.write("a.md", sentence)
            repo.write("café.md", sentence)
            repo.commit()
            repo.write("a.md", "an entirely different sentence about something else\n")

            findings = self._findings(repo.root)

        whole_line = [f for f in findings if f.mode == MODE_WHOLE_LINE]
        self.assertEqual(len(whole_line), 1)
        self.assertEqual(whole_line[0].citation, "café.md:1")

    def test_a_removed_line_starting_with_dash_dash_does_not_hide_a_later_retraction(
        self,
    ) -> None:
        sentence = "binding a proxy to zero dot zero dot zero dot zero exposes it to everything\n"
        with Repo() as repo:
            repo.write("a.md", "-- decorative\n" + sentence)
            repo.write("b.md", sentence)
            repo.commit()
            repo.write("a.md", "an entirely different sentence about something else\n")

            findings = self._findings(repo.root)

        whole_line = [f for f in findings if f.mode == MODE_WHOLE_LINE]
        self.assertEqual(len(whole_line), 1)
        self.assertEqual(whole_line[0].citation, "b.md:1")

    def test_an_added_line_starting_with_plus_plus_does_not_break_reflow_detection(
        self,
    ) -> None:
        """Mirrors `..._the_diff_also_re_added_is_not_reported`: the kept
        sentence is removed as one line and re-added rewrapped across two,
        in the same diff — a thing still said, not retracted. An unrelated
        `++ shout` added line sits ahead of the rewrap in the same hunk —
        `++ ` (with the trailing space), not bare `++`, is what collides
        with `iter_diff`'s own `"+++ "` match (space and all)."""
        kept = "binding a proxy to zero dot zero dot zero dot zero exposes it to everything\n"
        with Repo() as repo:
            repo.write("a.md", "intro\n" + kept)
            repo.commit()
            repo.write(
                "a.md",
                "intro\n++ shout\nbinding a proxy to zero dot zero dot zero dot zero\n"
                "exposes it to everything\n",
            )

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

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

            # duplication_threshold isn't under test here — 4 survivors
            # sharing one phrase would otherwise trip the default threshold.
            findings = self._findings(
                repo.root, config={"duplication_threshold": 10}
            )

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

    def test_a_bare_string_extensions_value_is_one_extension_not_its_characters(
        self,
    ) -> None:
        # `set(".rs")` (no coercion) silently becomes `{'.', 'r', 's'}`,
        # which would match nearly every file in the tree by a single
        # trailing character — asserting only `.py`/`.rs` files are swept
        # (not, say, a `.md` file merely ending in a character `.rs`
        # contains) pins the one-element-list coercion every other list
        # config already gets.
        phrase = "the bridge interface differs for every network it creates today\n"
        with Repo() as repo:
            repo.write("a.md", phrase)
            repo.write("b.rs", phrase)
            repo.commit()
            repo.write("a.md", "unrelated wording entirely\n")

            findings = self._findings(repo.root, config={"extensions": ".rs"})

        self.assertTrue(findings)
        self.assertEqual({f.file for f in findings}, {"b.rs"})

    def test_text_surviving_in_exactly_one_other_file_is_flagged_by_default(self) -> None:
        """The check's own documented tolerance: "the same fact can
        legitimately appear twice on purpose" — 2 total copies pre-diff
        (the edited file plus one survivor) still reports, matching
        `duplication_threshold`'s default of 1."""
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

    def test_text_surviving_in_several_other_files_is_suppressed_by_default(self) -> None:
        """The reported failure shape: a boilerplate block (here, a shared
        header line) duplicated across several files on purpose. Deleting
        one copy of many is not evidence of drift, so the default
        `duplication_threshold` of 1 suppresses it."""
        sentence = "binding a proxy to zero dot zero dot zero dot zero exposes it to everything\n"
        with Repo() as repo:
            repo.write("a.md", sentence)
            repo.write("b.md", sentence)
            repo.write("c.md", sentence)
            repo.write("d.md", sentence)
            repo.commit()
            repo.write("a.md", "an entirely different sentence about something else\n")

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_duplication_threshold_config_raises_the_cutoff(self) -> None:
        sentence = "binding a proxy to zero dot zero dot zero dot zero exposes it to everything\n"
        with Repo() as repo:
            repo.write("a.md", sentence)
            repo.write("b.md", sentence)
            repo.write("c.md", sentence)
            repo.write("d.md", sentence)
            repo.commit()
            repo.write("a.md", "an entirely different sentence about something else\n")

            findings = self._findings(repo.root, config={"duplication_threshold": 3})

        whole_line = [f for f in findings if f.mode == MODE_WHOLE_LINE]
        self.assertEqual(len(whole_line), 3)
        self.assertEqual({f.file for f in whole_line}, {"b.md", "c.md", "d.md"})

    def test_duplication_threshold_config_lowers_the_cutoff(self) -> None:
        sentence = "binding a proxy to zero dot zero dot zero dot zero exposes it to everything\n"
        with Repo() as repo:
            repo.write("a.md", sentence)
            repo.write("b.md", sentence)
            repo.commit()
            repo.write("a.md", "an entirely different sentence about something else\n")

            findings = self._findings(repo.root, config={"duplication_threshold": 0})

        self.assertEqual(findings, [])

    def test_a_non_integer_duplication_threshold_is_a_clear_crash_finding(self) -> None:
        # `runner.run()` catches any exception a check raises and turns it
        # into one gate finding — asserting the message names `ConfigError`
        # pins this as that documented path, not an opaque crash.
        with Repo() as repo:
            repo.write("a.md", "irrelevant\n")
            repo.commit()
            findings = self._findings(repo.root, config={"duplication_threshold": "1"})
        self.assertEqual(len(findings), 1)
        self.assertIn("ConfigError", findings[0].message)
        self.assertIn("duplication_threshold must be an integer", findings[0].message)

    def test_a_boolean_duplication_threshold_is_a_clear_crash_finding(self) -> None:
        # bool is an int subclass in Python — must be rejected explicitly,
        # not silently accepted as 0/1.
        with Repo() as repo:
            repo.write("a.md", "irrelevant\n")
            repo.commit()
            findings = self._findings(repo.root, config={"duplication_threshold": True})
        self.assertEqual(len(findings), 1)
        self.assertIn("ConfigError", findings[0].message)
        self.assertIn("duplication_threshold must be an integer", findings[0].message)

    def test_an_excluded_files_own_retraction_is_not_flagged(self) -> None:
        sentence = "binding a proxy to zero dot zero dot zero dot zero exposes it to everything\n"
        with Repo() as repo:
            repo.write("a.md", sentence)
            repo.write("b.md", sentence)
            repo.commit()
            repo.write("a.md", "an entirely different sentence about something else\n")

            findings = self._findings_with_toml(
                repo.root, '[restatement]\nexclude = ["a.md"]\n'
            )

        self.assertEqual(findings, [])

    def test_an_excluded_survivor_is_not_counted_or_reported(self) -> None:
        """`b.md` would push the survivor count to 2 (over the default
        threshold of 1) and would itself be a false citation — excluding
        it drops the count back to 1 (just `c.md`) and stops it being
        reported as a location."""
        sentence = "binding a proxy to zero dot zero dot zero dot zero exposes it to everything\n"
        with Repo() as repo:
            repo.write("a.md", sentence)
            repo.write("b.md", sentence)
            repo.write("c.md", sentence)
            repo.commit()
            repo.write("a.md", "an entirely different sentence about something else\n")

            findings = self._findings_with_toml(
                repo.root, '[restatement]\nexclude = ["b.md"]\n'
            )

        whole_line = [f for f in findings if f.mode == MODE_WHOLE_LINE]
        self.assertEqual(len(whole_line), 1)
        self.assertEqual(whole_line[0].citation, "c.md:1")


if __name__ == "__main__":
    unittest.main()
