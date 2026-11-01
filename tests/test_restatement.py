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

PHRASE = "the bridge interface differs for every network it creates today"


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

            findings = self._findings(repo.root)

        self.assertTrue(
            any(f.citation == "c.md:1" for f in findings),
            f"c.md's surviving copy must still be flagged: {findings}",
        )

    def test_text_moved_into_another_file_is_not_its_own_survivor(self) -> None:
        """A line the diff added was meant by whoever wrote it, so a
        sentence moved from one file into another is not reported at its
        new copy, in either mode."""
        sentence = "binding a proxy to zero dot zero dot zero dot zero exposes it to everything\n"
        with Repo() as repo:
            repo.write("a.md", "a heading\n" + sentence)
            repo.commit()
            repo.write("a.md", "a heading\n")
            repo.write("b.md", "other content entirely\n" + sentence)

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_an_untouched_copy_is_reported_when_another_copy_moved(self) -> None:
        """The moved copy is dropped before the duplication count, so it
        neither counts toward the threshold nor hides a real survivor."""
        sentence = "binding a proxy to zero dot zero dot zero dot zero exposes it to everything\n"
        with Repo() as repo:
            repo.write("a.md", sentence)
            repo.write("c.md", sentence)
            repo.commit()
            repo.write("a.md", "an entirely different sentence about something else\n")
            repo.write("b.md", sentence)

            findings = self._findings(repo.root)

        self.assertEqual({f.citation for f in findings}, {"c.md:1"})
        self.assertEqual({f.mode for f in findings}, {MODE_NGRAM, MODE_WHOLE_LINE})

    def test_only_the_untouched_line_is_reported_in_a_file_the_diff_also_added_to(
        self,
    ) -> None:
        """A survivor the diff didn't add is still one, even in a file the
        diff changed."""
        sentence = "binding a proxy to zero dot zero dot zero dot zero exposes it to everything\n"
        with Repo() as repo:
            repo.write("a.md", sentence)
            repo.write("c.md", "a heading\n" + sentence)
            repo.commit()
            repo.write("a.md", "an entirely different sentence about something else\n")
            repo.write("c.md", "a heading\n" + sentence + "a paragraph\n" + sentence)

            findings = self._findings(repo.root)

        self.assertEqual({f.citation for f in findings}, {"c.md:2"})
        self.assertEqual({f.mode for f in findings}, {MODE_NGRAM, MODE_WHOLE_LINE})

    def test_an_added_copy_ahead_of_an_untouched_one_does_not_hide_it(self) -> None:
        """The n-gram sweep must not settle on a run's first occurrence in
        a file when that occurrence is a line the diff added."""
        with Repo() as repo:
            repo.write("a.md", f"{PHRASE}\n")
            repo.write("c.md", f"a heading\na paragraph\nas noted {PHRASE} indeed\n")
            repo.commit()
            repo.write("a.md", "unrelated wording entirely\n")
            repo.write(
                "c.md",
                f"a heading\nso {PHRASE} too\nnew text\na paragraph\nas noted {PHRASE} indeed\n",
            )

            findings = self._findings(repo.root)

        self.assertEqual([(f.citation, f.mode) for f in findings], [("c.md:5", MODE_NGRAM)])

    def test_a_survivor_wrapping_onto_a_line_the_diff_edited_is_reported(self) -> None:
        """Only a run lying wholly on added lines is the diff's own; one
        that starts on an untouched line is still a survivor there."""
        with Repo() as repo:
            repo.write("a.md", "alpha beta gamma delta epsilon zeta eta\n")
            repo.write("b.md", "a heading\n\nas noted alpha beta gamma\ndelta epsilon zeta tail one\n")
            repo.commit()
            repo.write("a.md", "unrelated wording entirely\n")
            repo.write("b.md", "a heading\n\nas noted alpha beta gamma\ndelta epsilon zeta tail two\n")

            findings = self._findings(repo.root)

        self.assertEqual([(f.citation, f.mode) for f in findings], [("b.md:3", MODE_NGRAM)])

    def test_a_last_line_that_only_gained_a_newline_is_still_a_survivor(self) -> None:
        """Git shows an old last line with no newline as removed and
        re-added when something is appended after it, though its text
        never changed."""
        sentence = "binding a proxy to zero dot zero dot zero dot zero exposes it to everything"
        with Repo() as repo:
            repo.write("a.md", f"{sentence}\n")
            repo.write("b.md", f"a heading\n\n{sentence}")
            repo.commit()
            repo.write("a.md", "an entirely different sentence about something else\n")
            repo.write("b.md", f"a heading\n\n{sentence}\n\nan appended paragraph\n")

            findings = self._findings(repo.root)

        self.assertEqual({f.citation for f in findings}, {"b.md:3"})
        self.assertEqual({f.mode for f in findings}, {MODE_NGRAM, MODE_WHOLE_LINE})

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
            repo.write("b.swift", "// " + phrase)
            repo.write("c.py", "# " + phrase)
            repo.write("d.sh", "# " + phrase)
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
            repo.write("b.rs", "// " + phrase)
            repo.commit()
            repo.write("a.md", "unrelated wording entirely\n")

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_configured_extensions_add_to_the_default_union(self) -> None:
        phrase = "the bridge interface differs for every network it creates today\n"
        with Repo() as repo:
            repo.write("a.md", phrase)
            repo.write("b.rs", "// " + phrase)
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
            repo.write("b.rs", "// " + phrase)
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

    def test_a_code_line_removed_from_a_source_file_is_not_a_retraction(self) -> None:
        """The triage repro: in a source file only comment text is prose,
        so identical code surviving in another source file is nothing."""
        code = "result = compute_the_value(alpha, beta, gamma, delta)\n"
        with Repo() as repo:
            repo.write("a.py", code)
            repo.write("b.py", code)
            repo.commit()
            repo.write("a.py", "pass\n")

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def _survivor_citations(self, survivor: str, text: str, **config: object) -> set[str]:
        """Citations reported when `a.md` drops `PHRASE` and `survivor`
        holds `text`."""
        with Repo() as repo:
            repo.write("a.md", PHRASE + "\n")
            repo.write(survivor, text)
            repo.commit()
            repo.write("a.md", "unrelated wording entirely\n")

            return {f.citation for f in self._findings(repo.root, config=dict(config))}

    def test_comment_text_surviving_in_a_source_file_is_reported(self) -> None:
        cases = {
            "hash comment": ("b.py", f"x = 1\n# {PHRASE}\n", "b.py:2"),
            "trailing comment": ("b.py", f"x = 1  # {PHRASE}\n", "b.py:1"),
            "shell comment": ("b.sh", f"echo hi\n# {PHRASE}\n", "b.sh:2"),
            "docstring": ("b.py", f'def f():\n    """Intro.\n\n    {PHRASE}\n    """\n', "b.py:4"),
            "prefixed docstring": ("b.py", f'R"""{PHRASE}"""\n', "b.py:1"),
            "single-quoted docstring": ("b.py", f"'''\n{PHRASE}\n'''\n", "b.py:2"),
            "rust outer doc": ("b.rs", f"/// {PHRASE}\nfn f() {{}}\n", "b.rs:1"),
            "rust inner doc": ("b.rs", f"//! {PHRASE}\n", "b.rs:1"),
            "rust line comment": ("b.rs", f"let x = 1; // {PHRASE}\n", "b.rs:1"),
            "swift block": ("b.swift", f"/*\n * {PHRASE}\n */\nlet x = 1\n", "b.swift:2"),
            "rust nested block": (
                "b.rs",
                f"/* outer /* inner */\n{PHRASE}\n*/\nfn f() {{}}\n",
                "b.rs:2",
            ),
        }
        for name, (survivor, text, citation) in cases.items():
            with self.subTest(name):
                self.assertEqual(
                    self._survivor_citations(survivor, text, extensions=[".rs"]),
                    {citation},
                )

    def test_code_in_a_source_file_contributes_no_words(self) -> None:
        cases = {
            "shell parameter expansion": ("b.sh", f"echo ${{x#{PHRASE}}}\n"),
            "shell argument count": ("b.sh", f"echo $# {PHRASE}\n"),
            "url in code": ("b.rs", f'let u = "http://{PHRASE.replace(" ", "/")}";\n'),
            "shebang": ("b.sh", f"#!/usr/bin/env {PHRASE}\n"),
            "assigned triple-quoted string": ("b.py", f'x = """{PHRASE}"""\n'),
            "hash inside a python string": ("b.py", f'x = "see # {PHRASE}"\n'),
            "code after an assigned string's close": (
                "b.py",
                f'x = """\n"""\n{PHRASE.replace(" ", "_")} = 1\n',
            ),
            "code after a nested block's true close": (
                "b.rs",
                f"/* a /* b */ c */ let {PHRASE.replace(' ', '_')} = 1;\n",
            ),
        }
        for name, (survivor, text) in cases.items():
            with self.subTest(name):
                self.assertEqual(
                    self._survivor_citations(survivor, text, extensions=[".rs"]), set()
                )

    def test_a_retraction_from_a_source_comment_is_reported(self) -> None:
        cases = {
            "hash comment": ("a.py", f"x = 1\n# {PHRASE}\n", "x = 1\n"),
            "docstring": ("a.py", f'"""\n{PHRASE}\n"""\n', '"""\n"""\n'),
            "rust line comment": ("a.rs", f"// {PHRASE}\n", "\n"),
            "rust outer doc": ("a.rs", f"/// {PHRASE}\nfn f() {{}}\n", "fn f() {}\n"),
            "trailing comment": ("a.py", f"x = 1  # {PHRASE}\n", "x = 1\n"),
            "swift block": ("a.swift", f"/*\n{PHRASE}\n*/\n", "/*\n*/\n"),
        }
        for name, (edited, before, after) in cases.items():
            with self.subTest(name):
                with Repo() as repo:
                    repo.write(edited, before)
                    repo.write("b.md", PHRASE + "\n")
                    repo.commit()
                    repo.write(edited, after)

                    findings = self._findings(repo.root, config={"extensions": [".rs"]})

                self.assertEqual({f.citation for f in findings}, {"b.md:1"})

    def test_a_comment_retraction_surviving_in_another_files_comment_is_reported(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write("a.rs", f"// {PHRASE}\nfn f() {{}}\n")
            repo.write("b.py", f'"""{PHRASE}"""\n')
            repo.commit()
            repo.write("a.rs", "fn f() {}\n")

            findings = self._findings(repo.root, config={"extensions": [".rs"]})

        self.assertEqual({f.citation for f in findings}, {"b.py:1"})

    def test_a_triple_quote_inside_a_one_line_string_opens_nothing(self) -> None:
        cases = {
            "double-quoted": f"x = '\"\"\"'\n# {PHRASE}\n",
            "single-quoted": f"x = \"'''\"\n# {PHRASE}\n",
            "escaped in a raw string": f'x = r"\\"\\"\\"|\'\'\'"\n# {PHRASE}\n',
        }
        for name, text in cases.items():
            with self.subTest(name):
                self.assertEqual(self._survivor_citations("b.py", text), {"b.py:2"})

    def test_an_escaped_triple_quote_does_not_end_a_docstring(self) -> None:
        text = f'"""Quote \\""" here.\n{PHRASE}\n"""\n'
        self.assertEqual(self._survivor_citations("b.py", text), {"b.py:2"})

    def test_a_removed_line_inside_a_comment_opened_outside_the_hunk_is_comment_text(
        self,
    ) -> None:
        """Classified in the context of the whole old file: the hunk holds
        only the removed middle line, whose opener is lines above it."""
        cases = {
            "docstring": ("a.py", '"""Intro.\n\n{}\n\nOutro.\n"""\nx = 1\n'),
            "block comment": ("a.rs", "/*\n * Intro.\n *\n * {}\n *\n * Outro.\n */\n"),
        }
        for name, (edited, template) in cases.items():
            with self.subTest(name):
                with Repo() as repo:
                    repo.write(edited, template.format(PHRASE))
                    repo.write("b.md", PHRASE + "\n")
                    repo.commit()
                    repo.write(edited, template.format("unrelated wording entirely"))

                    findings = self._findings(repo.root, config={"extensions": [".rs"]})

                self.assertEqual({f.citation for f in findings}, {"b.md:1"})

    def test_a_docstring_retraction_surviving_in_markdown_is_reported(self) -> None:
        with Repo() as repo:
            repo.write("a.py", f'"""{PHRASE}"""\n')
            repo.write("b.md", PHRASE + "\n")
            repo.commit()
            repo.write("a.py", '"""Something else."""\n')

            findings = self._findings(repo.root)

        self.assertEqual({f.citation for f in findings}, {"b.md:1"})

    def test_whole_line_mode_compares_only_a_lines_comment_portion(self) -> None:
        sentence = "binding a proxy to zero dot zero dot zero dot zero exposes it to everything"
        with Repo() as repo:
            repo.write("a.md", sentence + "\n")
            repo.write("b.py", f"proxy.bind(host)  # {sentence}\n")
            repo.commit()
            repo.write("a.md", "an entirely different sentence about something else\n")

            findings = self._findings(repo.root)

        whole_line = [f for f in findings if f.mode == MODE_WHOLE_LINE]
        self.assertEqual([f.citation for f in whole_line], ["b.py:1"])

    def test_an_extension_with_no_comment_syntax_is_read_whole_line(self) -> None:
        self.assertEqual(
            self._survivor_citations(
                "b.ts", f"const s = '{PHRASE}';\n", extensions=[".ts"]
            ),
            {"b.ts:1"},
        )


if __name__ == "__main__":
    unittest.main()
