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
from unittest.mock import patch

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

    def test_the_same_dead_name_cited_twice_on_one_line_is_flagged_once(self) -> None:
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.commit()
            repo.write("Sources/Room.swift", "func loadGadget() -> Gadget {}\n")
            repo.commit()
            repo.write(
                "docs/NOTES.md",
                "`loadWidget` used to call `loadWidget` again on retry.\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "docs/NOTES.md:1")

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

    def test_a_swift_was_marker_exempts_a_deliberately_historical_reference(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.commit()
            repo.write(
                "Sources/Room.swift",
                "func loadGadget() -> Gadget {}\n"
                "// was: loadWidget\n"
                "// loadGadget replaced `loadWidget`.\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_a_swift_comment_with_trailing_prose_is_not_a_marker(self) -> None:
        # The marker must be the whole comment, not just start with "was:" —
        # trailing prose after it must not ride along as if it were the
        # marker (regression: this used to pass with a bare `startswith`
        # check).
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.commit()
            repo.write(
                "Sources/Room.swift",
                "func loadGadget() -> Gadget {}\n"
                "// was: loadWidget, replaced by loadGadget\n"
                "// still references `loadWidget` here.\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "Sources/Room.swift:3")

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


class CheckCitationsHistoryCacheTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def _log_call_count(self, repo_root: Path) -> int:
        with patch(
            "claims.checks.check_citations.subprocess.run", wraps=subprocess.run
        ) as spy:
            run(repo_root, "HEAD", {})
        return sum(1 for call in spy.call_args_list if "log" in call.args[0])

    def test_a_second_invocation_over_unchanged_history_does_not_walk_the_log(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.commit()
            repo.write("Sources/Room.swift", "func loadGadget() -> Gadget {}\n")
            repo.commit()

            first = self._log_call_count(repo.root)
            second = self._log_call_count(repo.root)

        self.assertEqual(first, 1)
        self.assertEqual(second, 0)

    def test_a_commit_added_after_caching_is_still_picked_up(self) -> None:
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.commit()

            run(repo.root, "HEAD", {})  # populate the cache at this HEAD

            repo.write("Sources/Room.swift", "func loadGadget() -> Gadget {}\n")
            repo.commit()
            repo.write("docs/NOTES.md", "See `loadWidget` for the old approach.\n")
            repo.commit()

            findings = list(run(repo.root, "HEAD", {}).findings)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "docs/NOTES.md:1")

    def test_history_rewritten_since_the_cached_head_still_finds_dead_citations(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write("Sources/Room.swift", "func loadWidget() -> Widget {}\n")
            repo.commit()

            run(repo.root, "HEAD", {})  # populate the cache at this HEAD

            subprocess.run(
                ["git", "-C", str(repo.root), "commit", "--amend", "-q", "-m", "commit"],
                check=True,
                env={
                    **os.environ,
                    "GIT_AUTHOR_DATE": "2020-01-01T00:00:00",
                    "GIT_COMMITTER_DATE": "2020-01-01T00:00:00",
                },
            )
            repo.write("Sources/Room.swift", "func loadGadget() -> Gadget {}\n")
            repo.commit()
            repo.write("docs/NOTES.md", "See `loadWidget` for the old approach.\n")
            repo.commit()

            findings = list(run(repo.root, "HEAD", {}).findings)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "docs/NOTES.md:1")


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
