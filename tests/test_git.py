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

from claims.git import (
    DiffHunkStart,
    DiffLine,
    added_lines_by_file,
    iter_diff,
    tracked_files,
)

from support import Repo


class IterDiffTests(unittest.TestCase):
    def test_a_modified_file_yields_a_file_diff_with_both_paths(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", "one\n")
            repo.commit()
            repo.write("doc.md", "one\ntwo\n")

            file_diffs = list(iter_diff(repo.root, "HEAD"))

        self.assertEqual(len(file_diffs), 1)
        self.assertEqual((file_diffs[0].src, file_diffs[0].dst), ("doc.md", "doc.md"))

    def test_a_new_file_has_no_src(self) -> None:
        with Repo() as repo:
            repo.write("other.md", "unrelated\n")
            repo.commit()
            repo.write("doc.md", "one\n")

            file_diffs = list(iter_diff(repo.root, "HEAD"))

        self.assertEqual(len(file_diffs), 1)
        self.assertEqual((file_diffs[0].src, file_diffs[0].dst), (None, "doc.md"))

    def test_a_deleted_file_has_no_dst(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", "one\n")
            repo.commit()
            (repo.root / "doc.md").unlink()

            file_diffs = list(iter_diff(repo.root, "HEAD"))

        self.assertEqual(len(file_diffs), 1)
        self.assertEqual((file_diffs[0].src, file_diffs[0].dst), ("doc.md", None))

    def test_an_added_lines_content_starting_with_plus_plus_is_a_content_line(self) -> None:
        with Repo() as repo:
            repo.write("f.md", "one\n")
            repo.commit()
            repo.write("f.md", "one\n++i;\n")

            file_diffs = list(iter_diff(repo.root, "HEAD"))

        self.assertEqual(len(file_diffs), 1)
        self.assertEqual((file_diffs[0].src, file_diffs[0].dst), ("f.md", "f.md"))
        self.assertIn(DiffLine(sign="+", text="++i;"), file_diffs[0].body)

    def test_a_removed_lines_content_starting_with_dash_dash_is_a_content_line(self) -> None:
        with Repo() as repo:
            repo.write("f.sql", "a\n-- old\nb\n")
            repo.commit()
            repo.write("f.sql", "a\nb\n")

            file_diffs = list(iter_diff(repo.root, "HEAD"))

        self.assertEqual(len(file_diffs), 1)
        self.assertEqual((file_diffs[0].src, file_diffs[0].dst), ("f.sql", "f.sql"))
        self.assertIn(DiffLine(sign="-", text="-- old"), file_diffs[0].body)

    def test_a_quotable_filename_is_not_c_quoted(self) -> None:
        with Repo() as repo:
            repo.write("café.md", "one\n")
            repo.commit()
            repo.write("café.md", "one\ntwo\n")

            file_diffs = list(iter_diff(repo.root, "HEAD"))

        self.assertEqual(len(file_diffs), 1)
        self.assertEqual((file_diffs[0].src, file_diffs[0].dst), ("café.md", "café.md"))

    def test_a_non_default_diff_header_prefix_does_not_lose_paths(self) -> None:
        for config_key in ("diff.mnemonicPrefix", "diff.noprefix"):
            with self.subTest(config_key=config_key):
                with Repo() as repo:
                    repo.config(config_key, "true")
                    repo.write("doc.md", "one\n")
                    repo.commit()
                    repo.write("doc.md", "one\ntwo\n")

                    file_diffs = list(iter_diff(repo.root, "HEAD"))

                self.assertEqual(len(file_diffs), 1)
                self.assertEqual(
                    (file_diffs[0].src, file_diffs[0].dst), ("doc.md", "doc.md")
                )

    def test_two_files_each_get_their_own_file_diff(self) -> None:
        with Repo() as repo:
            repo.write("a.md", "one\n")
            repo.write("b.md", "one\n")
            repo.commit()
            repo.write("a.md", "one\ntwo\n")
            repo.write("b.md", "one\ntwo\n")

            file_diffs = list(iter_diff(repo.root, "HEAD"))

        self.assertEqual([(f.src, f.dst) for f in file_diffs], [("a.md", "a.md"), ("b.md", "b.md")])

    def test_a_hunk_start_gives_the_new_sides_first_line_number(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", "one\ntwo\nthree\n")
            repo.commit()
            repo.write("doc.md", "one\ntwo\nadded\nthree\n")

            file_diffs = list(iter_diff(repo.root, "HEAD"))

        self.assertEqual(len(file_diffs), 1)
        self.assertEqual(file_diffs[0].body[0], DiffHunkStart(new_start=3))

    def test_a_mode_only_change_has_no_paths_and_an_empty_body(self) -> None:
        # A mode-only change (`old mode`/`new mode`) has no `--- `/`+++ `
        # pair at all — same shape as a pure rename or a binary file, the
        # header-less case `FileDiff`'s own docstring calls out.
        with Repo() as repo:
            repo.write("doc.md", "unchanged content\n")
            repo.commit()
            (repo.root / "doc.md").chmod(0o755)

            file_diffs = list(iter_diff(repo.root, "HEAD"))

        self.assertEqual(len(file_diffs), 1)
        self.assertEqual(
            (file_diffs[0].src, file_diffs[0].dst, file_diffs[0].body), (None, None, [])
        )


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

    def test_a_filename_with_a_non_ascii_character_is_not_c_quoted(self) -> None:
        with Repo() as repo:
            repo.write("café.md", "text")
            files = tracked_files(repo.root)
        self.assertEqual(files, ["café.md"])


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

    def test_an_added_lines_content_starting_with_plus_plus_is_not_dropped(self) -> None:
        with Repo() as repo:
            repo.write("f.md", "one\n")
            repo.commit()
            repo.write("f.md", "one\n++i;\ntwo\n")

            added = added_lines_by_file(repo.root, "HEAD")

        self.assertEqual(added, {"f.md": {2, 3}})

    def test_an_added_line_after_a_removed_line_starting_with_dash_dash_is_not_dropped(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write("f.sql", "a\n-- old\nb\n")
            repo.commit()
            repo.write("f.sql", "a\nnewline\nb\n")

            added = added_lines_by_file(repo.root, "HEAD")

        self.assertEqual(added, {"f.sql": {2}})

    def test_a_deleted_file_later_in_the_diff_adds_no_phantom_line(self) -> None:
        with Repo() as repo:
            repo.write("a.md", "one\ntwo\n")
            repo.write("z.md", "gone\n")
            repo.commit()
            repo.write("a.md", "one\ntwo\nthree\n")
            (repo.root / "z.md").unlink()

            added = added_lines_by_file(repo.root, "HEAD")

        self.assertEqual(added, {"a.md": {3}})

    def test_a_quotable_filename_does_not_lose_or_misattribute_added_lines(self) -> None:
        with Repo() as repo:
            repo.write("normal.md", "one\ntwo\n")
            repo.write("café.md", "one\ntwo\n")
            repo.commit()
            repo.write("normal.md", "one\ntwo\nthree\n")
            repo.write("café.md", "one\ntwo\nthree\n")

            added = added_lines_by_file(repo.root, "HEAD")

        self.assertEqual(added, {"normal.md": {3}, "café.md": {3}})


if __name__ == "__main__":
    unittest.main()
