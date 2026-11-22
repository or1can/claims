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

"""Tests for folding approvals into the commits that wrote the marks (ADR
0017): `pending-marks --own` and `fold-approvals`."""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest import mock

from claims import fold
from claims.checked import Mark, marks_at
from claims.checks import claim_words
from claims.cli import main
from claims.runner import register_check

from support import RegistryClearingTestCase, Repo

CONFIG = '[claim-words]\nfiles = ["docs/*.md"]\n'


class FoldTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(claim_words.NAME, claim_words.check)
        self.repo = Repo().__enter__()
        self.addCleanup(self.repo.__exit__)
        self.repo.write("claims.toml", CONFIG)
        self.repo.write("README.md", "Readme.\n")
        self.repo.commit()
        self.base = self.rev("HEAD")

    def run_cli(self, *argv: str, stdin: str = "") -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch("sys.stdin", io.StringIO(stdin)),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            code = main([*argv, "--repo-root", str(self.repo.root)])
        return code, out.getvalue(), err.getvalue()

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(self.repo.root), *args], check=True, capture_output=True, text=True
        ).stdout

    def rev(self, name: str) -> str:
        return self.git("rev-parse", name).strip()

    def mark(self, entry: str, *, pending: bool = True, by: str = "agent") -> None:
        # Against the base, so a finding an earlier commit raised can be re-marked.
        argv = ["mark-checked", "--by", by, "--diff-range", self.base]
        if pending:
            argv.append("--pending")
        code, _, err = self.run_cli(*argv, "-", stdin=entry + "\n")
        self.assertEqual((code, err), (0, ""))

    def commit(self, message: str) -> str:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.rev("HEAD")

    def marks(self, commit: str) -> dict[str, Mark]:
        return {m.note: m for m in marks_at(self.repo.root, commit)}

    def doc(self, *sentences: str) -> None:
        self.repo.write("docs/a.md", "".join(f"{s}\n\n" for s in sentences))

    def test_pending_marks_own_lists_only_what_the_commit_added_or_re_marked(self) -> None:
        self.doc("Every check runs.", "Every rule holds.")
        self.mark("docs/a.md:1 claim-words-totalising read the runner")
        self.mark("docs/a.md:3 claim-words-totalising read the rules")
        self.commit("c1")
        self.doc("Every check runs.", "Every rule holds.", "Every test passes.")
        self.mark("docs/a.md:3 claim-words-totalising read the rules again")
        self.mark("docs/a.md:5 claim-words-totalising read the tests")
        self.commit("c2")

        code, out, err = self.run_cli("pending-marks", "--at", "HEAD", "--own")

        self.assertEqual((code, err), (1, ""))
        self.assertEqual(
            out,
            "docs/a.md:3 claim-words-totalising read the rules again (by agent)\n"
            "docs/a.md:5 claim-words-totalising read the tests (by agent)\n"
            "2 pending mark(s)\n",
        )
        self.assertEqual(self.run_cli("pending-marks", "--at", "HEAD")[1].splitlines()[-1], "3 pending mark(s)")

    def fold(self, *argv: str) -> tuple[int, str, str]:
        return self.run_cli("fold-approvals", self.base, "--by", "Kevin", *argv)

    def state(self) -> tuple[str, str, str]:
        return (
            self.git("for-each-ref"),
            self.rev("HEAD"),
            self.git("status", "--porcelain"),
        )

    def two_commits_two_entries(self) -> tuple[str, str]:
        self.doc("Every check runs.", "Every rule holds.")
        self.mark("docs/a.md:1 claim-words-totalising read the runner")
        c1 = self.commit("c1")
        self.mark("docs/a.md:3 claim-words-totalising read the rules")
        c2 = self.commit("c2")
        return c1, c2

    def test_a_preview_lists_each_commits_own_marks_and_fixups_and_changes_nothing(self) -> None:
        c1, c2 = self.two_commits_two_entries()
        self.mark("docs/a.md:1 claim-words-totalising read the runner closely")
        f = self.commit("fixup! c1")
        before = self.state()

        for argv in ((), ("--approve", c1)):
            code, out, err = self.fold(*argv)

            self.assertEqual((code, err), (0, ""))
            self.assertEqual(self.state(), before)
            lines = out.splitlines()
            self.assertEqual(
                lines[:5],
                [
                    f"{c1[:7]} c1",
                    "    docs/a.md:1 claim-words-totalising read the runner (by agent)",
                    f"    fixup {f[:7]} fixup! c1",
                    "        docs/a.md:1 claim-words-totalising read the runner closely (by agent)",
                    f"{c2[:7]} c2",
                ],
            )
            self.assertIn("    docs/a.md:3 claim-words-totalising read the rules (by agent)", lines)
            self.assertIn("nothing changed: this was a preview; add --apply to fold", lines)

    def test_each_refusal_exits_non_zero_and_rewrites_nothing(self) -> None:
        # Nothing pending in the range.
        self.doc("Every check runs.")
        self.mark("docs/a.md:1 claim-words-totalising read the runner", pending=False)
        self.commit("reviewed")
        before = self.state()
        code, _, err = self.fold("--approve", "HEAD", "--apply")
        self.assertEqual((code, self.state()), (1, before))
        self.assertIn("nothing is pending", err)

        c1, _ = self.two_commits_two_entries()

        # A dirty working tree.
        self.repo.write("README.md", "Changed.\n")
        before = self.state()
        code, _, err = self.fold("--approve", c1, "--apply")
        self.assertEqual((code, self.state()), (1, before))
        self.assertIn("working tree", err)
        self.git("checkout", "HEAD", "--", "README.md")

        # A fixup! for a commit outside the range.
        self.repo.write("README.md", "Changed.\n")
        self.commit("fixup! the initial commit")
        before = self.state()
        code, _, err = self.fold("--approve", c1, "--apply")
        self.assertEqual((code, self.state()), (1, before))
        self.assertIn("fixup! the initial commit", err)
        self.git("reset", "-q", "--hard", "HEAD~1")

        # A pending entry already at BASE.
        before = self.state()
        code, _, err = self.run_cli("fold-approvals", c1, "--by", "Kevin", "--apply")
        self.assertEqual((code, self.state()), (1, before))
        self.assertIn("pending", err)

        # A rebase in progress.
        self.git("checkout", "-q", "-b", "other", self.base)
        self.repo.write("docs/a.md", "Elsewhere.\n")
        self.commit("other")
        self.git("checkout", "-q", "-")
        self.assertNotEqual(
            subprocess.run(
                ["git", "-C", str(self.repo.root), "rebase", "-q", "other"], capture_output=True
            ).returncode,
            0,
        )
        before = self.state()
        code, _, err = self.fold("--approve", c1, "--apply")
        self.assertEqual((code, self.state()), (1, before))
        self.assertIn("rebase", err)

    def test_each_named_commit_has_its_own_entry_approved(self) -> None:
        c1, c2 = self.two_commits_two_entries()
        old = self.rev("HEAD")

        code, out, err = self.fold("--approve", c1, "--approve", c2, "--apply")

        self.assertEqual((code, err), (0, ""))
        new1, new2 = self.rev("HEAD~1"), self.rev("HEAD")
        self.assertEqual(
            {n: (m.pending, m.by, m.approved_by) for n, m in self.marks(new1).items()},
            {"read the runner": (False, "agent", "Kevin")},
        )
        self.assertEqual(
            {n: (m.pending, m.by, m.approved_by) for n, m in self.marks(new2).items()},
            {"read the runner": (False, "agent", "Kevin"), "read the rules": (False, "agent", "Kevin")},
        )
        branch = self.git("symbolic-ref", "--short", "HEAD").strip()
        self.assertIn(old, out)
        self.assertIn(f"git push --force-with-lease={branch}:{old}", out)
        # Never pushed: there is nowhere to push to, and nothing tried.
        self.assertEqual(self.git("remote"), "")

    def decoy(self) -> None:
        # A `claims` package that fails loudly the moment it is imported.
        self.repo.write("claims/__init__.py", "raise SystemExit('the decoy claims package was imported')\n")

    def test_a_claims_package_at_the_repository_root_is_not_what_the_rebase_runs(self) -> None:
        # A consuming project may hold a package of its own named `claims`,
        # and the rebase runs its steps from the repository root.
        self.decoy()
        self.repo.commit()
        self.base = self.rev("HEAD")
        c1, c2 = self.two_commits_two_entries()

        code, _, err = self.fold("--approve", c1, "--approve", c2, "--apply")

        self.assertEqual((code, err), (0, ""))
        self.assertEqual({m.approved_by for m in self.marks("HEAD").values()}, {"Kevin"})

    def test_a_fold_run_from_a_copy_the_rebase_rewinds_runs_that_copy_as_it_started(self) -> None:
        # This repository folds its own branches with its own checkout,
        # which each step of the rebase checks out at an older commit.
        self.decoy()
        self.repo.commit()
        self.base = self.rev("HEAD")
        c1, c2 = self.two_commits_two_entries()
        package = Path(fold.__file__).resolve().parent
        shutil.copytree(
            package, self.repo.root / "claims", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__")
        )
        self.commit("c3, carrying the real package")

        done = subprocess.run(
            [sys.executable, "-P", "-m", "claims.cli", "fold-approvals", self.base, "--by", "Kevin",
             "--approve", c1, "--approve", c2, "--apply", "--repo-root", str(self.repo.root)],
            cwd=self.repo.root,
            env={**os.environ, "PYTHONPATH": str(self.repo.root)},
            capture_output=True,
            text=True,
            timeout=120,
        )

        self.assertEqual((done.returncode, done.stderr), (0, ""))
        self.assertEqual({m.approved_by for m in self.marks("HEAD").values()}, {"Kevin"})

    def re_marked(self) -> tuple[str, str]:
        self.doc("Every check runs.")
        self.mark("docs/a.md:1 claim-words-totalising read the runner")
        c1 = self.commit("c1")
        self.mark("docs/a.md:1 claim-words-totalising read the runner again")
        c2 = self.commit("c2")
        return c1, c2

    def test_a_re_marked_entry_is_approved_in_each_named_commit_with_its_own_content(self) -> None:
        c1, c2 = self.re_marked()

        code, _, err = self.fold("--approve", c1, "--approve", c2, "--apply")

        self.assertEqual((code, err), (0, ""))
        self.assertEqual(
            [(m.note, m.pending, m.by, m.approved_by) for m in marks_at(self.repo.root, "HEAD~1")],
            [("read the runner", False, "agent", "Kevin")],
        )
        self.assertEqual(
            [(m.note, m.pending, m.by, m.approved_by) for m in marks_at(self.repo.root, "HEAD")],
            [("read the runner again", False, "agent", "Kevin")],
        )

    def test_a_re_mark_in_a_commit_not_named_stays_pending_and_is_reported(self) -> None:
        c1, _ = self.re_marked()

        code, out, err = self.fold("--approve", c1, "--apply")

        self.assertEqual((code, err), (0, ""))
        self.assertEqual(
            [(m.note, m.pending) for m in marks_at(self.repo.root, "HEAD~1")],
            [("read the runner", False)],
        )
        self.assertEqual(
            [(m.note, m.pending, m.by, m.approved_by) for m in marks_at(self.repo.root, "HEAD")],
            [("read the runner again", True, "agent", None)],
        )

    def test_an_entry_inherited_from_a_commit_not_named_stays_pending(self) -> None:
        c1, c2 = self.two_commits_two_entries()

        code, _, err = self.fold("--approve", c2, "--apply")

        self.assertEqual((code, err), (0, ""))
        self.assertEqual(
            {n: m.pending for n, m in self.marks(self.rev("HEAD")).items()},
            {"read the runner": True, "read the rules": False},
        )

    def test_a_fixup_is_folded_in_and_its_reading_approved(self) -> None:
        c1, _ = self.two_commits_two_entries()
        self.mark("docs/a.md:1 claim-words-totalising read the runner closely")
        self.commit(f"fixup! {c1[:10]}")

        code, _, err = self.fold("--approve", c1, "--apply")

        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.git("log", "--format=%s", f"{self.base}..HEAD").split(), ["c2", "c1"])
        self.assertEqual(
            [(m.note, m.pending, m.by, m.approved_by) for m in marks_at(self.repo.root, "HEAD~1")],
            [("read the runner closely", False, "agent", "Kevin")],
        )

    def test_a_bad_merge_result_resets_to_the_old_tip(self) -> None:
        c1, c2 = self.re_marked()
        old = self.state()

        with mock.patch("claims.fold.driver_command", return_value="printf '' > %A"):
            code, _, err = self.fold("--approve", c1, "--approve", c2, "--apply")

        self.assertEqual(code, 1)
        self.assertEqual(self.state(), old)
        self.assertIn("changed claims.checked.toml beyond approving marks", err)

    def test_an_ordinary_merge_after_a_fold_of_one_entry_edited_twice_still_conflicts(self) -> None:
        c1, c2 = self.re_marked()
        self.assertEqual(self.fold("--approve", c1, "--approve", c2, "--apply")[0], 0)
        self.git("checkout", "-q", "-b", "other", "HEAD~1")
        self.mark("docs/a.md:1 claim-words-totalising read the runner otherwise")
        self.commit("other")

        result = subprocess.run(
            ["git", "-C", str(self.repo.root), "merge", "-q", "-"], capture_output=True, text=True
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CONFLICT (content): Merge conflict in claims.checked.toml", result.stdout)

    def test_a_merge_result_dropping_a_by_line_resets_to_the_old_tip(self) -> None:
        c1, c2 = self.re_marked()
        old = self.state()
        strip_by = (
            f"{sys.executable} -c "
            "\"import re, sys; p = sys.argv[1]; s = open(p).read(); "
            "open(p, 'w').write(re.sub('by = .*\\\\n', '', s))\" %A"
        )

        real = fold.driver_command
        with mock.patch(
            "claims.fold.driver_command", side_effect=lambda parent: f"{real(parent)} && {strip_by}"
        ):
            code, _, err = self.fold("--approve", c1, "--apply")

        self.assertEqual(code, 1)
        self.assertEqual(self.state(), old)
        self.assertIn("changed claims.checked.toml beyond approving marks", err)

    def test_a_squash_or_amend_commit_a_merge_or_an_overriding_attribute_is_refused(self) -> None:
        c1, _ = self.two_commits_two_entries()
        for subject in ("squash! c1", "amend! c1"):
            self.repo.write("README.md", subject + "\n")
            self.commit(subject)
            before = self.state()
            code, _, err = self.fold("--approve", c1, "--apply")
            self.assertEqual((code, self.state()), (1, before))
            self.assertIn(subject, err)
            self.git("reset", "-q", "--hard", "HEAD~1")

        self.git("checkout", "-q", "-b", "side", "HEAD~1")
        self.repo.write("side.md", "Side.\n")
        self.commit("side")
        self.git("checkout", "-q", "-")
        self.git("merge", "-q", "--no-edit", "side")
        before = self.state()
        code, _, err = self.fold("--approve", c1, "--apply")
        self.assertEqual((code, self.state()), (1, before))
        self.assertIn("merge commit", err)
        self.git("reset", "-q", "--hard", "HEAD~1")

        self.repo.write(".gitattributes", "* merge=union\n")
        self.commit("attributes")
        before = self.state()
        code, _, err = self.fold("--approve", c1, "--apply")
        self.assertEqual((code, self.state()), (1, before))
        self.assertIn("merge attribute", err)

    def test_a_by_holding_a_newline_is_refused(self) -> None:
        self.two_commits_two_entries()
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.run_cli("fold-approvals", self.base, "--by", "a\nb")
