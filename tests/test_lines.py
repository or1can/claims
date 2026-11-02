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

"""Tests for `claims.lines`: a text's lines, numbered as git numbers them (#185)."""

from __future__ import annotations

import unittest

from claims.lines import git_lines


class GitLinesTests(unittest.TestCase):
    def test_only_a_newline_ends_a_line(self) -> None:
        for char in "\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029":
            with self.subTest(char=repr(char)):
                self.assertEqual(git_lines(f"a{char}b\nc\n"), [f"a{char}b", "c"])

    def test_a_crlf_line_loses_its_carriage_return(self) -> None:
        self.assertEqual(git_lines("a\r\nb\r\n"), ["a", "b"])

    def test_a_trailing_newline_gives_no_extra_empty_line(self) -> None:
        self.assertEqual(git_lines("a\n"), ["a"])
        self.assertEqual(git_lines("a\n\n"), ["a", ""])

    def test_a_last_line_without_a_newline_is_still_a_line(self) -> None:
        self.assertEqual(git_lines("a\nb"), ["a", "b"])

    def test_an_empty_string_gives_no_lines(self) -> None:
        self.assertEqual(git_lines(""), [])


if __name__ == "__main__":
    unittest.main()
