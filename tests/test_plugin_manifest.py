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

    def test_agent_directory_has_an_agent_file_with_required_frontmatter(self) -> None:
        manifest = _load(".claude-plugin/plugin.json")
        for agent_dir in manifest["agents"]:
            agent_files = list((REPO_ROOT / agent_dir).glob("*.md"))
            self.assertTrue(agent_files, f"no agent files under {agent_dir}")
            for agent_file in agent_files:
                text = agent_file.read_text(encoding="utf-8")
                self.assertIn("name:", text)
                self.assertIn("description:", text)

    def test_hooks_file_gates_pretooluse_on_git_commit_only(self) -> None:
        manifest = _load(".claude-plugin/plugin.json")
        hooks_file = _load(manifest["hooks"])
        pre_tool_use = hooks_file["hooks"]["PreToolUse"][0]
        self.assertEqual(pre_tool_use["matcher"], "Bash")
        handler = pre_tool_use["hooks"][0]
        self.assertEqual(handler["if"], "Bash(git commit *)")
        self.assertIn("claims.hook", handler["command"])
        self.assertIn("CLAUDE_PLUGIN_ROOT", handler["command"])

    def test_marketplace_json_lists_this_plugin_by_the_same_name(self) -> None:
        plugin = _load(".claude-plugin/plugin.json")
        marketplace = _load(".claude-plugin/marketplace.json")
        listed = marketplace["plugins"][0]
        self.assertEqual(listed["name"], plugin["name"])
        self.assertEqual(listed["source"], "./")


if __name__ == "__main__":
    unittest.main()
