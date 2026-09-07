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

from claims.config import ConfigError, load_config


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


if __name__ == "__main__":
    unittest.main()
