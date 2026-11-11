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

"""Tests for the `stale-claims` check: `claims.checks.stale_claims`.

Exercises the shared `run(repo_root, diff_range, config)` seam against a
fixture git repo with controlled commit timestamps, asserting on the
returned `Finding` list — see spec.md's Testing Decisions. Ported from
`ratect`'s `stale-claims.py` (Apache-2.0 prior art, same author),
generalised beyond its Rust-specific subject patterns.
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import unittest
from pathlib import Path

from claims.checks.stale_claims import NAME, check
from claims.cli import main
from claims.config import load_config
from claims.runner import Finding, register_check, run

from support import RegistryClearingTestCase, Repo

BASE = 1_700_000_000

DOC = """## stale
See src/subject.py for details.

## less-churny
See src/quiet.py for details.

## moved
See src/moved.py for details.
"""

DOC_AFTER_MOVE = """## stale
See src/subject.py for details.

## less-churny
See src/quiet.py for details.

## moved
See src/moved.py for the full picture.
"""


def _build_fixture(repo: Repo) -> None:
    # Commit 0: the claim (doc.md) and its three subjects, all together.
    repo.write("doc.md", DOC)
    repo.write("src/subject.py", "v0")
    repo.write("src/quiet.py", "v0")
    repo.write("src/moved.py", "v0")
    repo.commit(BASE)

    # subject.py churns three times after the claim's only touch (commit 0)
    # — genuinely stale: 3 of its 4 commits postdate the claim.
    repo.write("src/subject.py", "v1")
    repo.commit(BASE + 100)
    repo.write("src/subject.py", "v2")
    repo.commit(BASE + 200)
    repo.write("src/subject.py", "v3")
    repo.commit(BASE + 300)

    # quiet.py churns once after the claim — stale, but less so.
    repo.write("src/quiet.py", "v1")
    repo.commit(BASE + 400)

    # moved.py and the "moved" section of doc.md change in the same commit
    # — the same-commit-move blind spot the check documents.
    repo.write("doc.md", DOC_AFTER_MOVE)
    repo.write("src/moved.py", "v1")
    repo.commit(BASE + 500)


def _audit_range(repo_root: Path) -> str:
    """The first commit `..HEAD`: the wide range a whole-tree audit runs over."""

    root = subprocess.run(
        ["git", "-C", str(repo_root), "rev-list", "--max-parents=0", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return f"{root}..HEAD"


def _heading(finding: Finding) -> str:
    """The heading a finding's message names, between its first quotes."""

    return finding.message.split("'")[1]


class StaleClaimsTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def _findings(self, repo_root: Path) -> list[Finding]:
        return list(run(repo_root, _audit_range(repo_root), {}).findings)

    def _findings_with_toml(
        self, repo_root: Path, claims_toml: str, diff_range: str | None = None
    ) -> list[Finding]:
        (repo_root / "claims.toml").write_text(claims_toml)
        config = load_config(repo_root)
        return list(run(repo_root, diff_range or _audit_range(repo_root), config).findings)

    def test_the_most_churned_subject_ranks_first(self) -> None:
        with Repo() as repo:
            _build_fixture(repo)
            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].citation, "doc.md:1")
        self.assertIn("subject.py", findings[0].message)
        self.assertEqual(findings[1].citation, "doc.md:4")
        self.assertIn("quiet.py", findings[1].message)

    def test_a_range_changing_no_subject_reports_nothing(self) -> None:
        with Repo() as repo:
            _build_fixture(repo)
            repo.write("unrelated.txt", "v0")
            repo.commit(BASE + 600)
            self.assertEqual(len(self._findings(repo.root)), 2)
            self.assertEqual(list(run(repo.root, "HEAD~1", {}).findings), [])
            # Editing the citing page itself touches none of its subjects.
            repo.write("doc.md", DOC_AFTER_MOVE + "\nMore.\n")
            self.assertEqual(list(run(repo.root, "HEAD", {}).findings), [])

    def test_a_range_changing_a_subject_ranks_its_section_with_the_same_score(
        self,
    ) -> None:
        with Repo() as repo:
            _build_fixture(repo)
            audit = self._findings(repo.root)
            # BASE + 400 changed quiet.py; BASE + 500 the "moved" pair.
            scoped = list(run(repo.root, "HEAD~2", {}).findings)
        self.assertEqual(scoped, [audit[1]])

    def test_sections_in_scope_keep_their_relative_order(self) -> None:
        with Repo() as repo:
            _build_fixture(repo)
            # BASE + 300 changed subject.py, BASE + 400 quiet.py.
            scoped = list(run(repo.root, "HEAD~3", {}).findings)
        self.assertEqual([f.citation for f in scoped], ["doc.md:1", "doc.md:4"])

    def test_a_pure_rename_puts_a_section_naming_the_new_path_in_scope(self) -> None:
        with Repo() as repo:
            repo.write("guide.md", "## cache\nSee `cache` for details.\n")
            repo.write("src/cache.py", "v0")
            repo.commit(BASE)
            (repo.root / "lib").mkdir()
            subprocess.run(
                ["git", "-C", str(repo.root), "mv", "src/cache.py", "lib/cache.py"],
                check=True,
            )
            repo.commit(BASE + 100)
            findings = list(run(repo.root, "HEAD~1", {}).findings)
        self.assertEqual(len(findings), 1)
        self.assertIn("cache.py 1 commit", findings[0].message)

    def test_a_deleted_subject_puts_its_section_in_scope(self) -> None:
        with Repo() as repo:
            _build_fixture(repo)
            # Unstaged: still in the index.
            (repo.root / "src/quiet.py").unlink()
            unstaged = list(run(repo.root, "HEAD", {}).findings)
            # Staged, as the commit hook meets it: no longer tracked.
            repo.rm("src/quiet.py")
            staged = list(run(repo.root, "HEAD", {}).findings)
            repo.commit(BASE + 600)
            committed = list(run(repo.root, "HEAD~1", {}).findings)
        self.assertEqual([f.citation for f in unstaged], ["doc.md:4"])
        self.assertEqual([f.citation for f in staged], ["doc.md:4"])
        self.assertEqual([f.citation for f in committed], ["doc.md:4"])
        self.assertIn("quiet.py 2 commits", committed[0].message)

    def test_a_rename_puts_a_section_naming_the_old_path_in_scope(self) -> None:
        with Repo() as repo:
            _build_fixture(repo)
            subprocess.run(
                ["git", "-C", str(repo.root), "mv", "src/quiet.py", "src/calm.py"],
                check=True,
            )
            findings = list(run(repo.root, "HEAD", {}).findings)
        self.assertEqual([f.citation for f in findings], ["doc.md:4"])

    def test_findings_are_advisory_not_gating(self) -> None:
        with Repo() as repo:
            _build_fixture(repo)
            findings = self._findings(repo.root)

        self.assertTrue(findings)
        self.assertTrue(all(not f.gate for f in findings))

    def test_a_same_commit_claim_and_subject_move_scores_no_finding(self) -> None:
        with Repo() as repo:
            _build_fixture(repo)
            findings = self._findings(repo.root)

        self.assertFalse(any(f.citation == "doc.md:7" for f in findings))

    def test_changelog_is_excluded(self) -> None:
        with Repo() as repo:
            _build_fixture(repo)
            repo.write("CHANGELOG.md", DOC)
            repo.commit(BASE + 600)
            findings = self._findings(repo.root)

        self.assertFalse(any(f.file == "CHANGELOG.md" for f in findings))

    def _grow(self, repo: Repo, name: str, claims_toml: str = "") -> list[Finding]:
        """Ranks `notes.md`'s one section, which names `name`, after `name`
        has had a line inserted at its top and another appended. A staged
        rewrite of one of its lines, in no commit yet, brings the section
        into the range, so its score is what the history alone gives."""

        repo.write("notes.md", f"## Releases\n\nSee `{name}` for each release.\n")
        repo.write(name, "# Log\n\n## 1.0\n\n- First.\n")
        repo.commit(BASE)
        repo.write(name, "# Log\n\n## Unreleased\n\n- Next.\n\n## 1.0\n\n- First.\n")
        repo.commit(BASE + 100)
        repo.write(name, "# Log\n\n## Unreleased\n\n- Next.\n\n## 1.0\n\n- First.\n- Also.\n")
        repo.commit(BASE + 200)
        text = (repo.root / name).read_text()
        repo.write(name, text.replace("- First.", "- Initial."))
        return self._findings_with_toml(repo.root, claims_toml, "HEAD")

    def test_appends_to_a_changelog_subject_are_not_churn(self) -> None:
        with Repo() as repo:
            self.assertEqual(self._grow(repo, "CHANGELOG.md"), [])

    def test_an_edited_line_in_a_changelog_subject_is_churn(self) -> None:
        with Repo() as repo:
            self._grow(repo, "CHANGELOG.md")
            text = (repo.root / "CHANGELOG.md").read_text()
            repo.write("CHANGELOG.md", text.replace("## Unreleased", "## 1.1"))
            repo.commit(BASE + 300)
            findings = self._findings_with_toml(repo.root, "")

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "notes.md:1")
        # Creating the file removed no lines either, so the edit is its
        # whole counted history.
        self.assertIn("CHANGELOG.md 1 commit (100% of its history)", findings[0].message)

    def test_a_section_of_a_changelog_is_filtered_the_same_way(self) -> None:
        with Repo() as repo:
            repo.write("docs/notes.md", "## Next\n\nSee [the log](../CHANGELOG.md#unreleased).\n")
            repo.write("CHANGELOG.md", "# Log\n\n## Unreleased\n\n- Next.\n\n## 1.0\n\n- First.\n")
            repo.commit(BASE)
            repo.write("CHANGELOG.md", "# Log\n\n## Unreleased\n\n- Next.\n- Newer.\n\n## 1.0\n\n- First.\n")
            repo.commit(BASE + 100)
            self.assertEqual(self._findings_with_toml(repo.root, ""), [])

            repo.write("CHANGELOG.md", "# Log\n\n## Unreleased\n\n- Later.\n- Newer.\n\n## 1.0\n\n- First.\n")
            repo.commit(BASE + 200)
            findings = self._findings_with_toml(repo.root, "")

        self.assertEqual(len(findings), 1)
        self.assertIn("CHANGELOG.md#unreleased 1 commit", findings[0].message)

    def test_a_merge_of_two_appends_is_not_churn(self) -> None:
        with Repo() as repo:
            log = "# Log\n\n## Unreleased\n\n- First.\n"
            repo.write("notes.md", "## Releases\n\nSee `CHANGELOG.md` for each release.\n")
            repo.write("CHANGELOG.md", log)
            repo.commit(BASE)
            git = ["git", "-C", str(repo.root)]
            subprocess.run([*git, "checkout", "-q", "-b", "side"], check=True)
            repo.write("CHANGELOG.md", log + "- Side.\n")
            repo.commit(BASE + 100)
            subprocess.run([*git, "checkout", "-q", "-"], check=True)
            repo.write("CHANGELOG.md", log.replace("- First.", "- Main.\n- First."))
            repo.commit(BASE + 200)
            date = {**os.environ, "GIT_AUTHOR_DATE": f"{BASE + 300} +0000", "GIT_COMMITTER_DATE": f"{BASE + 300} +0000"}
            subprocess.run([*git, "merge", "-q", "--no-edit", "side"], check=True, env=date)
            parents = subprocess.run(
                [*git, "log", "--format=%P", "-1", "--", "CHANGELOG.md"],
                capture_output=True, text=True, check=True,
            ).stdout.split()
            self.assertEqual(len(parents), 2, "the merge must be in the file's history")
            # Staged, so the range ranks the section and the history scores it.
            text = (repo.root / "CHANGELOG.md").read_text()
            repo.write("CHANGELOG.md", text.replace("- Main.", "- Mainline."))

            self.assertEqual(self._findings_with_toml(repo.root, "", "HEAD"), [])

    def test_appends_to_a_listed_append_only_subject_are_not_churn(self) -> None:
        with Repo() as repo:
            findings = self._grow(repo, "RELEASES.md", '[subjects]\nappend_only = "RELEASES.md"\n')

        self.assertEqual(findings, [])

    def test_appends_to_an_unlisted_subject_are_churn(self) -> None:
        with Repo() as repo:
            findings = self._grow(repo, "RELEASES.md")

        self.assertEqual(len(findings), 1)
        self.assertIn("RELEASES.md 2 commits (67% of its history)", findings[0].message)

    def _releasing(self, repo: Repo, name: str = "CHANGELOG.md") -> None:
        """`guide.md` names `name`, whose second commit edits a line in
        place, so its counted history is that one edit."""

        repo.write("guide.md", f"## Releasing\n\nRecord each change in `{name}`.\n")
        name = name.removeprefix("./")
        repo.write(name, "# Log\n\n## Unreleased\n\n- First.\n")
        repo.commit(BASE)
        repo.write(name, "# Log\n\n## Unreleased\n\n- Initial.\n")
        repo.commit(BASE + 100)

    def _append(self, repo: Repo, name: str = "CHANGELOG.md") -> None:
        text = (repo.root / name).read_text()
        repo.write(name, text + "\n## [0.1.0]\n")

    def test_a_range_only_growing_a_changelog_subject_ranks_nothing(self) -> None:
        with Repo() as repo:
            self._releasing(repo)
            self.assertEqual(len(self._findings_with_toml(repo.root, "", "HEAD~1")), 1)
            self._append(repo)
            repo.commit(BASE + 200)
            self.assertEqual(self._findings_with_toml(repo.root, "", "HEAD~1"), [])

    def test_a_range_rewriting_a_changelog_line_ranks_its_section(self) -> None:
        with Repo() as repo:
            self._releasing(repo)
            text = (repo.root / "CHANGELOG.md").read_text()
            repo.write("CHANGELOG.md", text.replace("## Unreleased", "## [0.1.0]"))
            repo.commit(BASE + 200)
            findings = self._findings_with_toml(repo.root, "", "HEAD~1")
        self.assertEqual([f.citation for f in findings], ["guide.md:1"])
        self.assertIn("CHANGELOG.md 2 commits (100% of its history)", findings[0].message)

    def test_a_line_added_and_rewritten_inside_the_range_ranks_its_section(self) -> None:
        with Repo() as repo:
            self._releasing(repo)
            self._append(repo)
            repo.commit(BASE + 200)
            text = (repo.root / "CHANGELOG.md").read_text()
            repo.write("CHANGELOG.md", text.replace("## [0.1.0]", "## [0.1.0] - 2026-11-11"))
            repo.commit(BASE + 300)
            # Over both commits the file only grew; the second rewrote a line.
            findings = self._findings_with_toml(repo.root, "", "HEAD~2")
        self.assertEqual([f.citation for f in findings], ["guide.md:1"])
        self.assertIn("CHANGELOG.md 2 commits (100% of its history)", findings[0].message)

    def test_a_staged_rewrite_of_a_line_the_range_added_ranks_its_section(self) -> None:
        with Repo() as repo:
            self._releasing(repo)
            self._append(repo)
            repo.commit(BASE + 200)
            text = (repo.root / "CHANGELOG.md").read_text()
            repo.write("CHANGELOG.md", text.replace("## [0.1.0]", "## [0.1.0] - 2026-11-11"))
            findings = self._findings_with_toml(repo.root, "", "HEAD~1")
        self.assertEqual([f.citation for f in findings], ["guide.md:1"])

    def test_growth_beside_another_changed_subject_still_ranks_the_section(self) -> None:
        with Repo() as repo:
            repo.write("guide.md", "## Releasing\n\nRun `release.sh`, then record it in `CHANGELOG.md`.\n")
            repo.write("CHANGELOG.md", "# Log\n\n## Unreleased\n\n- First.\n")
            repo.write("release.sh", "v0\n")
            repo.commit(BASE)
            repo.write("release.sh", "v1\n")
            repo.commit(BASE + 100)
            before = self._findings_with_toml(repo.root, "", "HEAD~1")
            self._append(repo)
            repo.write("release.sh", "v2\n")
            repo.commit(BASE + 200)
            findings = self._findings_with_toml(repo.root, "", "HEAD~1")
        self.assertEqual([f.citation for f in before], ["guide.md:1"])
        self.assertEqual([f.citation for f in findings], ["guide.md:1"])
        self.assertIn("release.sh 2 commits (67% of its history)", findings[0].message)
        self.assertNotIn("CHANGELOG.md", findings[0].message)

    def test_a_range_only_growing_a_listed_append_only_subject_ranks_nothing(self) -> None:
        toml = '[subjects]\nappend_only = "RELEASES.md"\n'
        with Repo() as repo:
            self._releasing(repo, "RELEASES.md")
            self._append(repo, "RELEASES.md")
            repo.commit(BASE + 200)
            self.assertEqual(self._findings_with_toml(repo.root, toml, "HEAD~1"), [])
            # Unlisted, the same growth still ranks it, as it always did.
            self.assertEqual(len(self._findings_with_toml(repo.root, "", "HEAD~1")), 1)

    def test_a_staged_change_only_growing_the_changelog_ranks_nothing(self) -> None:
        with Repo() as repo:
            self._releasing(repo)
            self._append(repo)
            self.assertEqual(self._findings_with_toml(repo.root, "", "HEAD"), [])

    def test_deleting_a_changelog_subject_ranks_its_section(self) -> None:
        with Repo() as repo:
            # An explicit path: a bare name resolves through the stem
            # index, which a deleted file has already left.
            self._releasing(repo, "./CHANGELOG.md")
            repo.rm("CHANGELOG.md")
            self.assertEqual([f.citation for f in self._findings_with_toml(repo.root, "", "HEAD")], ["guide.md:1"])

    def test_deleting_an_empty_changelog_subject_ranks_its_section(self) -> None:
        with Repo() as repo:
            repo.write("guide.md", "## Releasing\n\nRecord each change in `./CHANGELOG.md`.\n")
            repo.write("CHANGELOG.md", "# Log\n")
            repo.commit(BASE)
            repo.write("CHANGELOG.md", "")
            repo.commit(BASE + 100)
            # Deleting a file with no lines removes none.
            repo.rm("CHANGELOG.md")
            findings = self._findings_with_toml(repo.root, "", "HEAD")
        self.assertEqual([f.citation for f in findings], ["guide.md:1"])

    def test_merging_a_base_that_rewrote_the_changelog_ranks_nothing(self) -> None:
        with Repo() as repo:
            self._releasing(repo)
            git = ["git", "-C", str(repo.root)]
            subprocess.run([*git, "checkout", "-q", "-b", "feature"], check=True)
            self._append(repo)
            repo.commit(BASE + 200)
            subprocess.run([*git, "checkout", "-q", "-"], check=True)
            text = (repo.root / "CHANGELOG.md").read_text()
            repo.write("CHANGELOG.md", text.replace("## Unreleased", "## [0.0.9]"))
            repo.commit(BASE + 300)
            base = subprocess.run(
                [*git, "rev-parse", "HEAD"], capture_output=True, text=True, check=True
            ).stdout.strip()
            subprocess.run([*git, "checkout", "-q", "feature"], check=True)
            date = {**os.environ, "GIT_AUTHOR_DATE": f"{BASE + 400} +0000", "GIT_COMMITTER_DATE": f"{BASE + 400} +0000"}
            subprocess.run([*git, "merge", "-q", "--no-edit", base], check=True, env=date)
            # The branch only grew the file; the rewrite is the base's own.
            self.assertEqual(self._findings_with_toml(repo.root, "", base), [])

    def test_a_revision_naming_no_single_commit_ranks_any_change(self) -> None:
        with Repo() as repo:
            self._releasing(repo)
            findings = self._findings_with_toml(repo.root, "", "HEAD^!")
        self.assertEqual([f.citation for f in findings], ["guide.md:1"])

    def test_a_two_commit_range_reads_the_file_at_its_end_not_the_working_tree(self) -> None:
        with Repo() as repo:
            self._releasing(repo)
            self._append(repo)
            repo.commit(BASE + 200)
            (repo.root / "CHANGELOG.md").unlink()
            self.assertEqual(self._findings_with_toml(repo.root, "", "HEAD~1..HEAD"), [])

    def test_an_excluded_file_is_skipped_entirely(self) -> None:
        with Repo() as repo:
            _build_fixture(repo)
            findings = self._findings_with_toml(
                repo.root, '[stale-claims]\nexclude = ["doc.md"]\n'
            )
        self.assertEqual(findings, [])

    def test_an_excluded_glob_is_skipped_entirely(self) -> None:
        with Repo() as repo:
            _build_fixture(repo)
            repo.write("docs/other.md", DOC)
            repo.commit(BASE + 600)
            # Without this further churn, `other.md`'s own claim would be
            # trivially non-stale (nothing postdates its own commit) and
            # the test wouldn't distinguish "excluded" from "just quiet".
            repo.write("src/subject.py", "v4")
            repo.commit(BASE + 700)
            findings = self._findings_with_toml(
                repo.root, '[stale-claims]\nexclude = ["docs/*.md"]\n'
            )
        self.assertFalse(any(f.file == "docs/other.md" for f in findings))
        self.assertTrue(any(f.file == "doc.md" for f in findings))

    def test_an_excluded_file_still_resolves_as_a_subject_named_elsewhere(
        self,
    ) -> None:
        # `exclude` skips ranking *that file's own* sections and drops it
        # from bare-name lookup (#92), but an explicit path still resolves
        # against the whole tracked tree.
        with Repo() as repo:
            repo.write("docs/legacy.md", "prose\n")
            repo.write(
                "guide.md", "## by path\nSee docs/legacy.md for the old behavior.\n"
            )
            repo.commit(BASE)
            repo.write("docs/legacy.md", "prose v1\n")
            repo.commit(BASE + 100)
            findings = self._findings_with_toml(
                repo.root, '[stale-claims]\nexclude = ["docs/legacy.md"]\n'
            )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "guide.md:1")
        self.assertIn("legacy.md", findings[0].message)

    def _findings_for_excluded_project(self, repo: Repo, doc: str) -> list[Finding]:
        repo.write("ex/project.rs", "v0")
        repo.write("guide.md", doc)
        repo.commit(BASE)
        repo.write("ex/project.rs", "v1")
        repo.commit(BASE + 100)
        return self._findings_with_toml(
            repo.root, '[stale-claims]\nexclude = ["ex/*"]\n'
        )

    def test_a_bare_name_never_resolves_to_an_excluded_file(self) -> None:
        with Repo() as repo:
            findings = self._findings_for_excluded_project(
                repo, "## install\nSee `project` for details.\n"
            )
        self.assertEqual(findings, [])

    def test_an_excluded_file_named_by_explicit_path_is_still_a_subject(
        self,
    ) -> None:
        with Repo() as repo:
            findings = self._findings_for_excluded_project(
                repo, "## install\nSee ex/project.rs for details.\n"
            )
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "guide.md:1")
        self.assertIn("project.rs", findings[0].message)

    def test_a_stem_shared_with_an_excluded_file_resolves_to_the_other(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write("ex/project.rs", "v0")
            repo.write("src/project.py", "v0")
            repo.write("guide.md", "## install\nSee `project` for details.\n")
            repo.commit(BASE)
            repo.write("ex/project.rs", "v1")
            repo.write("src/project.py", "v1")
            repo.commit(BASE + 100)
            findings = self._findings_with_toml(
                repo.root, '[stale-claims]\nexclude = ["ex/*"]\n'
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("project.py", findings[0].message)
        self.assertNotIn("project.rs", findings[0].message)

    def _findings_for_churned_config(self, repo: Repo, doc: str) -> list[Finding]:
        repo.write("claims.toml", "# v0\n")
        repo.write("guide.md", doc)
        repo.commit(BASE)
        repo.write("claims.toml", "# v1\n")
        repo.commit(BASE + 100)
        return self._findings(repo.root)

    def test_a_bare_claims_never_resolves_to_the_root_config(self) -> None:
        with Repo() as repo:
            findings = self._findings_for_churned_config(
                repo, "## install\nRun `claims` on every commit.\n"
            )
        self.assertEqual(findings, [])

    def test_a_backticked_claims_toml_is_not_a_subject(self) -> None:
        with Repo() as repo:
            findings = self._findings_for_churned_config(
                repo, "## configure\nSettings live in `claims.toml`.\n"
            )
        self.assertEqual(findings, [])

    def test_the_claims_stem_resolves_to_another_file_sharing_it(self) -> None:
        with Repo() as repo:
            repo.write("src/claims.py", "v0")
            repo.write("claims.toml", "# v0\n")
            repo.write("guide.md", "## api\nSee `claims` for details.\n")
            repo.commit(BASE)
            repo.write("src/claims.py", "v1")
            repo.commit(BASE + 100)
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("claims.py", findings[0].message)

    def test_exclude_does_not_affect_a_non_matching_file(self) -> None:
        with Repo() as repo:
            _build_fixture(repo)
            findings = self._findings_with_toml(
                repo.root, '[stale-claims]\nexclude = ["other.md"]\n'
            )
        self.assertEqual(len(findings), 2)

    def test_a_bare_string_exclude_value_is_coerced_to_one_element(self) -> None:
        with Repo() as repo:
            _build_fixture(repo)
            findings = self._findings_with_toml(
                repo.root, '[stale-claims]\nexclude = "doc.md"\n'
            )
        self.assertEqual(findings, [])

    def test_a_backtick_bare_name_with_an_extension_still_names_its_subject(self) -> None:
        # `` `subject.py` `` (extension included), not a full path — the
        # original's `MODULE_RE` strips a trailing `.rs` before the stem
        # lookup so this still resolves; a naive port that requires the
        # backtick content to be exactly the bare stem would silently drop
        # every `` `name.ext` `` reference in prose, which is the common
        # way to write one.
        with Repo() as repo:
            repo.write("doc.md", "## stale\nSee `subject.py` for details.\n")
            repo.write("src/subject.py", "v0")
            repo.commit(BASE)
            repo.write("src/subject.py", "v1")
            repo.commit(BASE + 100)
            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "doc.md:1")
        self.assertIn("subject.py", findings[0].message)

    def test_a_backticked_name_with_a_different_extension_names_no_subject(self) -> None:
        # `` `hook.json` `` with only `hook.py` tracked: the stem matches but
        # the extension does not, so the mention names nothing rather than
        # guessing at a file of another type (#102).
        with Repo() as repo:
            findings = self._findings_for_churned(
                repo, "src/hook.py", "## hook\nSee `hook.json` for details.\n"
            )
        self.assertEqual(findings, [])

    def test_a_backticked_extension_match_is_case_sensitive(self) -> None:
        # Tracked paths are case-sensitive (`path_matches` uses
        # `fnmatchcase`), so the extension comparison is too.
        with Repo() as repo:
            findings = self._findings_for_churned(
                repo, "src/hook.py", "## hook\nSee `hook.PY` for details.\n"
            )
        self.assertEqual(findings, [])

    def test_a_mismatched_extension_does_not_bypass_module_reference_scope(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write("src/hook.py", "v0")
            repo.write("docs/other.md", "## out-of-scope\nSee `hook.json` for details.\n")
            repo.commit(BASE)
            repo.write("src/hook.py", "v1")
            repo.commit(BASE + 100)
            findings = self._findings_with_toml(
                repo.root,
                '[stale-claims]\nmodule_reference_scope = ["decisions/*.md"]\n',
            )
        self.assertEqual(findings, [])

    def test_a_bare_backtick_name_names_its_subject_anywhere_by_default(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", "## stale\nSee `subject` for details.\n")
            repo.write("src/subject.py", "v0")
            repo.commit(BASE)
            repo.write("src/subject.py", "v1")
            repo.commit(BASE + 100)
            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "doc.md:1")
        self.assertIn("subject.py", findings[0].message)

    def test_module_reference_scope_bounds_bare_citations_but_not_qualified_ones(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write("src/subject.py", "v0")
            repo.write("decisions/0001-choice.md", "## in-scope\nSee `subject` for details.\n")
            repo.write("docs/other.md", "## out-of-scope\nSee `subject` for details.\n")
            repo.write(
                "docs/qualified.md",
                "## qualified-from-out-of-scope\nSee `subject.py` for details.\n",
            )
            repo.commit(BASE)
            repo.write("src/subject.py", "v1")
            repo.commit(BASE + 100)

            findings = self._findings_with_toml(
                repo.root,
                '[stale-claims]\nmodule_reference_scope = ["decisions/*.md"]\n',
            )

        self.assertEqual(
            {f.file for f in findings},
            {"decisions/0001-choice.md", "docs/qualified.md"},
        )

    def test_a_tracked_filename_containing_a_space_does_not_crash_the_check(self) -> None:
        # A naive `ls-files` output split on whitespace would shred this
        # filename into two bogus paths and crash `read_text` on the
        # nonexistent half — an advisory check crashing violates its own
        # "never fails the run" contract.
        with Repo() as repo:
            _build_fixture(repo)
            repo.write("release notes.md", "## notes\nSee src/subject.py.\n")
            repo.commit(BASE + 600)
            findings = self._findings(repo.root)

        self.assertEqual({f.citation for f in findings}, {"doc.md:1", "doc.md:4"})

    def _findings_for_churned(
        self, repo: Repo, subject: str, doc: str, citing: str = "guide.md"
    ) -> list[Finding]:
        repo.write(citing, doc)
        repo.write(subject, "v0")
        repo.commit(BASE)
        repo.write(subject, "v1")
        repo.commit(BASE + 100)
        return self._findings(repo.root)

    def test_a_dot_directory_path_is_a_subject(self) -> None:
        with Repo() as repo:
            findings = self._findings_for_churned(
                repo,
                ".github/workflows/ci.yml",
                "## ci\nSee .github/workflows/ci.yml for details.\n",
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("ci.yml", findings[0].message)

    def test_a_home_or_host_absolute_path_is_not_a_repo_subject(self) -> None:
        for cited in ("~/foo/bar.py", "/usr/foo/bar.py", "/foo/bar.py"):
            with self.subTest(cited=cited), Repo() as repo:
                findings = self._findings_for_churned(
                    repo, "foo/bar.py", f"## host\nSee {cited} for details.\n"
                )
                self.assertEqual(findings, [])

    def test_a_dot_slash_path_names_its_repo_relative_subject(self) -> None:
        with Repo() as repo:
            findings = self._findings_for_churned(
                repo, "foo/bar.py", "## here\nSee ./foo/bar.py for details.\n"
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("bar.py", findings[0].message)

    def test_a_dot_dot_path_resolves_from_the_citing_file(self) -> None:
        doc = "## up\nSee ../foo/bar.py for details.\n"
        with Repo() as repo:
            findings = self._findings_for_churned(
                repo, "foo/bar.py", doc, citing="docs/guide.md"
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("bar.py", findings[0].message)

        with Repo() as repo:
            findings = self._findings_for_churned(
                repo, "foo/bar.py", doc, citing="docs/sub/guide.md"
            )
        self.assertEqual(findings, [])

    def test_a_path_missing_at_the_root_resolves_from_the_citing_file(self) -> None:
        with Repo() as repo:
            findings = self._findings_for_churned(
                repo,
                "docs/sub/bar.py",
                "## beside\nSee sub/bar.py for details.\n",
                citing="docs/guide.md",
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("bar.py", findings[0].message)

    OTHER = "# Other\n## a\na v0\n## b\nb v0\n### b1\nb1 v0\n## c\nc v0\n"

    def _findings_after_editing_other(
        self, doc: str, line: str, claims_toml: str = ""
    ) -> list[Finding]:
        """`guide.md` holds `doc`; `ref/other.md` is then edited on `line`
        alone. Run under `claims_toml`."""

        with Repo() as repo:
            repo.write("guide.md", doc)
            repo.write("ref/other.md", self.OTHER)
            repo.commit(BASE)
            repo.write("ref/other.md", self.OTHER.replace(line, line.replace("v0", "v1")))
            repo.commit(BASE + 100)
            return self._findings_with_toml(repo.root, claims_toml)

    def test_an_anchored_link_ignores_edits_outside_its_section(self) -> None:
        doc = "## see\nSee [b](ref/other.md#b).\n"
        for line in ("a v0", "c v0"):
            with self.subTest(line=line):
                self.assertEqual(self._findings_after_editing_other(doc, line), [])

    def test_an_anchored_link_counts_edits_inside_its_section(self) -> None:
        doc = "## see\nSee [b](ref/other.md#b).\n"
        for line in ("b v0", "b1 v0"):
            with self.subTest(line=line):
                findings = self._findings_after_editing_other(doc, line)
                self.assertEqual(len(findings), 1)
                self.assertIn("other.md#b 1 commit", findings[0].message)

    def test_an_unanchored_link_still_counts_every_edit_to_the_file(self) -> None:
        findings = self._findings_after_editing_other("## see\nSee [o](ref/other.md).\n", "a v0")
        self.assertEqual(len(findings), 1)

    def test_an_anchor_naming_no_heading_falls_back_to_the_whole_file(self) -> None:
        findings = self._findings_after_editing_other(
            "## see\nSee [o](ref/other.md#nope).\n", "a v0"
        )
        self.assertEqual(len(findings), 1)
        self.assertIn("other.md 1 commit", findings[0].message)

    def test_a_bare_prose_anchor_is_scoped_like_a_link(self) -> None:
        doc = "## see\nSee ref/other.md#b.\n"
        self.assertEqual(self._findings_after_editing_other(doc, "a v0"), [])
        self.assertEqual(len(self._findings_after_editing_other(doc, "b v0")), 1)

    def test_an_anchor_on_a_non_markdown_path_falls_back_to_the_whole_file(self) -> None:
        with Repo() as repo:
            findings = self._findings_for_churned(
                repo, "foo/bar.py", "## line\nSee foo/bar.py#L10 for details.\n"
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("bar.py 1 commit", findings[0].message)

    def test_a_heading_with_regex_metacharacters_scopes_its_section(self) -> None:
        other = "# Other\n## Why (a+b)?\nwhy v0\n## c\nc v0\n"
        doc = "## see\nSee [w](ref/other.md#why-ab).\n"
        for line, expected in (("c v0", 0), ("why v0", 1)):
            with self.subTest(line=line), Repo() as repo:
                repo.write("guide.md", doc)
                repo.write("ref/other.md", other)
                repo.commit(BASE)
                repo.write("ref/other.md", other.replace(line, line.replace("v0", "v1")))
                repo.commit(BASE + 100)
                self.assertEqual(len(self._findings(repo.root)), expected)

    def test_an_uncommitted_edit_to_the_linked_file_does_not_shift_its_section(
        self,
    ) -> None:
        # The commit hook runs with the linked page itself possibly dirty;
        # history is committed, so the section is found where HEAD has it.
        with Repo() as repo:
            repo.write("guide.md", "## see\nSee [b](ref/other.md#b).\n")
            repo.write("ref/other.md", self.OTHER)
            repo.commit(BASE)
            repo.write("ref/other.md", self.OTHER.replace("b v0", "b v1"))
            repo.commit(BASE + 100)
            repo.write("ref/other.md", "pad\n" * 20 + self.OTHER.replace("b v0", "b v1"))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("other.md#b 1 commit", findings[0].message)

    def test_the_same_file_linked_with_and_without_an_anchor_keeps_both(self) -> None:
        findings = self._findings_after_editing_other(
            "## see\nSee [o](ref/other.md) and [b](ref/other.md#b).\n", "b v0"
        )
        self.assertEqual(len(findings), 1)
        self.assertIn("other.md 1 commit", findings[0].message)
        self.assertIn("other.md#b 1 commit", findings[0].message)

    NAVIGATION = '[subjects]\nnavigation = "ref/other.md"\n'

    def test_a_navigation_page_named_whole_is_not_ranked(self) -> None:
        findings = self._findings_after_editing_other(
            "## see\nSee [o](ref/other.md).\n", "a v0", self.NAVIGATION
        )
        self.assertEqual(findings, [])

    def test_an_anchor_naming_no_heading_in_a_navigation_page_is_not_ranked(self) -> None:
        # The anchor names the whole page, as into any page, and named
        # whole a navigation page is no subject.
        findings = self._findings_after_editing_other(
            "## see\nSee [o](ref/other.md#nope).\n", "a v0", self.NAVIGATION
        )
        self.assertEqual(findings, [])

    def test_an_anchored_link_into_a_navigation_page_still_ranks(self) -> None:
        findings = self._findings_after_editing_other(
            "## see\nSee [o](ref/other.md) and [b](ref/other.md#b).\n", "b v0", self.NAVIGATION
        )
        self.assertEqual(len(findings), 1)
        self.assertIn("other.md#b 1 commit", findings[0].message)
        self.assertNotIn("other.md 1 commit", findings[0].message)

    ADR = (
        "# 0001 X\n"
        "## Context\nSee src/subject.py.\n"
        "### Prior art\nSee src/subject.py.\n"
        "## Decision\nSee src/subject.py.\n"
    )

    def _findings_for_adr(
        self, claims_toml: str, adr: str = "decisions/0001-x.md", text: str = ADR
    ) -> list[Finding]:
        """`adr` holds `text`, whose every section names `src/subject.py`,
        which then churns. Run under `claims_toml`."""

        with Repo() as repo:
            repo.write(adr, text)
            repo.write("src/subject.py", "v0")
            repo.commit(BASE)
            repo.write("src/subject.py", "v1")
            repo.commit(BASE + 100)
            return self._findings_with_toml(repo.root, claims_toml)

    def test_an_excluded_section_and_its_subsections_are_not_ranked(self) -> None:
        findings = self._findings_for_adr(
            '[stale-claims]\nexclude_sections = ["decisions/*.md#context"]\n'
        )
        self.assertEqual([_heading(f) for f in findings], ["Decision"])

    def test_a_fenced_heading_shaped_line_does_not_end_an_excluded_section(self) -> None:
        adr = self.ADR.replace(
            "### Prior art\n", "```sh\n# run it\nSee src/subject.py.\n```\n### Prior art\n"
        )
        findings = self._findings_for_adr(
            '[stale-claims]\nexclude_sections = ["decisions/*.md#context"]\n', text=adr
        )
        self.assertEqual([_heading(f) for f in findings], ["Decision"])

    def test_a_fenced_heading_shaped_line_does_not_start_a_section(self) -> None:
        # A `# comment` in a shell block is code, not a heading: the lines
        # after it stay in the section the fence sits in.
        adr = self.ADR.replace(
            "### Prior art\n", "```sh\n# run it\nSee src/subject.py.\n```\n### Prior art\n"
        )
        findings = self._findings_for_adr("", text=adr)
        self.assertEqual(
            sorted(_heading(f) for f in findings), ["Context", "Decision", "Prior art"]
        )

    def test_an_excluded_section_in_a_file_the_glob_misses_is_still_ranked(self) -> None:
        findings = self._findings_for_adr(
            '[stale-claims]\nexclude_sections = ["decisions/*.md#context"]\n', adr="adr/0001-x.md"
        )
        self.assertEqual(
            sorted(_heading(f) for f in findings), ["Context", "Decision", "Prior art"]
        )

    def test_a_bare_string_exclude_sections_value_is_one_element(self) -> None:
        findings = self._findings_for_adr(
            '[stale-claims]\nexclude_sections = "decisions/*.md#context"\n'
        )
        self.assertEqual([_heading(f) for f in findings], ["Decision"])

    def test_an_exclude_sections_entry_with_no_slug_shape_is_invalid_configuration(self) -> None:
        # `#Context` and `#prior art` are no heading's slug, so could
        # never match one.
        for entry in (
            "decisions/*.md",
            "decisions/*.md#",
            "decisions/*.md#Context",
            "decisions/*.md#prior art",
        ):
            with self.subTest(entry=entry):
                findings = self._findings_for_adr(
                    f'[stale-claims]\nexclude_sections = ["{entry}"]\n'
                )
                self.assertEqual(len(findings), 1)
                self.assertTrue(findings[0].gate)
                self.assertIn("exclude_sections", findings[0].message)

    def test_an_excluded_section_is_still_a_subject_when_linked(self) -> None:
        with Repo() as repo:
            repo.write("decisions/0001-x.md", self.ADR)
            repo.write("guide.md", "## see\nSee [c](decisions/0001-x.md#context).\n")
            repo.commit(BASE)
            repo.write("decisions/0001-x.md", self.ADR.replace("## Context\n", "## Context\nMore.\n"))
            repo.commit(BASE + 100)
            findings = self._findings_with_toml(
                repo.root, '[stale-claims]\nexclude_sections = ["decisions/*.md#context"]\n'
            )
        self.assertEqual([f.file for f in findings], ["guide.md"])
        self.assertIn("0001-x.md#context 1 commit", findings[0].message)


class StaleClaimsCliTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def test_end_to_end_via_the_cli(self) -> None:
        with Repo() as repo:
            _build_fixture(repo)

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(
                    [
                        "--repo-root",
                        str(repo.root),
                        "--diff-range",
                        _audit_range(repo.root),
                    ]
                )
            output = out.getvalue()

        self.assertEqual(code, 0)
        self.assertIn("doc.md:1", output)
        self.assertIn("doc.md:4", output)
        self.assertNotIn("doc.md:7", output)


if __name__ == "__main__":
    unittest.main()
