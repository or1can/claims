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

"""Tests for the `spliced-docs` check: `claims.checks.spliced_docs`.

Exercises the shared `run(repo_root, diff_range, config)` seam against a
fixture git repo — see spec.md's Testing Decisions. Ported from `ratect`'s
and Project B's own `tools/spliced-docs.py` (Rust, Swift; both Apache-2.0/
relicensed prior art).
"""

from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path

from claims.checks.spliced_docs import MODE_UNDOCUMENTED, MODE_UNKNOWN, NAME, check
from claims.cli import main
from claims.runner import Finding, register_check, run

from support import RegistryClearingTestCase, Repo


class SplicedDocsTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def _findings(self, repo_root: Path) -> list[Finding]:
        return list(run(repo_root, "HEAD", {}).findings)

    def test_a_rust_splice_naming_an_undocumented_item_in_file_is_flagged(self) -> None:
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "fn load_project() -> Project {}\n\n"
                "/// Loads the project's `load_project` config from disk.\n"
                "/// Converts the config into native TOML for `to_native_toml`.\n"
                "fn to_native_toml() -> Config {}\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "src/lib.rs:4")
        self.assertEqual(findings[0].mode, MODE_UNDOCUMENTED)
        self.assertIn("load_project", findings[0].message)

    def test_a_rust_splice_naming_nothing_in_the_repo_is_flagged(self) -> None:
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "/// Loads the config for `frobnicate_widget`.\n"
                "/// Writes the resulting struct to disk.\n"
                "fn save_config() {}\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].mode, MODE_UNKNOWN)
        self.assertIn("frobnicate_widget", findings[0].message)

    def test_a_rust_doc_comment_correctly_attached_is_not_flagged(self) -> None:
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "/// Loads the project's config from disk.\n"
                "///\n"
                "/// Returns the parsed `Config` struct.\n"
                "fn load_project() -> Config {}\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_a_swift_splice_naming_an_undocumented_declaration_in_file_is_flagged(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write(
                "Sources/Room.swift",
                "func canRestoreInPlace() -> Bool { true }\n\n"
                "/// Whether `canRestoreInPlace` allows an in-place restore.\n"
                "/// Blocks the restore for `restoreBlocker`.\n"
                "var restoreBlocker: Blocker? { nil }\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "Sources/Room.swift:4")
        self.assertEqual(findings[0].mode, MODE_UNDOCUMENTED)
        self.assertIn("canRestoreInPlace", findings[0].message)

    def test_a_swift_splice_naming_nothing_in_the_repo_is_flagged(self) -> None:
        with Repo() as repo:
            repo.write(
                "Sources/Room.swift",
                "/// Whether `canRestore` allows a restore.\n"
                "/// Blocks the restore for `restoreBlocker`.\n"
                "var restoreBlocker: Blocker? { nil }\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].mode, MODE_UNKNOWN)
        self.assertIn("canRestore", findings[0].message)

    def test_a_swift_unclosed_backtick_still_names_its_declaration(self) -> None:
        with Repo() as repo:
            repo.write(
                "Sources/Room.swift",
                "func canRestoreInPlace() -> Bool { true }\n\n"
                "/// Whether `canRestoreInPlace allows an in-place restore.\n"
                "/// Blocks the restore for `restoreBlocker`.\n"
                "var restoreBlocker: Blocker? { nil }\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].mode, MODE_UNDOCUMENTED)
        self.assertIn("canRestoreInPlace", findings[0].message)

    def test_a_swift_declaration_correctly_documented_is_not_flagged(self) -> None:
        with Repo() as repo:
            repo.write(
                "Sources/Room.swift",
                "/// Whether the room can be restored.\n"
                "///\n"
                "/// Returns false once `restoreBlocker` is set.\n"
                "func canRestoreInPlace() -> Bool { true }\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_findings_are_advisory_never_gating(self) -> None:
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "/// Loads the config for `frobnicate_widget`.\n"
                "/// Writes the resulting struct to disk.\n"
                "fn save_config() {}\n",
            )
            repo.commit()

            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["--repo-root", str(repo.root)])

        self.assertEqual(code, 0)

    def test_findings_have_gate_false(self) -> None:
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "/// Loads the config for `frobnicate_widget`.\n"
                "/// Writes the resulting struct to disk.\n"
                "fn save_config() {}\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertTrue(findings)
        self.assertTrue(all(not f.gate for f in findings))


if __name__ == "__main__":
    unittest.main()
