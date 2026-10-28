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

"""Tests for the git `pre-commit` hook command: `claims.pre_commit`.

Asserts on the exit code and stderr alone, the only two things git and a
hook manager read from it (#127).
"""

from __future__ import annotations

import io
import sys
import unittest
from unittest import mock

from claims.checks import check_file_refs, check_links
from claims.pre_commit import main
from claims.runner import Finding, clear_registry, register_check

from support import RegistryClearingTestCase, Repo


def _register(name: str, *, gate: bool) -> None:
    register_check(
        name,
        lambda repo_root, diff_range, config: [
            Finding(file="a.md", line=1, message="bad", mode=name, gate=gate)
        ],
    )


class PreCommitTests(RegistryClearingTestCase):
    def _run(self, repo: Repo, claims_toml: str | None = "") -> tuple[int, str]:
        if claims_toml is not None:
            (repo.root / "claims.toml").write_text(claims_toml)
        stderr = io.StringIO()
        code = main(repo.root, stderr)
        return code, stderr.getvalue()

    def test_no_claims_toml_exits_0_silently(self) -> None:
        _register("failing-gate", gate=True)
        with Repo() as repo:
            self.assertEqual(self._run(repo, claims_toml=None), (0, ""))

    def test_hook_enabled_false_exits_0_silently(self) -> None:
        _register("failing-gate", gate=True)
        with Repo() as repo:
            result = self._run(repo, "[hook]\nenabled = false\n")
        self.assertEqual(result, (0, ""))

    def test_a_check_with_enabled_false_is_filtered_out(self) -> None:
        _register("failing-gate", gate=True)
        with Repo() as repo:
            result = self._run(repo, "[failing-gate]\nenabled = false\n")
        self.assertEqual(result, (0, ""))

    def test_a_check_with_enabled_false_has_its_advisory_findings_filtered_out(
        self,
    ) -> None:
        _register("advisory-check", gate=False)
        with Repo() as repo:
            result = self._run(repo, "[advisory-check]\nenabled = false\n")
        self.assertEqual(result, (0, ""))

    def test_a_check_with_enabled_false_does_not_affect_other_checks(self) -> None:
        _register("failing-gate", gate=True)
        register_check("clean-check", lambda repo_root, diff_range, config: [])
        with Repo() as repo:
            code, _ = self._run(repo, "[clean-check]\nenabled = false\n")
        self.assertEqual(code, 1)

    def test_a_check_with_enabled_false_filters_its_suffixed_modes_too(self) -> None:
        # A check reporting more than one mode names each `{name}-suffix`
        # (`restatement`'s `-ngram`/`-whole-line`, and others), so an
        # exact `mode == name` match would silently disable nothing.
        register_check(
            "multi-mode-check",
            lambda repo_root, diff_range, config: [
                Finding(
                    file="a.md",
                    line=1,
                    message="bad",
                    mode="multi-mode-check-some-suffix",
                    gate=True,
                )
            ],
        )
        with Repo() as repo:
            result = self._run(repo, "[multi-mode-check]\nenabled = false\n")
        self.assertEqual(result, (0, ""))

    def test_a_top_level_non_table_value_blocks_rather_than_crashing(self) -> None:
        # A bare `enabled = false` with no `[section]` is valid TOML whose
        # value is a bool, not a table: the unrecognized-table gate
        # finding (ticket #21) blocks, where a crash would fail open.
        register_check("any-check", lambda repo_root, diff_range, config: [])
        with Repo() as repo:
            code, _ = self._run(repo, "enabled = false\n")
        self.assertEqual(code, 1)

    def test_disabling_the_fixed_config_mode_name_does_not_silence_it(self) -> None:
        # `"config"` is the unrecognized-table finding's own fixed mode
        # (ticket #21); `[config] enabled = false` must not silence the
        # one finding that warns about a `claims.toml` mistake.
        register_check("any-check", lambda repo_root, diff_range, config: [])
        with Repo() as repo:
            code, stderr = self._run(
                repo, "[config]\nenabled = false\n[not-a-real-check]\nx = 1\n"
            )
        self.assertEqual(code, 1)
        self.assertIn("not-a-real-check", stderr)

    def test_an_unregistered_name_does_not_wildcard_match_real_checks(self) -> None:
        # `[check] enabled = false` must not silence every `check-*` check
        # because their modes start with `check-`.
        _register("check-something", gate=True)
        with Repo() as repo:
            code, _ = self._run(repo, "[check]\nenabled = false\n")
        self.assertEqual(code, 1)

    def _run_on_removal(self, line: str) -> tuple[int, str]:
        # #116, end to end: the commit recording a removal in a `historical`
        # file is the one making it, so the line is uncommitted when the
        # hook runs and has to be admitted on `HEAD`'s tree.
        clear_registry()
        register_check(check_file_refs.NAME, check_file_refs.check)
        register_check(check_links.NAME, check_links.check)
        with Repo() as repo:
            repo.write("tools/a.py", "x = 1\n")
            repo.write("CHANGELOG.md", "# Changelog\n")
            repo.write(
                "claims.toml",
                '[check-file-refs]\nhistorical = ["CHANGELOG.md"]\n'
                '[check-links]\nhistorical = ["CHANGELOG.md"]\n',
            )
            repo.commit()
            repo.rm("tools/a.py")
            repo.write("CHANGELOG.md", f"# Changelog\n{line}\n")
            return self._run(repo, claims_toml=None)

    def test_recording_a_removal_in_the_commit_that_makes_it_is_allowed(self) -> None:
        for line in ("- Delete `tools/a.py`.", "- Delete [a](tools/a.py)."):
            with self.subTest(line=line):
                self.assertEqual(self._run_on_removal(line), (0, ""))

    def test_a_misspelled_removal_is_still_blocked(self) -> None:
        for line in ("- Delete `tools/b.py`.", "- Delete [a](tools/b.py)."):
            with self.subTest(line=line):
                code, stderr = self._run_on_removal(line)
                self.assertEqual(code, 1)
                self.assertIn("nor at HEAD", stderr)

    def test_an_invalid_claims_toml_exits_1_with_the_reason(self) -> None:
        register_check("clean-check", lambda repo_root, diff_range, config: [])
        with Repo() as repo:
            code, stderr = self._run(repo, "not valid toml [[[")
        self.assertEqual(code, 1)
        self.assertIn("claims.toml is invalid", stderr)

    def test_zero_checks_registered_exits_1(self) -> None:
        with Repo() as repo:
            code, stderr = self._run(repo)
        self.assertEqual(code, 1)
        self.assertIn("0 checked", stderr)

    def test_a_gate_finding_exits_1_with_the_summary(self) -> None:
        _register("failing-gate", gate=True)
        _register("advisory-check", gate=False)
        with Repo() as repo:
            code, stderr = self._run(repo)
        self.assertEqual(code, 1)
        self.assertIn("a.md:1", stderr)
        self.assertIn("failing-gate", stderr)
        self.assertIn("advisory-check", stderr)

    def test_advisory_findings_only_exits_0_with_the_summary(self) -> None:
        _register("advisory-check", gate=False)
        with Repo() as repo:
            code, stderr = self._run(repo)
        self.assertEqual(code, 0)
        self.assertIn("a.md:1", stderr)
        self.assertIn("advisory-check", stderr)

    def test_clean_exits_0_silently(self) -> None:
        register_check("clean-check", lambda repo_root, diff_range, config: [])
        with Repo() as repo:
            self.assertEqual(self._run(repo), (0, ""))

    def test_an_unexpected_exception_fails_open_with_a_warning(self) -> None:
        _register("failing-gate", gate=True)
        with Repo() as repo, mock.patch(
            "claims.gate.run", side_effect=RuntimeError("boom")
        ):
            code, stderr = self._run(repo)
        self.assertEqual(code, 0)
        self.assertIn("boom", stderr)
        self.assertIn("not checked", stderr)

    def test_a_check_that_fails_to_import_fails_open_with_a_warning(self) -> None:
        # A broken install most often fails at import, before any check runs.
        with Repo() as repo, mock.patch.dict(sys.modules, {"claims.gate": None}):
            code, stderr = self._run(repo)
        self.assertEqual(code, 0)
        self.assertIn("not checked", stderr)


if __name__ == "__main__":
    unittest.main()
