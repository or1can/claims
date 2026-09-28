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
`mask_code_spans`, which has no such caller behind it yet.
"""

from __future__ import annotations

import unittest

from claims.markdown import CODE_SPAN_RE, mask_code_spans, section_range


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
