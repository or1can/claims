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

"""Tests for the `check-citations` check: `claims.checks.check_citations`.

Exercises the shared `run(repo_root, diff_range, config)` seam against
fixture git repos — see spec.md's Testing Decisions. Ported from Project B's
`scripts/check-citations` (Apache-2.0/relicensed prior art, same author).
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from claims.checks.check_citations import NAME, check
from claims.cli import main
from claims.runner import Finding, register_check, run

from support import RegistryClearingTestCase, Repo


class CheckCitationsTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def _findings(self, repo_root: Path) -> list[Finding]:
        return list(run(repo_root, "HEAD", {}).findings)

    def test_a_citation_to_a_removed_symbol_is_flagged(self) -> None:
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.commit()
            repo.write("Sources/Room.swift", "func loadGadget() -> Gadget {}\n")
            repo.commit()
            repo.write("docs/NOTES.md", "See `loadWidget` for the old approach.\n")
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "docs/NOTES.md:1")
        self.assertTrue(findings[0].gate)
        self.assertIn("loadWidget", findings[0].message)

    def test_a_citation_to_a_symbol_that_still_exists_is_not_flagged(self) -> None:
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.commit()
            repo.write("docs/NOTES.md", "See `loadWidget` for details.\n")
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_a_was_marker_exempts_a_deliberately_historical_reference(self) -> None:
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.commit()
            repo.write("Sources/Room.swift", "func loadGadget() -> Gadget {}\n")
            repo.commit()
            repo.write(
                "docs/NOTES.md",
                "<!-- was: loadWidget -->\n"
                "`loadWidget` asked `loadGadget` for a fallback.\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_a_was_marker_only_covers_its_own_line_and_the_next(self) -> None:
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.commit()
            repo.write("Sources/Room.swift", "func loadGadget() -> Gadget {}\n")
            repo.commit()
            repo.write(
                "docs/NOTES.md",
                "<!-- was: loadWidget -->\n"
                "one\n"
                "`loadWidget` is mentioned two lines below the marker.\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "docs/NOTES.md:3")

    def test_a_swift_comment_citation_to_a_removed_symbol_is_flagged(self) -> None:
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.commit()
            repo.write(
                "Sources/Room.swift",
                "func loadGadget() -> Gadget {}\n"
                "// loadGadget replaced `loadWidget`.\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "Sources/Room.swift:2")

    def test_a_citation_to_a_test_target_name_is_not_flagged(self) -> None:
        # A directory named like a test target is never itself a declared
        # symbol, but prose citing it must not be read as a dead citation.
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.write("RoomTests/RoomTests.swift", "func testLoad() {}\n")
            repo.commit()
            repo.write("Sources/Room.swift", "func loadGadget() -> Gadget {}\n")
            repo.commit()
            repo.write("docs/NOTES.md", "See `RoomTests` for coverage.\n")
            repo.commit()

            findings = self._findings(repo.root)

        self.assertFalse(any("RoomTests" in f.message for f in findings))

    def test_ordinary_prose_using_the_word_was_does_not_exempt_a_dead_citation(
        self,
    ) -> None:
        # The marker is `<!-- was: name -->`, not the bare word "was:" —
        # an unmarked sentence that happens to use it must still flag a
        # genuinely dead citation, or the check silences itself by accident.
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.commit()
            repo.write("Sources/Room.swift", "func loadGadget() -> Gadget {}\n")
            repo.commit()
            repo.write(
                "docs/NOTES.md", "The old name was: `loadWidget`, renamed since.\n"
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertIn("loadWidget", findings[0].message)

    def test_a_tracked_symlink_does_not_crash_the_check(self) -> None:
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            os.symlink("nonexistent-target.swift", repo.root / "Sources/Broken.swift")
            subprocess.run(
                ["git", "-C", str(repo.root), "add", "Sources/Broken.swift"],
                check=True,
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_a_non_git_directory_reports_a_gate_finding_not_a_crash_or_silent_pass(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as not_a_repo:
            Path(not_a_repo, "NOTES.md").write_text(
                "See `loadWidget` for the old approach.\n", encoding="utf-8"
            )
            findings = self._findings(Path(not_a_repo))

        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].gate)
        self.assertIn("cannot run", findings[0].message)

    def test_shallow_clone_reports_a_gate_finding_not_a_silent_pass(self) -> None:
        with Repo() as source:
            source.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            source.commit()
            source.write("Sources/Room.swift", "func loadGadget() -> Gadget {}\n")
            source.commit()
            source.write("docs/NOTES.md", "See `loadWidget` for the old approach.\n")
            source.commit()

            with tempfile.TemporaryDirectory() as shallow_dir:
                subprocess.run(
                    [
                        "git",
                        "clone",
                        "-q",
                        "--depth",
                        "1",
                        f"file://{source.root}",
                        shallow_dir,
                    ],
                    check=True,
                )
                findings = self._findings(Path(shallow_dir))

        self.assertEqual(len(findings), 1)
        self.assertTrue(findings[0].gate)
        self.assertIn("shallow", findings[0].message)


class CheckCitationsCliTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def test_a_gate_finding_fails_the_cli(self) -> None:
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.commit()
            repo.write("Sources/Room.swift", "func loadGadget() -> Gadget {}\n")
            repo.commit()
            repo.write("docs/NOTES.md", "See `loadWidget` for the old approach.\n")
            repo.commit()

            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["--repo-root", str(repo.root)])

        self.assertEqual(code, 1)

    def test_no_dead_citations_passes_the_cli(self) -> None:
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.commit()
            repo.write("docs/NOTES.md", "See `loadWidget` for details.\n")
            repo.commit()

            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["--repo-root", str(repo.root)])

        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
