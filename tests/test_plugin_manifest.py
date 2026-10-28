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

"""Structural checks on the Claude Code plugin manifest (ticket 18).

No live Claude Code session installs a plugin in CI, so this can't exercise
actual install/enable behaviour (that's ticket 19, against a real consuming
project). What it can check: the manifest files are valid, name each other
consistently, and every path they reference actually exists.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tomllib
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


def _load(relative_path: str) -> dict:
    return json.loads((REPO_ROOT / relative_path).read_text(encoding="utf-8"))


class PluginManifestTests(unittest.TestCase):
    def test_plugin_json_name_is_valid_kebab_case(self) -> None:
        manifest = _load(".claude-plugin/plugin.json")
        self.assertRegex(manifest["name"], NAME_RE)

    def test_plugin_json_component_paths_exist(self) -> None:
        manifest = _load(".claude-plugin/plugin.json")
        for path in manifest["skills"] + manifest["agents"] + [manifest["hooks"]]:
            self.assertTrue(path.startswith("./"), f"{path} must start with ./")
            self.assertTrue((REPO_ROOT / path).exists(), f"{path} does not exist")

    def test_skill_directory_has_a_skill_file(self) -> None:
        manifest = _load(".claude-plugin/plugin.json")
        for skill_dir in manifest["skills"]:
            self.assertTrue((REPO_ROOT / skill_dir / "SKILL.md").is_file())

    def test_agent_entry_is_a_file_with_required_frontmatter(self) -> None:
        # Unlike `skills`, which takes a directory, `agents` takes direct
        # file paths — `claude plugin validate` rejects a directory here
        # (caught by actually running it, not by this test, which used to
        # glob a directory and so never noticed the manifest passed one).
        manifest = _load(".claude-plugin/plugin.json")
        for agent_file in manifest["agents"]:
            path = REPO_ROOT / agent_file
            self.assertTrue(path.is_file(), f"{agent_file} is not a file")
            text = path.read_text(encoding="utf-8")
            self.assertIn("name:", text)
            self.assertIn("description:", text)

    def test_hooks_file_registers_only_the_nudge(self) -> None:
        # Git decides when a commit happens, through its own `pre-commit`
        # hook (#128, `decisions/0007-git-decides-when-a-commit-happens.md`):
        # the plugin registers no `PreToolUse` hook, only the nudge that
        # says when that git hook is missing.
        manifest = _load(".claude-plugin/plugin.json")
        hooks = _load(manifest["hooks"])["hooks"]
        self.assertEqual(set(hooks), {"SessionStart", "CwdChanged"})
        for event, groups in hooks.items():
            with self.subTest(event=event):
                [group] = groups
                [handler] = group["hooks"]
                self.assertEqual(handler["type"], "command")
                self.assertIn("claims.nudge", handler["command"])
                self.assertIn("CLAUDE_PLUGIN_ROOT", handler["command"])

    def test_claude_plugin_validate_passes_against_the_real_manifests(self) -> None:
        # Structural checks above can't catch what `claude plugin validate`
        # itself rejects (ticket 19: `agents` pointing at a directory passed
        # every assertion here but failed live). No `--strict`: an
        # `author`-missing warning is acceptable, only errors should fail
        # this test.
        claude = shutil.which("claude")
        if claude is None:
            self.skipTest("claude CLI not found on PATH")
        try:
            result = subprocess.run(
                [claude, "plugin", "validate", "."],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            self.fail("claude plugin validate . timed out after 30s")
        self.assertEqual(
            result.returncode,
            0,
            f"claude plugin validate . failed:\n{result.stdout}\n{result.stderr}",
        )

    def test_marketplace_json_lists_this_plugin_by_the_same_name(self) -> None:
        plugin = _load(".claude-plugin/plugin.json")
        marketplace = _load(".claude-plugin/marketplace.json")
        listed = marketplace["plugins"][0]
        self.assertEqual(listed["name"], plugin["name"])
        self.assertEqual(listed["source"], "./")

    def test_pyproject_version_matches_the_plugin_version(self) -> None:
        # One release, two version strings (AGENTS.md, "Versioning").
        with (REPO_ROOT / "pyproject.toml").open("rb") as f:
            pyproject = tomllib.load(f)
        plugin = _load(".claude-plugin/plugin.json")
        self.assertEqual(pyproject["project"]["version"], plugin["version"])


if __name__ == "__main__":
    unittest.main()
