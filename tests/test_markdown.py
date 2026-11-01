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

"""Tests for `claims.markdown`, the prose primitives checks share.

`fence_state` and `sentences_from` are exercised through the checks that
call them — `tests/test_check_file_refs.py` for nested and dangling
fences, `tests/test_claim_words.py` for soft-wrapped sentences — and were
moved here unchanged (ticket #52). What this file covers is
`mask_code_spans`, which has no such caller behind it yet, and how
`sentences_from` reads a table (#145) and which terminators it does not
end a sentence at (#154).
"""

from __future__ import annotations

import unittest

from claims.markdown import CODE_SPAN_RE, Sentence, mask_code_spans, section_range, sentences_from


class MaskCodeSpansTests(unittest.TestCase):
    def test_a_span_s_own_content_does_not_survive(self) -> None:
        self.assertNotIn("0.9.0", mask_code_spans("Pinned at `ratect 0.9.0` today."))

    def test_prose_outside_a_span_survives(self) -> None:
        masked = mask_code_spans("Pinned at `ratect 0.9.0` since 1.2.3.")
        self.assertIn("Pinned at ", masked)
        self.assertIn(" since 1.2.3.", masked)

    def test_the_backticks_survive_so_a_citation_is_still_findable(self) -> None:
        # A caller that masks in order to match prose may still need to ask
        # whether the sentence carries a citation at all.
        self.assertTrue(CODE_SPAN_RE.search(mask_code_spans("Run `claims` now.")))

    def test_length_is_preserved(self) -> None:
        text = "Two spans: `one` and `another`."
        self.assertEqual(len(mask_code_spans(text)), len(text))

    def test_every_span_is_masked_not_only_the_first(self) -> None:
        masked = mask_code_spans("`0.1.2` and `3.4.5`")
        self.assertNotIn("0.1.2", masked)
        self.assertNotIn("3.4.5", masked)

    def test_an_unclosed_backtick_masks_nothing(self) -> None:
        # One backtick opens no span in CommonMark either; there is nothing
        # to write over, and the text is returned as it came.
        self.assertEqual(mask_code_spans("A stray ` and 1.2.3"), "A stray ` and 1.2.3")


class SentencesFromTableTests(unittest.TestCase):
    def test_each_table_row_is_its_own_sentence_on_its_own_line(self) -> None:
        text = (
            "| # | Decision | Status |\n"
            "| --- | --- | --- |\n"
            "| 1 | Every binary shares one core | Accepted |\n"
            "| 2 | Use toml | Accepted |\n"
        )
        self.assertEqual(
            sentences_from(text),
            [
                Sentence("| # | Decision | Status |", 0, 0),
                Sentence("| 1 | Every binary shares one core | Accepted |", 2, 2),
                Sentence("| 2 | Use toml | Accepted |", 3, 3),
            ],
        )

    def test_the_delimiter_row_yields_nothing(self) -> None:
        self.assertEqual(
            sentences_from("| a | b |\n|:--|--:|\n| c | d |\n"),
            [Sentence("| a | b |", 0, 0), Sentence("| c | d |", 2, 2)],
        )

    def test_a_table_without_outer_pipes_is_recognised(self) -> None:
        self.assertEqual(
            sentences_from("a | b\n--- | ---\nc | d\ne | f\n"),
            [Sentence("a | b", 0, 0), Sentence("c | d", 2, 2), Sentence("e | f", 3, 3)],
        )

    def test_pipes_with_no_delimiter_row_after_them_are_not_a_table(self) -> None:
        self.assertEqual(
            sentences_from("Run a | b\nand c | d.\n"),
            [Sentence("Run a | b and c | d.", 0, 1)],
        )

    def test_a_table_directly_after_a_paragraph_line_does_not_join_it(self) -> None:
        self.assertEqual(
            sentences_from("The decisions are\n| a | b |\n| - | - |\n| c | d |\n"),
            [
                Sentence("The decisions are", 0, 0),
                Sentence("| a | b |", 1, 1),
                Sentence("| c | d |", 3, 3),
            ],
        )

    def test_a_table_ends_at_a_line_that_is_not_a_row(self) -> None:
        self.assertEqual(
            sentences_from("| a | b |\n| - | - |\n| c | d |\nThen prose\nwraps.\n"),
            [
                Sentence("| a | b |", 0, 0),
                Sentence("| c | d |", 2, 2),
                Sentence("Then prose wraps.", 3, 4),
            ],
        )


