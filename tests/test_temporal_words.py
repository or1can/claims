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

"""Tests for the `temporal-words` check: `claims.checks.temporal_words`.

Exercises the shared `run(repo_root, diff_range, config)` seam, like every
sibling check's own tests. Ticket #52's acceptance criteria are what each
test here is derived from: the three modes, the two exemption polarities
(a backticked span and a fenced block suppress; a blockquote does not),
and the opt-in-by-omission `files` scope.
"""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from pathlib import Path

from claims.checks.temporal_words import (
    MODE_CITED,
    MODE_PHRASE,
    MODE_VERSION,
    NAME,
    check,
)
from claims.runner import Finding, register_check, run

from support import RegistryClearingTestCase, Repo


class TemporalWordsTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def _findings(self, repo_root: Path, config: Mapping[str, object]) -> list[Finding]:
        return list(run(repo_root, "HEAD", {NAME: config}).findings)

    def _added(self, repo: Repo, body: str, name: str = "reference.md") -> None:
        """`body` staged as the pending change to a committed file."""

        repo.write(name, "# reference\n\nseed\n")
        repo.commit()
        repo.write(name, "# reference\n\n" + body)

    def _modes(self, repo_root: Path, files: list[str] | None = None) -> list[str]:
        config: Mapping[str, object] = {} if files is None else {"files": files}
        return [f.mode for f in self._findings(repo_root, config)]

    # --- scope ---------------------------------------------------------

    def test_without_a_files_key_nothing_is_swept(self) -> None:
        with Repo() as repo:
            self._added(repo, "Released 1.2.3, and not documented yet.\n")

            findings = self._findings(repo.root, {})

        self.assertEqual(findings, [])

    def test_a_file_the_globs_do_not_name_is_not_read(self) -> None:
        with Repo() as repo:
            self._added(repo, "Released 1.2.3.\n", name="other.md")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [])

    def test_a_sentence_the_diff_did_not_add_is_not_read(self) -> None:
        with Repo() as repo:
            repo.write("reference.md", "# reference\n\nReleased 1.2.3.\n")
            repo.commit()
            repo.write("reference.md", "# reference\n\nReleased 1.2.3.\n\nA new line.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [])

    def test_a_glob_designates_a_whole_directory(self) -> None:
        with Repo() as repo:
            self._added(repo, "Released 1.2.3.\n", name="docs/guide.md")

            modes = self._modes(repo.root, ["docs/*.md"])

        self.assertEqual(modes, [MODE_VERSION])

    # --- severity and citation ------------------------------------------

    def test_every_finding_is_advisory(self) -> None:
        with Repo() as repo:
            self._added(repo, "Released 1.2.3, and not documented yet.\n")

            findings = self._findings(repo.root, {"files": ["reference.md"]})

        self.assertTrue(findings)
        self.assertFalse(any(f.gate for f in findings))

    def test_a_finding_cites_the_sentence_s_first_line_and_quotes_it(self) -> None:
        with Repo() as repo:
            self._added(repo, "The output mode\nis not written yet.\n")

            findings = self._findings(repo.root, {"files": ["reference.md"]})

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "reference.md:3")
        self.assertIn("The output mode is not written yet.", findings[0].message)

    # --- temporal-words-version -----------------------------------------

    def test_a_three_component_version_is_flagged(self) -> None:
        with Repo() as repo:
            self._added(repo, "Native TOML configuration arrived in 0.3.0.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [MODE_VERSION])

    def test_a_two_component_version_is_not_flagged(self) -> None:
        with Repo() as repo:
            self._added(repo, "Requires Docker 20.10 or later.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [])

    def test_a_hyphen_prefixed_version_is_flagged(self) -> None:
        # `claim-words`' own `(?<![\w-])` boundary would reject this one.
        with Repo() as repo:
            self._added(repo, "A pre-0.9.0 checkout has no such file.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [MODE_VERSION])

    def test_a_version_inside_a_backticked_span_is_not_flagged(self) -> None:
        with Repo() as repo:
            self._added(repo, "The image is `alpine:3.18.2` here.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [])

    def test_a_version_on_a_fenced_line_is_not_flagged(self) -> None:
        with Repo() as repo:
            self._added(repo, '```toml\nref = "1.2.3"\n```\n')

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [])

    def test_a_version_on_a_fence_delimiter_line_is_not_flagged(self) -> None:
        with Repo() as repo:
            self._added(repo, '```toml title="1.2.3"\nref = 1\n```\n')

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [])

    def test_a_version_inside_a_nested_fence_is_not_flagged(self) -> None:
        with Repo() as repo:
            self._added(repo, "````markdown\n```toml\nref = 1.2.3\n```\n````\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [])

    def test_a_version_after_the_fence_closes_is_flagged(self) -> None:
        with Repo() as repo:
            self._added(repo, "```toml\nref = 1\n```\n\nPinned at 1.2.3.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [MODE_VERSION])

    def test_a_version_ending_a_sentence_is_flagged(self) -> None:
        # The sentence's own full stop must not be read as a fourth
        # component that disqualifies the match.
        with Repo() as repo:
            self._added(repo, "Added in 0.9.0.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [MODE_VERSION])

    def test_a_version_inside_a_longer_dotted_token_is_not_flagged(self) -> None:
        # A left boundary that admits a hyphen must still reject a word
        # character and a dot, or every dotted identifier is a version.
        with Repo() as repo:
            self._added(repo, "Trace ids look like 99.1.2.3 in the log.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [])

    # --- temporal-words-phrase ------------------------------------------

    def test_each_listed_phrase_is_flagged(self) -> None:
        phrases = [
            "There is no output mode yet",
            "It is not yet written",
            "It used to read JSON",
            "The tree was flat before this existed",
            "It currently reads TOML",
            "Only Markdown is read today",
            "This first version reads Markdown",
            "It previously read JSON",
            "It historically read JSON",
            "Nothing has changed until now",
        ]
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                with Repo() as repo:
                    self._added(repo, phrase + ".\n")

                    modes = self._modes(repo.root, ["reference.md"])

                self.assertIn(MODE_PHRASE, modes)

    def test_a_phrase_fires_without_a_backticked_citation(self) -> None:
        with Repo() as repo:
            self._added(repo, "The reader is not written yet.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [MODE_PHRASE])

    def test_a_phrase_fires_beside_a_backticked_citation(self) -> None:
        with Repo() as repo:
            self._added(repo, "`ratect` has no `--output` mode yet.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [MODE_PHRASE])

    def test_no_longer_is_never_flagged(self) -> None:
        with Repo() as repo:
            self._added(repo, "Earthly is no longer maintained.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [])

    def test_a_phrase_inside_a_hyphenated_token_is_not_flagged(self) -> None:
        with Repo() as repo:
            self._added(repo, "Pass --today-only to narrow it.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [])

    def test_a_phrase_inside_a_backticked_span_is_not_flagged(self) -> None:
        with Repo() as repo:
            self._added(repo, "Run `claims today` to see it.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [])

    def test_a_phrase_is_matched_without_regard_to_case(self) -> None:
        with Repo() as repo:
            self._added(repo, "Currently the reader takes TOML.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [MODE_PHRASE])

    # --- temporal-words-cited -------------------------------------------

    def test_now_beside_a_backticked_citation_is_flagged(self) -> None:
        with Repo() as repo:
            self._added(repo, "`ratect` now reads its own configuration.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [MODE_CITED])

    def test_now_without_a_backticked_citation_is_not_flagged(self) -> None:
        with Repo() as repo:
            self._added(repo, "There are four tasks in the file now.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [])

    def test_now_inside_a_backticked_span_is_not_flagged(self) -> None:
        # The span it sits in is also the citation the gate looks for, so
        # a check that masked only for matching would fire on itself.
        with Repo() as repo:
            self._added(repo, "Pass `claims now` to skip the wait.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [])

    def test_until_now_beside_a_citation_fires_both_modes(self) -> None:
        # A sentence matching more than one mode is reported once per
        # mode, as `claim-words` does.
        with Repo() as repo:
            self._added(repo, "`ratect` had no reader until now.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(sorted(modes), sorted([MODE_PHRASE, MODE_CITED]))

    # --- retirement markers ---------------------------------------------

    def test_an_italics_wrapped_sentence_is_exempt(self) -> None:
        with Repo() as repo:
            self._added(repo, "*Ratect has no `--output` mode yet.*\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [])

    def test_a_previously_said_lead_in_is_exempt(self) -> None:
        with Repo() as repo:
            self._added(repo, "Previously said: there is no output mode yet.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [])

    def test_a_blockquoted_sentence_is_not_exempt(self) -> None:
        # ADR 0003: in reference prose a `>` is a callout carrying a live
        # claim, so this check does not honour that marker.
        with Repo() as repo:
            self._added(repo, "> **Status.** From 0.3.0 it reads TOML.\n")

            modes = self._modes(repo.root, ["reference.md"])

        self.assertEqual(modes, [MODE_VERSION])


if __name__ == "__main__":
    unittest.main()
