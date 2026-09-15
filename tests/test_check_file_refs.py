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

"""Tests for the `check-file-refs` check: `claims.checks.check_file_refs`.

Exercises the shared `run(repo_root, diff_range, config)` seam against
fixture git repos — see spec.md's Testing Decisions.
"""

from __future__ import annotations

from pathlib import Path

from claims.checks.check_file_refs import NAME, check
from claims.config import load_config
from claims.runner import Finding, register_check, run

from support import RegistryClearingTestCase, Repo


class CheckFileRefsTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(NAME, check)

    def _findings(self, repo_root: Path) -> list[Finding]:
        return list(run(repo_root, "HEAD", {}).findings)

    def _findings_with_config(self, repo_root: Path, claims_toml: str) -> list[Finding]:
        (repo_root / "claims.toml").write_text(claims_toml)
        config = load_config(repo_root)
        return list(run(repo_root, "HEAD", config).findings)

    def test_a_bare_prose_reference_to_a_missing_file_is_flagged(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "See scripts/build.py for the build steps.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].citation, "README.md:1")
        self.assertTrue(findings[0].gate)
        self.assertIn("scripts/build.py", findings[0].message)

    def test_a_bare_prose_reference_to_an_existing_file_is_not_flagged(self) -> None:
        with Repo() as repo:
            repo.write("scripts/build.py", "print('hi')\n")
            repo.write("README.md", "See scripts/build.py for the build steps.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_version_number_lookalike_is_not_a_candidate(self) -> None:
        # `api/v2.0` matches stale-claims' own untightened PATH_RE (any
        # alphanumeric run counts as an "extension" there) — the whole
        # point of this check's own recognized-extension set is that
        # `.0` isn't one, so this is never even a candidate.
        with Repo() as repo:
            repo.write("README.md", "Use api/v2.0 or getting-started/v1.2.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_path_already_inside_real_link_syntax_is_not_independently_flagged(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write("README.md", "See [the build script](scripts/build.py).\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_bare_mention_alongside_a_separate_real_link_is_still_flagged(self) -> None:
        # The link-syntax exclusion is span-scoped, not line-scoped — a
        # second, genuinely bare mention on the same line must still be
        # caught even though the line also contains real link syntax.
        with Repo() as repo:
            repo.write(
                "README.md",
                "See [the docs](docs/guide.md), unlike scripts/missing.py.\n",
            )
            repo.write("docs/guide.md", "prose\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("scripts/missing.py", findings[0].message)

    def test_an_extension_outside_the_recognized_set_is_not_a_candidate(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "See assets/logo.xyz for the mark.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_project_can_add_an_extension_without_losing_the_defaults(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "See assets/logo.xyz and scripts/build.py.\n")
            repo.commit()
            findings = self._findings_with_config(
                repo.root, '[check-file-refs]\nextensions = [".xyz"]\n'
            )
        messages = [f.message for f in findings]
        self.assertTrue(any("assets/logo.xyz" in m for m in messages))
        self.assertTrue(any("scripts/build.py" in m for m in messages))
        self.assertEqual(len(findings), 2)

    def test_a_bare_string_extensions_value_is_coerced_to_one_element(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "See assets/logo.xyz for the mark.\n")
            repo.commit()
            findings = self._findings_with_config(
                repo.root, '[check-file-refs]\nextensions = ".xyz"\n'
            )
        self.assertEqual(len(findings), 1)
        self.assertIn("assets/logo.xyz", findings[0].message)

    def test_an_excluded_path_is_skipped_entirely(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "See scripts/build.py for the build steps.\n")
            repo.commit()
            findings = self._findings_with_config(
                repo.root, '[check-file-refs]\nexclude = ["README.md"]\n'
            )
        self.assertEqual(findings, [])

    def test_exclude_does_not_affect_a_non_matching_path(self) -> None:
        with Repo() as repo:
            repo.write("README.md", "See scripts/build.py for the build steps.\n")
            repo.commit()
            findings = self._findings_with_config(
                repo.root, '[check-file-refs]\nexclude = ["other.md"]\n'
            )
        self.assertEqual(len(findings), 1)

    def test_no_findings_on_a_repo_with_no_markdown(self) -> None:
        with Repo() as repo:
            repo.write("main.py", "print('hi')\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_reference_to_a_real_hidden_directory_path_is_not_flagged(self) -> None:
        # A bare `\b` word-boundary anchor doesn't match between two
        # non-word characters — a space then a literal `.` — so a naive
        # regex silently drops the leading dot of a hidden-directory path
        # (`.claude/settings.json` becomes `claude/settings.json`, which
        # then never resolves) instead of matching the real path whole.
        with Repo() as repo:
            repo.write(".claude/settings.json", "{}\n")
            repo.write("README.md", "See .claude/settings.json for config.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_url_fragment_is_not_mistaken_for_a_file_path(self) -> None:
        # `https://example.com/install.sh` shouldn't be treated as a bare
        # file-path claim — `example.com/install.sh` is path-shaped and
        # its extension (`.sh`) is recognized, but it's part of a URL, not
        # a claim that a tracked file exists at that relative path.
        with Repo() as repo:
            repo.write(
                "README.md", "Run `curl https://example.com/install.sh | sh`.\n"
            )
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_leading_dot_slash_reference_to_a_real_file_is_not_flagged(self) -> None:
        # The `(?<![\w.-])` lookbehind that recovers a hidden-directory
        # path's own leading dot (see the hidden-directory test above)
        # also captures a `./` prefix whole — `./docs/guide.md` must still
        # resolve against the real `docs/guide.md`, not be compared
        # against the literal (never-tracked) string `./docs/guide.md`.
        with Repo() as repo:
            repo.write("docs/guide.md", "prose\n")
            repo.write("README.md", "See ./docs/guide.md for details.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_leading_dot_slash_reference_to_a_missing_file_is_still_flagged(
        self,
    ) -> None:
        # Distinguishes "strip the ./ and still check it" from "drop any
        # ./-prefixed mention as not a candidate at all" — the previous
        # test alone can't tell those apart, since a match either way
        # would be silent for an existing file.
        with Repo() as repo:
            repo.write("README.md", "See ./docs/nope.md for details.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("./docs/nope.md", findings[0].message)

    def test_a_leading_dot_dot_slash_reference_to_a_real_file_is_not_a_candidate(
        self,
    ) -> None:
        # `../CLAUDE.md` can never itself be a repo-root-relative tracked
        # path — resolving it correctly needs the citing file's own
        # directory (`check_links._resolve`'s job), which this check's
        # flat, repo-root-relative candidates don't track. Skipped as not
        # a candidate at all, rather than guessed at or falsely flagged.
        # The stripped form (`CLAUDE.md`) is deliberately real and tracked
        # here — a naive "just strip ../ like ./" implementation would
        # also pass this fixture, so it alone can't tell "skipped" from
        # "resolved"; the next test pins that distinction.
        with Repo() as repo:
            repo.write("CLAUDE.md", "prose\n")
            repo.write("docs/README.md", "See ../CLAUDE.md for the root doc.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_leading_dot_dot_slash_reference_to_a_missing_file_is_not_flagged(
        self,
    ) -> None:
        # If `../` were merely stripped (like `./`) rather than treated as
        # "not a candidate", `../nope.md` would strip to `nope.md`, fail
        # to resolve, and produce a finding — which would be a wrong
        # verdict here (a `../`-prefixed mention was never actually
        # claiming the repo-root-relative path `nope.md` exists). No
        # tracked file makes either interpretation's "does it resolve"
        # answer coincide, so this is what actually distinguishes
        # "skipped as not a candidate" from "stripped and checked".
        with Repo() as repo:
            repo.write("docs/README.md", "See ../nope.md for details.\n")
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_bare_mention_inside_a_fenced_code_block_is_not_a_candidate(self) -> None:
        # Example code inside a fenced block is illustrative, not a claim
        # that the named path is a real tracked file — the same
        # "documentation of the syntax itself" concern
        # `executable_claims._fence_state` exists for.
        with Repo() as repo:
            repo.write(
                "README.md",
                "Run this:\n\n```\npython scripts/train.py\n```\n",
            )
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_nested_fence_example_is_not_a_candidate(self) -> None:
        # CommonMark's real nesting rule (`executable_claims._fence_state`'s
        # own precedent): a fence only closes on a same-or-longer run of
        # backticks, so a 3-backtick example nested inside a 4-backtick
        # outer fence is still fully fenced content throughout, not just
        # its own opening/closing lines.
        with Repo() as repo:
            repo.write(
                "README.md",
                "````\n```\nscripts/train.py\n```\n````\n",
            )
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_fence_openers_own_info_string_is_not_scanned(self) -> None:
        # A real Docusaurus/MkDocs convention (`` ```json title="x.json" ``)
        # — the opening delimiter line's own trailing text must not be
        # scanned either, not just the lines strictly between delimiters.
        with Repo() as repo:
            repo.write(
                "README.md",
                '```json title="config/app.json"\n{}\n```\n',
            )
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(findings, [])

    def test_a_bare_mention_outside_a_fence_is_still_flagged(self) -> None:
        with Repo() as repo:
            repo.write(
                "README.md",
                "Run this:\n\n```\npython scripts/train.py\n```\n\n"
                "See scripts/other_missing.py too.\n",
            )
            repo.commit()
            findings = self._findings(repo.root)
        self.assertEqual(len(findings), 1)
        self.assertIn("scripts/other_missing.py", findings[0].message)


if __name__ == "__main__":
    import unittest

    unittest.main()