class SentencesFromSplitTests(unittest.TestCase):
    def test_a_listed_abbreviation_does_not_end_a_sentence(self) -> None:
        self.assertEqual(
            sentences_from("Colours (e.g. the exit code) are kept.\n"),
            [Sentence("Colours (e.g. the exit code) are kept.", 0, 0)],
        )
        self.assertEqual(
            sentences_from("A thing etc. is here.\n"),
            [Sentence("A thing etc. is here.", 0, 0)],
        )
        self.assertEqual(
            sentences_from("A thing etc. Is here.\n"),
            [Sentence("A thing etc. Is here.", 0, 0)],
        )

    def test_an_abbreviation_is_matched_without_regard_to_case(self) -> None:
        self.assertEqual(
            sentences_from("E.g. This one. Cf. That one.\n"),
            [Sentence("E.g. This one.", 0, 0), Sentence("Cf. That one.", 0, 0)],
        )

    def test_any_other_terminator_still_ends_a_sentence(self) -> None:
        self.assertEqual(
            sentences_from("It runs. Then it stops.\n"),
            [Sentence("It runs.", 0, 0), Sentence("Then it stops.", 0, 0)],
        )
        self.assertEqual(
            sentences_from("Use `a.b`. Next.\n"),
            [Sentence("Use `a.b`.", 0, 0), Sentence("Next.", 0, 0)],
        )
        self.assertEqual(
            sentences_from("*It runs.* Then [it](x.md) stops.\n"),
            [Sentence("*It runs.*", 0, 0), Sentence("Then [it](x.md) stops.", 0, 0)],
        )

    def test_a_terminator_before_a_lowercase_word_does_not_end_a_sentence(self) -> None:
        self.assertEqual(
            sentences_from("It ran fine. then\nit stopped.\n"),
            [Sentence("It ran fine. then it stopped.", 0, 1)],
        )

    def test_a_terminator_inside_link_text_does_not_end_a_sentence(self) -> None:
        self.assertEqual(
            sentences_from("See [Logging vs. output](x.md) for more.\n"),
            [Sentence("See [Logging vs. output](x.md) for more.", 0, 0)],
        )
        self.assertEqual(
            sentences_from("See [the guide. Then](x.md) more.\n"),
            [Sentence("See [the guide. Then](x.md) more.", 0, 0)],
        )

    def test_a_terminator_inside_a_code_span_does_not_end_a_sentence(self) -> None:
        self.assertEqual(
            sentences_from("Run `make. Then` here. Next.\n"),
            [Sentence("Run `make. Then` here.", 0, 0), Sentence("Next.", 0, 0)],
        )


PAGE = """# Page
intro
## A
a
## B
b
### B1
b1
## C
c
"""


class SectionRangeTests(unittest.TestCase):
    def test_a_section_ends_before_the_next_heading_of_its_own_level(self) -> None:
        self.assertEqual(section_range("## A\na\n## C\nc\n", "a"), (1, 2))

    def test_a_subsection_belongs_to_its_parent_section(self) -> None:
        self.assertEqual(section_range(PAGE, "b"), (5, 8))

    def test_a_subsection_is_a_section_of_its_own(self) -> None:
        self.assertEqual(section_range(PAGE, "b1"), (7, 8))

    def test_a_higher_level_heading_ends_a_section(self) -> None:
        self.assertEqual(section_range("### A\na\n# Top\n", "a"), (1, 2))

    def test_the_last_section_runs_to_the_end_of_the_file(self) -> None:
        self.assertEqual(section_range(PAGE, "c"), (9, 10))

    def test_an_anchor_naming_no_heading_has_no_section(self) -> None:
        self.assertIsNone(section_range(PAGE, "nope"))

    def test_a_heading_with_regex_metacharacters_slugs_like_check_links(self) -> None:
        self.assertEqual(section_range("## Why (a+b)?\nx\n## Next\n", "why-ab"), (1, 2))

    def test_a_hash_line_inside_a_fence_is_neither_a_heading_nor_a_boundary(self) -> None:
        text = "## A\n```sh\n# comment\n```\nafter\n## B\n"
        self.assertEqual(section_range(text, "a"), (1, 5))
        self.assertIsNone(section_range(text, "comment"))


if __name__ == "__main__":
    unittest.main()
