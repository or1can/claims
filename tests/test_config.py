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

"""Tests for per-project config loading: `claims.config`."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from claims.config import ConfigError, append_only, load_config, load_local_config


class ConfigTests(unittest.TestCase):
    def test_missing_config_file_yields_empty_config(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            self.assertEqual(load_config(Path(repo_root)), {})

    def test_malformed_config_file_raises_configerror(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            (Path(repo_root) / "claims.toml").write_text("not valid toml [[[")
            with self.assertRaises(ConfigError):
                load_config(Path(repo_root))

    def test_each_top_level_table_is_one_checks_section(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            (Path(repo_root) / "claims.toml").write_text(
                '[executable-claims]\ntimeout = 30\n\n'
                '[restatement]\nfile_types = ["*.md"]\n'
            )
            config = load_config(Path(repo_root))

        self.assertEqual(config["executable-claims"], {"timeout": 30})
        self.assertEqual(config["restatement"], {"file_types": ["*.md"]})

    def test_missing_local_config_file_yields_empty_config(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            self.assertEqual(load_local_config(Path(repo_root)), {})

    def test_malformed_local_config_file_raises_configerror(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            (Path(repo_root) / "claims.local.toml").write_text("not valid toml [[[")
            with self.assertRaises(ConfigError):
                load_local_config(Path(repo_root))

    def test_local_config_is_read_from_its_own_file_not_claims_toml(self) -> None:
        with tempfile.TemporaryDirectory() as repo_root:
            (Path(repo_root) / "claims.toml").write_text(
                '[executable-claims]\ntimeout = 30\n'
            )
            (Path(repo_root) / "claims.local.toml").write_text(
                '[executable-claims]\nallowed = ["true"]\n'
            )
            local_config = load_local_config(Path(repo_root))

        self.assertEqual(local_config, {"executable-claims": {"allowed": ["true"]}})



class AppendOnlyTests(unittest.TestCase):
    def _load(self, claims_toml: str) -> dict[str, dict[str, object]]:
        with tempfile.TemporaryDirectory() as repo_root:
            (Path(repo_root) / "claims.toml").write_text(claims_toml)
            return load_config(Path(repo_root))

    def test_changelog_is_append_only_built_in(self) -> None:
        self.assertTrue(append_only({}, "CHANGELOG.md"))
        self.assertFalse(append_only({}, "README.md"))

    def test_a_listed_glob_adds_to_the_built_in(self) -> None:
        config = self._load('[subjects]\nappend_only = ["notes/*.md"]\n')

        self.assertTrue(append_only(config, "notes/2026.md"))
        self.assertTrue(append_only(config, "CHANGELOG.md"))
        self.assertFalse(append_only(config, "README.md"))

    def test_a_bare_string_is_a_one_element_list(self) -> None:
        config = self._load('[subjects]\nappend_only = "RELEASES.md"\n')

        self.assertTrue(append_only(config, "RELEASES.md"))
        self.assertFalse(append_only(config, "R"))

    def test_a_wrong_typed_value_is_invalid_config(self) -> None:
        for claims_toml in (
            "[subjects]\nappend_only = 3\n",
            "[subjects]\nappend_only = [3]\n",
            'subjects = "CHANGELOG.md"\n',
        ):
            with self.subTest(claims_toml=claims_toml), self.assertRaises(ConfigError):
                self._load(claims_toml)


if __name__ == "__main__":
    unittest.main()
