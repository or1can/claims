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


class StaleClaimsTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def _findings(self, repo_root: Path) -> list[Finding]:
        return list(run(repo_root, "HEAD", {}).findings)

    def _findings_with_toml(self, repo_root: Path, claims_toml: str) -> list[Finding]:
        (repo_root / "claims.toml").write_text(claims_toml)
        config = load_config(repo_root)
        return list(run(repo_root, "HEAD", config).findings)

    def test_the_most_churned_subject_ranks_first(self) -> None:
        with Repo() as repo:
            _build_fixture(repo)
            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].citation, "doc.md:1")
        self.assertIn("subject.py", findings[0].message)
        self.assertEqual(findings[1].citation, "doc.md:4")
        self.assertIn("quiet.py", findings[1].message)

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


class StaleClaimsCliTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def test_end_to_end_via_the_cli(self) -> None:
        with Repo() as repo:
            _build_fixture(repo)

            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(["--repo-root", str(repo.root)])
            output = out.getvalue()

        self.assertEqual(code, 0)
        self.assertIn("doc.md:1", output)
        self.assertIn("doc.md:4", output)
        self.assertNotIn("doc.md:7", output)


if __name__ == "__main__":
    unittest.main()
