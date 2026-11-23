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

"""The trees a claim of each kind is read at (ADR 0019, #267): a copy of
a commit's tree with no `.git`, and which commits a past or superseded
claim names."""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from claims.cli import main
from claims.trees import Tree, claim_trees, tree_copy

from support import Repo


def _rev(repo: Repo, rev: str = "HEAD") -> str:
    return subprocess.run(
        ["git", "-C", str(repo.root), "rev-parse", rev], capture_output=True, text=True, check=True
    ).stdout.strip()


def _cli(*argv: str) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


class TreeCopyTests(unittest.TestCase):
    def test_the_copy_holds_the_commits_tracked_files_and_no_git(self) -> None:
        with Repo() as repo:
            repo.write("a.md", "old\n")
            repo.write("sub/b.py", "x = 1\n")
            repo.commit()
            commit = _rev(repo)
            repo.write("a.md", "new\n")
            (repo.root / "untracked.txt").write_text("u\n")
            copy = tree_copy(repo.root, commit)
            self.assertEqual((copy / "a.md").read_text(), "old\n")
            self.assertEqual((copy / "sub" / "b.py").read_text(), "x = 1\n")
            self.assertFalse((copy / "untracked.txt").exists())
            self.assertFalse((copy / ".git").exists())
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(repo.root), "status", "--porcelain"],
                    capture_output=True, text=True, check=True,
                ).stdout,
                "M  a.md\n?? untracked.txt\n",
            )

    def test_the_copy_keeps_a_file_marked_export_ignore(self) -> None:
        with Repo() as repo:
            repo.write(".gitattributes", "notes.md export-ignore\n")
            repo.write("notes.md", "kept\n")
            repo.commit()
            self.assertEqual((tree_copy(repo.root, "HEAD") / "notes.md").read_text(), "kept\n")

    def test_the_copy_sits_in_the_work_tree_ignored_by_git(self) -> None:
        # Visible in an editor, as `.git/` is often not; ignored, so neither
        # `git status` nor a search that honours ignore files, hidden files
        # included, reads an old tree as the tree as it stands.
        with Repo() as repo:
            repo.write("a.md", "old\n")
            repo.commit()
            copy = tree_copy(repo.root, "HEAD")
            self.assertEqual(copy.parent, (repo.root / ".claims" / "trees").resolve())
            self.assertEqual((repo.root / ".claims" / ".gitignore").read_text(), "*\n")
            self.assertEqual(
                subprocess.run(
                    ["git", "-C", str(repo.root), "status", "--porcelain", "--ignored=no"],
                    capture_output=True, text=True, check=True,
                ).stdout,
                "",
            )

    def test_a_committed_claims_directory_is_refused_not_read_as_a_copy(self) -> None:
        # A project that commits `.claims/trees/<sha>/` would hand the reader
        # a forged old tree; one committing `.claims` as a symlink would
        # send the copy's writes outside the work tree.
        with Repo() as repo:
            repo.write("a.md", "real\n")
            repo.commit()
            commit = _rev(repo)
            repo.write(f".claims/trees/{commit}/a.md", "forged\n")
            repo.commit()
            with self.assertRaisesRegex(ValueError, "tracks .claims/"):
                tree_copy(repo.root, commit)

    def test_a_claims_symlink_is_refused(self) -> None:
        with Repo() as repo, tempfile.TemporaryDirectory() as elsewhere:
            repo.write("a.md", "real\n")
            repo.commit()
            (repo.root / ".claims").symlink_to(elsewhere)
            with self.assertRaisesRegex(ValueError, "symlink"):
                tree_copy(repo.root, "HEAD")
            self.assertEqual(list(Path(elsewhere).iterdir()), [])

    def test_the_copys_files_are_read_only(self) -> None:
        with Repo() as repo:
            repo.write("a.md", "old\n")
            repo.commit()
            copy = tree_copy(repo.root, _rev(repo))
            self.assertFalse(os.access(copy / "a.md", os.W_OK))

    def test_a_second_request_for_the_same_commit_reuses_the_copy(self) -> None:
        with Repo() as repo:
            repo.write("a.md", "old\n")
            repo.commit()
            commit = _rev(repo)
            first = tree_copy(repo.root, commit)
            marker = first / "left-by-the-first-copy"
            marker.write_text("")
            second = tree_copy(repo.root, "HEAD")
            self.assertEqual(second, first)
            self.assertTrue(marker.exists())

    def test_tree_at_prints_the_copys_path(self) -> None:
        with Repo() as repo:
            repo.write("a.md", "old\n")
            repo.commit()
            code, out, _ = _cli("tree-at", "HEAD", "--repo-root", str(repo.root))
            self.assertEqual(code, 0)
            self.assertEqual(out, f"{tree_copy(repo.root, _rev(repo))}\n")

    def test_tree_at_a_rev_naming_no_commit_fails(self) -> None:
        with Repo() as repo:
            repo.write("a.md", "old\n")
            repo.commit()
            code, _, err = _cli("tree-at", "nope", "--repo-root", str(repo.root))
            self.assertEqual(code, 2)
            self.assertIn("nope names no commit", err)


