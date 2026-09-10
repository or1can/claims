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

"""Tests for the shared git helper: `claims.git`."""

from __future__ import annotations

import unittest

from claims.git import added_lines_by_file, tracked_files

from support import Repo


class TrackedFilesTests(unittest.TestCase):
    def test_a_filename_containing_a_space_is_not_split(self) -> None:
        with Repo() as repo:
            repo.write("release notes.md", "text")
            files = tracked_files(repo.root)
        self.assertEqual(files, ["release notes.md"])

    def test_a_pathspec_restricts_the_result(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", "text")
            repo.write("script.py", "text")
            files = tracked_files(repo.root, "*.md")
        self.assertEqual(files, ["doc.md"])

    def test_an_untracked_repo_returns_no_files(self) -> None:
        with Repo() as repo:
            files = tracked_files(repo.root)
        self.assertEqual(files, [])


class AddedLinesByFileTests(unittest.TestCase):
    def test_added_line_numbers_are_in_the_new_file(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", "one\ntwo\nthree\n")
            repo.commit()
            repo.write("doc.md", "one\ntwo\nadded\nthree\n")

            added = added_lines_by_file(repo.root, "HEAD")

        self.assertEqual(added, {"doc.md": {3}})

    def test_a_removed_only_line_adds_nothing(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", "one\ntwo\nthree\n")
            repo.commit()
            repo.write("doc.md", "one\nthree\n")

            added = added_lines_by_file(repo.root, "HEAD")

        self.assertEqual(added, {})

    def test_a_file_with_no_added_lines_is_absent(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", "text\n")
            repo.write("other.md", "text\n")
            repo.commit()
            repo.write("other.md", "text\nmore\n")

            added = added_lines_by_file(repo.root, "HEAD")

        self.assertEqual(added, {"other.md": {2}})

    def test_a_non_default_diff_header_prefix_does_not_lose_added_lines(self) -> None:
        for config_key in ("diff.mnemonicPrefix", "diff.noprefix"):
            with self.subTest(config_key=config_key):
                with Repo() as repo:
                    repo.config(config_key, "true")
                    repo.write("doc.md", "one\ntwo\nthree\n")
                    repo.commit()
                    repo.write("doc.md", "one\ntwo\nadded\nthree\n")

                    added = added_lines_by_file(repo.root, "HEAD")

                self.assertEqual(added, {"doc.md": {3}})


if __name__ == "__main__":
    unittest.main()
