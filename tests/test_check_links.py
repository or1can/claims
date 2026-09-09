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

"""Tests for the `check-links` check: `claims.checks.check_links`.

Exercises the shared `run(repo_root, diff_range, config)` seam against
fixture git repos — see spec.md's Testing Decisions. Ported from Project B's
`scripts/check-links` and `scripts/slugs.sh` (Apache-2.0/relicensed prior
art, same author).
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from claims.checks.check_links import NAME, check
from claims.cli import main
from claims.runner import Finding, register_check, run

from support import RegistryClearingTestCase, Repo


class CheckLinksTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def _findings(self, repo_root: Path) -> list[Finding]:
        return list(run(repo_root, "HEAD", {}).findings)

    def test_a_link_to_a_nonexistent_path_is_flagged(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "See [notes](docs/NOTES.md) for details.\n")
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "README.md:1")
        self.assertTrue(findings[0].gate)
        self.assertIn("docs/NOTES.md", findings[0].message)

    def test_a_correct_relative_link_with_an_anchor_is_not_flagged(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "See [notes](docs/NOTES.md#some-heading).\n")
            repo.write("docs/NOTES.md", "# Some Heading\n\nBody.\n")
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_a_multi_word_heading_anchor_that_does_not_resolve_is_flagged(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "See [notes](docs/NOTES.md#wrong-heading).\n")
            repo.write("docs/NOTES.md", "# My Heading Name\n\nBody.\n")
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "README.md:1")
        self.assertIn("wrong-heading", findings[0].message)

    def test_a_multi_word_heading_anchor_that_does_resolve_is_not_flagged(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "See [notes](docs/NOTES.md#my-heading-name).\n")
            repo.write("docs/NOTES.md", "# My Heading Name\n\nBody.\n")
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_a_path_plus_anchor_link_is_checked_not_silently_skipped(self) -> None:
        # Regression case (ticket 13): the source tool's first version only
        # matched a link ending bare `.md)`, so a `...md#anchor)` link was
        # never validated at all — a correct path with a broken anchor must
        # still be flagged, not waved through because the path resolves.
        with Repo() as repo:
            repo.write("README.md", "See [notes](docs/NOTES.md#missing).\n")
            repo.write("docs/NOTES.md", "# Present\n\nBody.\n")
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertIn("missing", findings[0].message)

    def test_a_bare_same_file_anchor_that_resolves_is_not_flagged(self) -> None:
        with Repo() as repo:
            repo.write(
                "README.md",
                "# Overview\n\nJump to [details](#details).\n\n## Details\n\nBody.\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_a_bare_same_file_anchor_that_does_not_resolve_is_flagged(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "# Overview\n\nJump to [details](#missing).\n")
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "README.md:3")

    def test_multiple_broken_links_are_all_reported(self) -> None:
        with Repo() as repo:
            repo.write(
                "README.md",
                "See [a](docs/A.md) and [b](docs/B.md).\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 2)
        messages = " ".join(f.message for f in findings)
        self.assertIn("docs/A.md", messages)
        self.assertIn("docs/B.md", messages)

    def test_a_link_to_a_non_markdown_target_is_not_checked(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "See the [logo](assets/logo.png).\n")
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_an_external_url_is_not_checked(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "See [docs](https://example.com/notes.md).\n")
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_a_tracked_symlink_does_not_crash_the_check(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "See [notes](docs/NOTES.md).\n")
            (repo.root / "docs").mkdir()
            os.symlink("nonexistent-target.md", repo.root / "docs" / "NOTES.md")
            subprocess.run(
                ["git", "-C", str(repo.root), "add", "docs/NOTES.md"], check=True
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "README.md:1")

    def test_a_link_escaping_the_repo_root_is_flagged_not_read(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "See [escape](../../etc/passwd.md).\n")
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)

    def test_a_real_filename_starting_with_dotdot_is_not_treated_as_an_escape(
        self,
    ) -> None:
        # Regression: the escape guard must key on the leading path *segment*
        # being `..`, not on the resolved string merely starting with the two
        # characters `..` — a real filename like `..config.md` would
        # otherwise be a false-positive broken link.
        with Repo() as repo:
            repo.write("README.md", "See [cfg](..config.md).\n")
            repo.write("..config.md", "# Config\n")
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_a_symlink_to_an_in_repo_target_is_followed_and_validated(self) -> None:
        # Ticket 20: the CLAUDE.md -> AGENTS.md convention (executable_claims.py's
        # own comment) — a link to a tracked symlink whose resolved target is
        # still inside repo_root must be read through, not reported broken.
        with Repo() as repo:
            repo.write("AGENTS.md", "# Setup\n\nBody.\n")
            os.symlink("AGENTS.md", repo.root / "CLAUDE.md")
            subprocess.run(["git", "-C", str(repo.root), "add", "CLAUDE.md"], check=True)
            repo.write("decisions/0001.md", "See [setup](../CLAUDE.md#setup).\n")
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_a_symlinked_file_escaping_the_repo_is_still_flagged_not_followed(
        self,
    ) -> None:
        with Repo() as repo, tempfile.TemporaryDirectory() as outside_dir:
            outside = Path(outside_dir)
            (outside / "leak.md").write_text("# Leak\n", encoding="utf-8")
            repo.write("README.md", "See [leak](escaped-leak.md).\n")
            os.symlink(outside / "leak.md", repo.root / "escaped-leak.md")
            subprocess.run(
                ["git", "-C", str(repo.root), "add", "escaped-leak.md"], check=True
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertIn("escaped-leak.md", findings[0].message)

    def test_a_link_through_a_symlinked_directory_escaping_the_repo_is_flagged(
        self,
    ) -> None:
        # Regression: a tracked symlinked *directory* pointing outside the
        # repo lets a resolved path with no leading `..` or `/` still read
        # off-tree content unless the check confines by real path, not just
        # the lexical string.
        with Repo() as repo, tempfile.TemporaryDirectory() as outside_dir:
            outside = Path(outside_dir)
            (outside / "leak.md").write_text("# Leak\n", encoding="utf-8")
            repo.write("README.md", "See [leak](escaped/leak.md).\n")
            os.symlink(outside, repo.root / "escaped")
            subprocess.run(
                ["git", "-C", str(repo.root), "add", "escaped"], check=True
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertIn("escaped/leak.md", findings[0].message)


class CheckLinksCliTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def test_a_gate_finding_fails_the_cli(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "See [notes](docs/NOTES.md).\n")
            repo.commit()

            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["--repo-root", str(repo.root)])

        self.assertEqual(code, 1)

    def test_no_broken_links_passes_the_cli(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "See [notes](docs/NOTES.md).\n")
            repo.write("docs/NOTES.md", "# Notes\n")
            repo.commit()

            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["--repo-root", str(repo.root)])

        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
