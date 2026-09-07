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

"""Tests for the `judgment-agent` check's deterministic candidate-list half:
`claims.checks.judgment_agent`.

Exercises the shared `run(repo_root, diff_range, config)` seam against
fixture git repos — see spec.md's Testing Decisions, which name this check's
fixture explicitly: "a fixture repo with a renamed symbol and prose that
cites the old name in a file the diff didn't touch, asserting the rename is
still surfaced as a candidate." Not a port — see the module docstring for
why (ticket 04's research found no surveyed tool computes this).
"""

from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path

from claims.checks.judgment_agent import MODE_ADDED, MODE_REMOVED, NAME, check
from claims.cli import main
from claims.runner import Finding, register_check, run

from support import RegistryClearingTestCase, Repo


class JudgmentAgentTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def _findings(self, repo_root: Path, diff_range: str = "HEAD") -> list[Finding]:
        return list(run(repo_root, diff_range, {}).findings)

    def test_a_rename_falsifies_a_citation_in_a_file_the_diff_never_touched(self) -> None:
        # The motivating case from ticket 04's research: a diff-scoped-by-file
        # check would never look at NOTES.md, since the diff never touches it.
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.write("docs/NOTES.md", "See `loadWidget` for the old approach.\n")
            repo.commit()
            repo.write("Sources/Room.swift", "func loadGadget() -> Gadget {}\n")

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "docs/NOTES.md:1")
        self.assertEqual(findings[0].mode, MODE_REMOVED)
        self.assertFalse(findings[0].gate)
        self.assertIn("loadWidget", findings[0].message)
        self.assertIn("Sources/Room.swift:1", findings[0].message)

    def test_a_same_commit_claim_and_subject_move_is_still_surfaced(self) -> None:
        # Churn-ranking (stale-claims.py) reads zero here by construction —
        # this check's before/after set-diff doesn't, since it's binary, not
        # a decaying-since-last-touch score.
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.write("docs/NOTES.md", "See `loadWidget` for the old approach.\n")
            repo.commit()
            # Both the code and the (stale, unfixed) prose move in one commit.
            repo.write("Sources/Room.swift", "func loadGadget() -> Gadget {}\n")
            repo.write("docs/NOTES.md", "See `loadWidget` for the old approach, still.\n")
            repo.commit()

            findings = self._findings(repo.root, "HEAD~1")

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "docs/NOTES.md:1")
        self.assertIn("touched in", findings[0].message)

    def test_uncommitted_evidence_is_named_as_such_not_silently_omitted(self) -> None:
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.write("docs/NOTES.md", "See `loadWidget` for the old approach.\n")
            repo.commit()
            repo.write("Sources/Room.swift", "func loadGadget() -> Gadget {}\n")

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertIn("uncommitted working-tree change", findings[0].message)

    def test_a_citation_to_a_newly_added_subject_is_a_candidate_too(self) -> None:
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.commit()
            repo.write(
                "Sources/Room.swift",
                "func loadWidget() -> Widget {}\nfunc loadGadget() -> Gadget {}\n",
            )
            repo.write("docs/NOTES.md", "See `loadGadget` for the new approach.\n")

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].mode, MODE_ADDED)
        self.assertIn("loadGadget", findings[0].message)

    def test_a_citation_to_an_unchanged_subject_is_not_a_candidate(self) -> None:
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.write("docs/NOTES.md", "See `loadWidget` for details.\n")
            repo.commit()
            repo.write("docs/OTHER.md", "Unrelated note.\n")

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_a_rust_rename_is_also_caught(self) -> None:
        with Repo() as repo:
            repo.write("src/room.rs", "pub fn load_widget() -> Widget {}\n")
            repo.write("docs/NOTES.md", "See `load_widget` for the old approach.\n")
            repo.commit()
            repo.write("src/room.rs", "pub fn load_gadget() -> Gadget {}\n")

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].mode, MODE_REMOVED)

    def test_no_touched_subjects_means_no_findings_not_a_crash(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "nothing to see here\n")
            repo.commit()
            repo.write("README.md", "still nothing to see here\n")

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_removed_candidates_rank_before_added_candidates(self) -> None:
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.write(
                "docs/NOTES.md",
                "See `loadGadget` for the new approach.\n"
                "See `loadWidget` for the old approach.\n",
            )
            repo.commit()
            repo.write("Sources/Room.swift", "func loadGadget() -> Gadget {}\n")

            findings = self._findings(repo.root)

        self.assertEqual([f.mode for f in findings], [MODE_REMOVED, MODE_ADDED])


class JudgmentAgentCliTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def test_a_candidate_never_fails_the_cli(self) -> None:
        # Advisory: candidates are context, not a gate — the run still
        # succeeds even though the "0 checked" precedent would otherwise
        # apply if this check produced nothing at all.
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.write("docs/NOTES.md", "See `loadWidget` for the old approach.\n")
            repo.commit()
            repo.write("Sources/Room.swift", "func loadGadget() -> Gadget {}\n")

            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["--repo-root", str(repo.root)])

        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
