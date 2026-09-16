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

"""Tests for the `check-cli-flags` check: `claims.checks.check_cli_flags`.

Exercises the shared `run(repo_root, diff_range, config)` seam against
fixture git repos — see spec.md's Testing Decisions. Uses real, executable
script fixtures (this check runs `<script> --help` for real) rather than
mocking `subprocess`, matching `test_executable_claims.py`'s own precedent
of exercising real execution.
"""

from __future__ import annotations

import stat
from pathlib import Path

from claims.checks.check_cli_flags import NAME, check
from claims.config import load_config
from claims.runner import Finding, register_check, run

from support import RegistryClearingTestCase, Repo


def _toml_string(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def grant(repo_root: Path, *, allow: tuple[str, ...] = (), deny: tuple[str, ...] = ()) -> None:
    lines = ["[check-cli-flags]"]
    if allow:
        lines.append("allowed = [" + ", ".join(_toml_string(c) for c in allow) + "]")
    if deny:
        lines.append("denied = [" + ", ".join(_toml_string(c) for c in deny) + "]")
    (repo_root / "claims.local.toml").write_text("\n".join(lines) + "\n")


def write_script(repo: Repo, rel: str, body: str) -> str:
    """Writes a real, executable script at `rel` — this check runs
    `<script> --help` for real, matching `test_executable_claims.py`'s
    own precedent of exercising real subprocess execution rather than
    mocking it.
    """

    repo.write(rel, body)
    path = repo.root / rel
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return rel


ARGPARSE_SCRIPT = """#!/usr/bin/env python3
import argparse
p = argparse.ArgumentParser()
p.add_argument("--normalize", action="store_true")
p.parse_args()
"""

NO_NORMALIZE_SCRIPT = """#!/usr/bin/env python3
import argparse
p = argparse.ArgumentParser()
p.add_argument("--verbose", action="store_true")
p.parse_args()
"""

FAILING_SCRIPT = """#!/usr/bin/env python3
import sys
sys.exit(1)
"""


class CheckCliFlagsTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def _findings(self, repo_root: Path) -> list[Finding]:
        return list(run(repo_root, "HEAD", {}).findings)

    def _findings_with_config(self, repo_root: Path, claims_toml: str) -> list[Finding]:
        (repo_root / "claims.toml").write_text(claims_toml)
        config = load_config(repo_root)
        return list(run(repo_root, "HEAD", config).findings)

    def test_a_single_invocation_claim_with_flag_present_produces_no_finding(
        self,
    ) -> None:
        with Repo() as repo:
            script = write_script(repo, "tools/warm_cache.py", ARGPARSE_SCRIPT)
            repo.write("README.md", f"Run `{script} --normalize` to normalize.\n")
            repo.commit()
            grant(repo.root, allow=(f"{script} --help",))
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_single_invocation_claim_with_flag_missing_is_flagged(self) -> None:
        with Repo() as repo:
            script = write_script(repo, "tools/warm_cache.py", NO_NORMALIZE_SCRIPT)
            repo.write("README.md", f"Run `{script} --normalize` to normalize.\n")
            repo.commit()
            grant(repo.root, allow=(f"{script} --help",))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "README.md:1")
        self.assertFalse(findings[0].gate)
        self.assertIn(script, findings[0].message)
        self.assertIn("--normalize", findings[0].message)

    def test_two_separate_backtick_mentions_on_one_line_are_detected(self) -> None:
        with Repo() as repo:
            script = write_script(repo, "tools/warm_cache.py", NO_NORMALIZE_SCRIPT)
            repo.write(
                "README.md", f"The `{script}` script supports `--normalize`.\n"
            )
            repo.commit()
            grant(repo.root, allow=(f"{script} --help",))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("--normalize", findings[0].message)

    def test_a_bare_flag_with_no_script_context_is_not_a_candidate(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "Pass `--normalize` for consistent output.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_an_ungranted_command_is_advisory_not_gate(self) -> None:
        with Repo() as repo:
            script = write_script(repo, "tools/warm_cache.py", ARGPARSE_SCRIPT)
            repo.write("README.md", f"Run `{script} --normalize` to normalize.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertFalse(findings[0].gate)
        self.assertIn("has no local grant", findings[0].message)

    def test_a_denied_command_is_skipped_as_advisory(self) -> None:
        with Repo() as repo:
            script = write_script(repo, "tools/warm_cache.py", ARGPARSE_SCRIPT)
            repo.write("README.md", f"Run `{script} --normalize` to normalize.\n")
            repo.commit()
            grant(repo.root, deny=(f"{script} --help",))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertFalse(findings[0].gate)
        self.assertIn("denied", findings[0].message)

    def test_a_failing_help_invocation_is_inconclusive_not_confirmed_false(
        self,
    ) -> None:
        with Repo() as repo:
            script = write_script(repo, "tools/warm_cache.py", FAILING_SCRIPT)
            repo.write("README.md", f"Run `{script} --normalize` to normalize.\n")
            repo.commit()
            grant(repo.root, allow=(f"{script} --help",))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertFalse(findings[0].gate)
        self.assertIn("could not be verified", findings[0].message)
        self.assertNotIn("does not appear to support", findings[0].message)

    def test_a_timed_out_help_invocation_is_inconclusive(self) -> None:
        sleep_script = "#!/usr/bin/env python3\nimport time\ntime.sleep(1)\n"
        with Repo() as repo:
            script = write_script(repo, "tools/slow.py", sleep_script)
            repo.write("README.md", f"Run `{script} --normalize` to normalize.\n")
            repo.commit()
            grant(repo.root, allow=(f"{script} --help",))
            findings = self._findings_with_config(
                repo.root, "[check-cli-flags]\ntimeout = 0.05\n"
            )
        self.assertEqual(len(findings), 1)
        self.assertFalse(findings[0].gate)
        self.assertIn("timed out", findings[0].message)

    def test_a_tracked_local_grant_file_is_a_gate_finding(self) -> None:
        # The one exception to this check's otherwise-blanket advisory
        # severity: a tracked claims.local.toml is a real security
        # compromise indicator, matching #15's own precedent.
        with Repo() as repo:
            script = write_script(repo, "tools/warm_cache.py", ARGPARSE_SCRIPT)
            repo.write("README.md", f"Run `{script} --normalize` to normalize.\n")
            repo.write(
                "claims.local.toml",
                f'[check-cli-flags]\nallowed = ["{script} --help"]\n',
            )
            repo.commit()
            findings = self._findings(repo.root)
        messages = [f.message for f in findings]
        self.assertTrue(any("is tracked by git" in m for m in messages))
        self.assertTrue(all(f.gate for f in findings if "is tracked by git" in f.message))

    def test_an_excluded_path_is_not_swept_for_candidates(self) -> None:
        with Repo() as repo:
            script = write_script(repo, "tools/warm_cache.py", NO_NORMALIZE_SCRIPT)
            repo.write(
                "notes/history.md", f"Run `{script} --normalize` to normalize.\n"
            )
            repo.commit()
            grant(repo.root, allow=(f"{script} --help",))
            findings = self._findings_with_config(
                repo.root, '[check-cli-flags]\nexclude = ["notes/*.md"]\n'
            )
        self.assertEqual(findings, [])

    def test_exclude_does_not_affect_a_non_matching_path(self) -> None:
        with Repo() as repo:
            script = write_script(repo, "tools/warm_cache.py", NO_NORMALIZE_SCRIPT)
            repo.write("README.md", f"Run `{script} --normalize` to normalize.\n")
            repo.commit()
            grant(repo.root, allow=(f"{script} --help",))
            findings = self._findings_with_config(
                repo.root, '[check-cli-flags]\nexclude = ["notes/*.md"]\n'
            )
        self.assertEqual(len(findings), 1)

    def test_an_extensionless_command_is_not_a_candidate(self) -> None:
        # Known, documented gap: only a path-shaped script ending in a
        # recognized extension is detected as a "script" — a bare command
        # name (docker, npm, git) isn't, since there's no reliable way to
        # tell a real CLI tool name from any other backticked word without
        # a vocabulary of known tools.
        with Repo() as repo:
            repo.write("README.md", "Run `docker --normalize` to normalize.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_short_flag_is_detected_too(self) -> None:
        script_body = (
            "#!/usr/bin/env python3\nimport argparse\n"
            "p = argparse.ArgumentParser()\np.add_argument('-n')\np.parse_args()\n"
        )
        with Repo() as repo:
            script = write_script(repo, "tools/warm_cache.py", script_body)
            repo.write("README.md", f"Run `{script} -n` to normalize.\n")
            repo.commit()
            grant(repo.root, allow=(f"{script} --help",))
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_repo_root_script_with_no_slash_is_run_via_dot_slash(self) -> None:
        # `manage.py` (no `/`) is a $PATH lookup, not "the tracked script
        # at the repo root" — must be run (and granted) as `./manage.py`,
        # not the bare name, or a repo-root script claim can never be
        # verified (and could silently run an unrelated same-named binary
        # if one happens to be on $PATH).
        with Repo() as repo:
            script = write_script(repo, "manage.py", ARGPARSE_SCRIPT)
            repo.write("README.md", f"Run `{script} --normalize` to normalize.\n")
            repo.commit()
            grant(repo.root, allow=(f"./{script} --help",))
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_repo_root_script_grant_must_include_the_dot_slash(self) -> None:
        with Repo() as repo:
            script = write_script(repo, "manage.py", ARGPARSE_SCRIPT)
            repo.write("README.md", f"Run `{script} --normalize` to normalize.\n")
            repo.commit()
            # Granting the bare name (no ./) does not match the command
            # this check actually runs — it should still gate as ungranted.
            grant(repo.root, allow=(f"{script} --help",))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("has no local grant", findings[0].message)

    def test_two_claims_on_different_lines_each_get_their_own_finding(self) -> None:
        with Repo() as repo:
            script = write_script(repo, "tools/warm_cache.py", NO_NORMALIZE_SCRIPT)
            repo.write(
                "README.md",
                f"Run `{script} --normalize` first.\n"
                f"Then run `{script} --normalize` again.\n",
            )
            repo.commit()
            grant(repo.root, allow=(f"{script} --help",))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 2)
        self.assertEqual({f.citation for f in findings}, {"README.md:1", "README.md:2"})

    def test_a_candidate_inside_a_fenced_code_block_is_not_detected(self) -> None:
        with Repo() as repo:
            script = write_script(repo, "tools/warm_cache.py", NO_NORMALIZE_SCRIPT)
            repo.write(
                "README.md",
                f"Example:\n\n```markdown\nRun `{script} --normalize` here.\n```\n",
            )
            repo.commit()
            grant(repo.root, allow=(f"{script} --help",))
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_candidate_outside_a_fence_is_still_flagged(self) -> None:
        with Repo() as repo:
            script = write_script(repo, "tools/warm_cache.py", NO_NORMALIZE_SCRIPT)
            repo.write(
                "README.md",
                f"```markdown\nRun `{script} --normalize` here.\n```\n\n"
                f"Also run `{script} --normalize` for real.\n",
            )
            repo.commit()
            grant(repo.root, allow=(f"{script} --help",))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "README.md:5")

    def test_a_missing_tracked_file_does_not_crash_the_check(self) -> None:
        # A stale index entry (tracked but deleted from the working tree)
        # must not turn this advisory check into a gate crash finding.
        with Repo() as repo:
            repo.write("README.md", "prose\n")
            repo.commit()
            (repo.root / "README.md").unlink()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_short_flag_is_not_confirmed_by_a_longer_flags_substring(self) -> None:
        # `-n` must not be "supported" merely because it's a substring of
        # a real `--normalize` in the script's own --help text.
        with Repo() as repo:
            script = write_script(repo, "tools/warm_cache.py", ARGPARSE_SCRIPT)
            repo.write("README.md", f"Run `{script} -n` to normalize.\n")
            repo.commit()
            grant(repo.root, allow=(f"{script} --help",))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("-n", findings[0].message)

    def test_a_flag_is_not_confirmed_by_being_a_prefix_of_a_longer_flag(self) -> None:
        # `--norm` must not be "supported" merely because it's a prefix of
        # a real `--normalize` in the script's own --help text.
        with Repo() as repo:
            script = write_script(repo, "tools/warm_cache.py", ARGPARSE_SCRIPT)
            repo.write("README.md", f"Run `{script} --norm` to normalize.\n")
            repo.commit()
            grant(repo.root, allow=(f"{script} --help",))
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("--norm", findings[0].message)


if __name__ == "__main__":
    import unittest

    unittest.main()
