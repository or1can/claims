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

from claims.git import tracked_files

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


if __name__ == "__main__":
    unittest.main()
