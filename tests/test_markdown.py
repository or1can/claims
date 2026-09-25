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

from claims.markdown import CODE_SPAN_RE, mask_code_spans


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


if __name__ == "__main__":
    unittest.main()
