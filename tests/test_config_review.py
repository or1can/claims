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

"""Tests for `claims.config_review`'s mechanical helper (ticket #22).

Exercises `config_value_matches(repo_root, config)` against a fixture git
repo, asserting on the returned `ConfigValueMatch` list — the same
seam-level style as every check's own tests (spec.md's Testing Decisions),
even though this isn't a registered check itself.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from claims.config_review import (
    EXTENSION_CONFIG_KEYS,
    GLOB_CONFIG_KEYS,
    NO_PATH_SHAPED_CONFIG,
    config_value_matches,
)

from support import Repo, every_check_name


class ConfigValueMatchesTests(unittest.TestCase):
    def test_a_glob_matching_a_tracked_file_reports_it(self) -> None:
        with Repo() as repo:
            repo.write("skip.md", "prose\n")
            matches = config_value_matches(
                repo.root, {"check-links": {"exclude": ["skip.md"]}}
            )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].check, "check-links")
        self.assertEqual(matches[0].key, "exclude")
        self.assertEqual(matches[0].value, "skip.md")
        self.assertEqual(matches[0].matched_files, ("skip.md",))

    def test_a_glob_matching_nothing_reports_an_empty_match(self) -> None:
        with Repo() as repo:
            repo.write("real.md", "prose\n")
            matches = config_value_matches(
                repo.root, {"check-links": {"exclude": ["nonexistent.md"]}}
            )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].matched_files, ())

    def test_a_bare_string_value_is_coerced_the_same_as_a_check_itself_would(
        self,
    ) -> None:
        with Repo() as repo:
            repo.write("skip.md", "prose\n")
            matches = config_value_matches(
                repo.root, {"check-links": {"exclude": "skip.md"}}
            )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].matched_files, ("skip.md",))

    def test_an_extension_value_is_matched_by_suffix_not_glob(self) -> None:
        with Repo() as repo:
            repo.write("lib.rs", "fn main() {}\n")
            matches = config_value_matches(
                repo.root, {"restatement": {"extensions": [".rs"]}}
            )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].check, "restatement")
        self.assertEqual(matches[0].key, "extensions")
        self.assertEqual(matches[0].matched_files, ("lib.rs",))

    def test_an_extension_matching_nothing_reports_an_empty_match(self) -> None:
        with Repo() as repo:
            repo.write("lib.py", "x = 1\n")
            matches = config_value_matches(
                repo.root, {"restatement": {"extensions": [".rs"]}}
            )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].matched_files, ())

    def test_stale_claims_own_exclude_key_is_reviewed_too(self) -> None:
        # `stale-claims` was the one check missing `exclude` from
        # `GLOB_CONFIG_KEYS` alongside its own `module_reference_scope`
        # (ticket #43) — pinned separately so a future key added to an
        # already-listed check can't silently go unreviewed the way this
        # one briefly did.
        with Repo() as repo:
            repo.write("real.md", "prose\n")
            matches = config_value_matches(
                repo.root, {"stale-claims": {"exclude": ["nonexistent.md"]}}
            )
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].check, "stale-claims")
        self.assertEqual(matches[0].key, "exclude")
        self.assertEqual(matches[0].matched_files, ())

    def test_historical_key_is_reviewed_for_both_checks_that_take_it(self) -> None:
        # `historical` reached `check-links` (#50) and `check-file-refs`
        # (#57) without either landing here, so a mistyped glob in it
        # silently resolved every mention against the working tree only.
        with Repo() as repo:
            repo.write("real.md", "prose\n")
            matches = config_value_matches(
                repo.root,
                {
                    "check-links": {"historical": ["nonexistent.md"]},
                    "check-file-refs": {"historical": ["nonexistent.md"]},
                },
            )
        self.assertEqual(
            sorted((m.check, m.key, m.matched_files) for m in matches),
            [
                ("check-file-refs", "historical", ()),
                ("check-links", "historical", ()),
            ],
        )

    def test_a_non_glob_key_in_a_known_check_is_ignored(self) -> None:
        # `executable-claims`' own `permitted_prefixes` is a literal
        # command-string prefix, not a file glob — it has no "matches
        # nothing in the tracked tree" fact to compute at all.
        with Repo() as repo:
            repo.write("doc.md", "prose\n")
            matches = config_value_matches(
                repo.root,
                {"executable-claims": {"permitted_prefixes": ["npm test"], "timeout": 5}},
            )
        self.assertEqual(matches, [])

    def test_an_unrecognized_check_section_is_ignored_not_crashed_on(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", "prose\n")
            matches = config_value_matches(repo.root, {"not-a-real-check": {"exclude": ["*"]}})
        self.assertEqual(matches, [])

    def test_empty_config_produces_no_matches(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", "prose\n")
            matches = config_value_matches(repo.root, {})
        self.assertEqual(matches, [])

    def test_multiple_checks_each_produce_their_own_entries(self) -> None:
        with Repo() as repo:
            repo.write("a.md", "prose\n")
            repo.write("b.md", "prose\n")
            matches = config_value_matches(
                repo.root,
                {
                    "check-links": {"exclude": ["a.md"]},
                    "claim-words": {"files": ["b.md"]},
                },
            )
        by_check = {m.check: m for m in matches}
        self.assertEqual(len(matches), 2)
        self.assertEqual(by_check["check-links"].matched_files, ("a.md",))
        self.assertEqual(by_check["claim-words"].matched_files, ("b.md",))

    def test_every_registered_check_is_accounted_for_exactly_once(self) -> None:
        # A future check adding a glob/extension-shaped key without
        # updating this module's own maps would otherwise just never be
        # reviewed — silently, the exact failure class this helper exists
        # to catch in a project's own config. This fails loud instead.
        # Compared against every check module `claims/checks/` actually
        # has on disk (`every_check_name`), not a second
        # hand-maintained list — a name appearing in more than one of the
        # three sets is also a contradiction (claiming both "has nothing
        # path-shaped" and "has this path-shaped key"), so disjointness is
        # asserted too, to make "exactly once" real rather than assumed.
        glob_names = set(GLOB_CONFIG_KEYS)
        extension_names = set(EXTENSION_CONFIG_KEYS)
        self.assertTrue(NO_PATH_SHAPED_CONFIG.isdisjoint(glob_names | extension_names))
        accounted_for = glob_names | extension_names | NO_PATH_SHAPED_CONFIG
        self.assertEqual(accounted_for, every_check_name())

    def test_a_non_repo_path_raises_rather_than_reporting_false_zero_matches(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as not_a_repo:
            with self.assertRaises(ValueError):
                config_value_matches(
                    Path(not_a_repo), {"check-links": {"exclude": ["*.md"]}}
                )

    def test_a_subdirectory_of_a_repo_raises_rather_than_scoping_silently(self) -> None:
        # `tracked_files` runs `git ls-files` scoped to git's own cwd, so
        # from a subdirectory it silently returns only that subdirectory's
        # own tracked files, rebased to it — a root-anchored glob could
        # then never match anything, misreporting every value as stale.
        with Repo() as repo:
            repo.write("sub/a.md", "prose\n")
            with self.assertRaises(ValueError):
                config_value_matches(
                    repo.root / "sub", {"check-links": {"exclude": ["a.md"]}}
                )

    def test_a_malformed_value_reports_an_error_not_a_crash(self) -> None:
        with Repo() as repo:
            repo.write("doc.md", "prose\n")
            matches = config_value_matches(repo.root, {"check-links": {"exclude": 5}})
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].matched_files, ())
        self.assertIsNotNone(matches[0].error)
        self.assertIn("not iterable", matches[0].error or "")

    def test_a_malformed_value_does_not_prevent_other_checks_own_facts(self) -> None:
        with Repo() as repo:
            repo.write("a.md", "prose\n")
            matches = config_value_matches(
                repo.root,
                {
                    "check-links": {"exclude": 5},
                    "claim-words": {"files": ["a.md"]},
                },
            )
        by_check = {m.check: m for m in matches}
        self.assertIsNotNone(by_check["check-links"].error)
        self.assertIsNone(by_check["claim-words"].error)
        self.assertEqual(by_check["claim-words"].matched_files, ("a.md",))


if __name__ == "__main__":
    unittest.main()
