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