class PastClaimTreeTests(unittest.TestCase):
    def test_a_committed_line_is_read_at_its_commit_and_its_parent(self) -> None:
        with Repo() as repo:
            repo.write("adr.md", "# A\n")
            repo.commit()
            parent = _rev(repo)
            repo.write("adr.md", "# A\n\nTwo files name a moved path.\n")
            repo.commit()
            written = _rev(repo)
            repo.write("adr.md", "# A\n\nTwo files name a moved path.\n\nLater.\n")
            repo.commit()
            self.assertEqual(
                claim_trees(repo.root, "adr.md", 3, "past"),
                [Tree("written", written), Tree("before", parent)],
            )

    def test_an_uncommitted_line_is_read_in_the_working_tree_and_at_head(self) -> None:
        with Repo() as repo:
            repo.write("adr.md", "# A\n")
            repo.commit()
            head = _rev(repo)
            repo.write("adr.md", "# A\n\nNot yet committed.\n")
            self.assertEqual(
                claim_trees(repo.root, "adr.md", 3, "past"),
                [Tree("written", None), Tree("before", head)],
            )

    def test_a_line_in_the_root_commit_has_no_tree_before_it(self) -> None:
        with Repo() as repo:
            repo.write("adr.md", "# A\n")
            repo.commit()
            self.assertEqual(claim_trees(repo.root, "adr.md", 1, "past"), [Tree("written", _rev(repo))])

    def test_claim_trees_prints_each_tree_and_its_root(self) -> None:
        with Repo() as repo:
            repo.write("adr.md", "# A\n")
            repo.commit()
            head = _rev(repo)
            repo.write("adr.md", "# A\n\nNot yet committed.\n")
            code, out, _ = _cli(
                "claim-trees", "--kind", "past", "adr.md:3", "--repo-root", str(repo.root)
            )
            self.assertEqual(code, 0)
            self.assertEqual(
                out,
                f"written working-tree {repo.root.resolve()}\n"
                f"before {head} {tree_copy(repo.root, head)}\n",
            )


