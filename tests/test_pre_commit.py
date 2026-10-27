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

from claims.pre_commit import main
from claims.runner import Finding, register_check

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
