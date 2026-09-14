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

    def _findings(
        self, repo_root: Path, config: dict[str, object] | None = None
    ) -> list[Finding]:
        return list(run(repo_root, "HEAD", {NAME: config or {}}).findings)

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

    def test_unknown_mode_is_opt_in_a_rust_splice_naming_nothing_is_not_flagged_by_default(
        self,
    ) -> None:
        # `unknown` mode is off by default (ticket #9) — this fixture is
        # shaped exactly like a real false positive on dense doc comments:
        # an ordinary paragraph naming a real-looking-but-undeclared
        # backtick term, no blank `///` separating it from the run above.
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "/// Loads the config for `frobnicate_widget`.\n"
                "/// Writes the resulting struct to disk.\n"
                "fn save_config() {}\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_a_rust_splice_naming_nothing_in_the_repo_is_flagged_when_unknown_mode_enabled(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "/// Loads the config for `frobnicate_widget`.\n"
                "/// Writes the resulting struct to disk.\n"
                "fn save_config() {}\n",
            )
            repo.commit()

            findings = self._findings(repo.root, config={"modes": ["unknown"]})

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].mode, MODE_UNKNOWN)
        self.assertIn("frobnicate_widget", findings[0].message)

    def test_modes_naming_both_restores_default_and_unknown_output(self) -> None:
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "fn load_project() -> Project {}\n\n"
                "/// Loads the project's `load_project` config from disk.\n"
                "/// Converts the config into native TOML for `to_native_toml`.\n"
                "fn to_native_toml() -> Config {}\n",
            )
            repo.write(
                "src/other.rs",
                "/// Loads the config for `frobnicate_widget`.\n"
                "/// Writes the resulting struct to disk.\n"
                "fn save_config() {}\n",
            )
            repo.commit()

            findings = self._findings(
                repo.root, config={"modes": ["undocumented", "unknown"]}
            )

        self.assertEqual(
            {f.mode for f in findings}, {MODE_UNDOCUMENTED, MODE_UNKNOWN}
        )

    def test_modes_naming_only_unknown_suppresses_undocumented_findings(self) -> None:
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "fn load_project() -> Project {}\n\n"
                "/// Loads the project's `load_project` config from disk.\n"
                "/// Converts the config into native TOML for `to_native_toml`.\n"
                "fn to_native_toml() -> Config {}\n",
            )
            repo.commit()

            findings = self._findings(repo.root, config={"modes": ["unknown"]})

        # `load_project` and `to_native_toml` are both real declarations in
        # this file, so with `undocumented` disabled and `unknown` finding
        # nothing unresolvable, no findings survive at all.
        self.assertEqual(findings, [])

    def test_an_unrecognized_mode_is_a_clear_crash_finding(self) -> None:
        with Repo() as repo:
            repo.write("src/lib.rs", "fn save_config() {}\n")
            repo.commit()

            findings = self._findings(repo.root, config={"modes": ["bogus"]})

        self.assertEqual(len(findings), 1)
        self.assertIn("ConfigError", findings[0].message)
        self.assertIn("'bogus' is not a known mode", findings[0].message)

    def test_a_bare_string_mode_is_treated_as_one_mode_not_a_list_of_characters(
        self,
    ) -> None:
        # `modes = "unknown"` is a one-character typo away from the correct
        # `modes = ["unknown"]` — mirrors `exclude_patterns`'s own guard
        # against the identical string-vs-list-of-characters footgun.
        with Repo() as repo:
            repo.write(
                "src/lib.rs",
                "/// Loads the config for `frobnicate_widget`.\n"
                "/// Writes the resulting struct to disk.\n"
                "fn save_config() {}\n",
            )
            repo.commit()

            findings = self._findings(repo.root, config={"modes": "unknown"})

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].mode, MODE_UNKNOWN)

    def test_a_non_list_mode_config_is_a_clear_crash_finding(self) -> None:
        with Repo() as repo:
            repo.write("src/lib.rs", "fn save_config() {}\n")
            repo.commit()

            findings = self._findings(repo.root, config={"modes": 5})

        self.assertEqual(len(findings), 1)
        self.assertIn("ConfigError", findings[0].message)
        self.assertIn("modes must be a list of strings", findings[0].message)

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

    def test_unknown_mode_is_opt_in_a_swift_splice_naming_nothing_is_not_flagged_by_default(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write(
                "Sources/Room.swift",
                "/// Whether `canRestore` allows a restore.\n"
                "/// Blocks the restore for `restoreBlocker`.\n"
                "var restoreBlocker: Blocker? { nil }\n",
            )
            repo.commit()

            findings = self._findings(repo.root)

        self.assertEqual(findings, [])

    def test_a_swift_splice_naming_nothing_in_the_repo_is_flagged_when_unknown_mode_enabled(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write(
                "Sources/Room.swift",
                "/// Whether `canRestore` allows a restore.\n"
                "/// Blocks the restore for `restoreBlocker`.\n"
                "var restoreBlocker: Blocker? { nil }\n",
            )
            repo.commit()

            findings = self._findings(repo.root, config={"modes": ["unknown"]})

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
                "fn load_project() -> Project {}\n\n"
                "/// Loads the project's `load_project` config from disk.\n"
                "/// Converts the config into native TOML for `to_native_toml`.\n"
                "fn to_native_toml() -> Config {}\n",
            )
            repo.commit()

            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["--repo-root", str(repo.root)])

        self.assertEqual(code, 0)

    def test_findings_have_gate_false(self) -> None:
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

        self.assertTrue(findings)
        self.assertTrue(all(not f.gate for f in findings))


if __name__ == "__main__":
    unittest.main()