class SupersededClaimTreeTests(unittest.TestCase):
    def test_a_claim_is_read_just_before_the_commit_that_added_its_status_note(self) -> None:
        # ADR 0005's case: the Status note naming the replaced bullet came in
        # the commit that wrote ADR 0019, and the bullet is read just before it.
        with Repo() as repo:
            repo.write("0005.md", "# 0005\n\n## Status\n\nAccepted.\n")
            repo.commit()
            before = _rev(repo)
            repo.write("0005.md", "# 0005\n\n## Status\n\nAccepted.\n\nAmended by 0019: the live bullet is replaced.\n")
            repo.commit()
            superseding = _rev(repo)
            self.assertEqual(
                claim_trees(repo.root, "0005.md", 7, "superseded"),
                [Tree("superseded", superseding), Tree("before", before)],
            )

    def test_a_status_note_reworded_later_still_names_the_commit_that_first_added_it(self) -> None:
        # Blame on a note reworded after the change it records names the
        # rewording, and read just before that, the claim is already
        # replaced. (ADR 0004's Status line 5 shows blame moving: it came in
        # 00b497d and blame names bf4d64b, which extended it.)
        with Repo() as repo:
            status = "# 0004\n\n## Status\n\nAccepted.\n\n"
            repo.write("0004.md", status)
            repo.commit()
            before = _rev(repo)
            repo.write("0004.md", status + "Amended by 0019: the move\nis replaced.\n")
            repo.commit()
            superseding = _rev(repo)
            repo.write("0004.md", status + "Amended by 0019, #261: the move\nis replaced.\n")
            repo.commit()
            self.assertEqual(
                claim_trees(repo.root, "0004.md", 7, "superseded"),
                [Tree("superseded", superseding), Tree("before", before)],
            )

    def test_an_uncommitted_status_note_supersedes_in_the_working_tree(self) -> None:
        with Repo() as repo:
            repo.write("0005.md", "# 0005\n\nAccepted.\n")
            repo.commit()
            head = _rev(repo)
            repo.write("0005.md", "# 0005\n\nAccepted.\n\nReplaced by 0019.\n")
            self.assertEqual(
                claim_trees(repo.root, "0005.md", 5, "superseded"),
                [Tree("superseded", None), Tree("before", head)],
            )

    def test_an_uncommitted_superseding_note_prints_no_root_either(self) -> None:
        with Repo() as repo:
            repo.write("0005.md", "# 0005\n")
            repo.commit()
            head = _rev(repo)
            repo.write("0005.md", "# 0005\n\nReplaced by 0019.\n")
            code, out, _ = _cli(
                "claim-trees", "--kind", "superseded", "0005.md:3", "--repo-root", str(repo.root)
            )
            self.assertEqual(code, 0)
            self.assertEqual(out, f"superseded working-tree\nbefore {head} {tree_copy(repo.root, head)}\n")

    def test_a_subdirectory_repo_root_still_traces_the_note_to_its_first_commit(self) -> None:
        with Repo() as repo:
            status = "# 0004\n\nAccepted.\n\n"
            repo.write("decisions/0004.md", status)
            repo.commit()
            before = _rev(repo)
            repo.write("decisions/0004.md", status + "Replaced by\n0019.\n")
            repo.commit()
            superseding = _rev(repo)
            repo.write("decisions/0004.md", status + "Replaced by\n0019, #261.\n")
            repo.commit()
            self.assertEqual(
                claim_trees(repo.root / "decisions", "0004.md", 6, "superseded"),
                [Tree("superseded", superseding), Tree("before", before)],
            )

    def test_claim_trees_prints_the_superseding_commit_with_no_root(self) -> None:
        with Repo() as repo:
            repo.write("0005.md", "# 0005\n")
            repo.commit()
            before = _rev(repo)
            repo.write("0005.md", "# 0005\n\nReplaced by 0019.\n")
            repo.commit()
            superseding = _rev(repo)
            code, out, _ = _cli(
                "claim-trees", "--kind", "superseded", "0005.md:3", "--repo-root", str(repo.root)
            )
            self.assertEqual(code, 0)
            self.assertEqual(
                out, f"superseded {superseding}\nbefore {before} {tree_copy(repo.root, before)}\n"
            )

    def test_a_line_past_the_end_of_the_file_fails(self) -> None:
        with Repo() as repo:
            repo.write("0005.md", "# 0005\n")
            repo.commit()
            code, _, err = _cli(
                "claim-trees", "--kind", "past", "0005.md:9", "--repo-root", str(repo.root)
            )
            self.assertEqual(code, 2)
            self.assertIn("0005.md has no line 9", err)


if __name__ == "__main__":
    unittest.main()
