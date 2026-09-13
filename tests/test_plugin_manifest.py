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

    def test_hooks_file_registers_a_bash_matched_pretooluse_hook(self) -> None:
        # Narrowing to a git commit specifically is split across two
        # layers (ticket 37): `if` here does the coarse "some git command
        # at all" filter using Claude Code's own Bash-command matching —
        # deliberately the bare command name (`git *`), not `git commit
        # *`, since Claude Code's own documented matching runs the hook
        # anyway on any command containing a `$()`/backtick/`$var` once
        # the pattern names more than the bare command name (see
        # code.claude.com/docs/en/hooks, "Bash if matching"), which
        # defeats a commit-specific pattern for exactly the agent-
        # authored commands (heredocs, command substitutions) this hook
        # most needs to filter correctly. `claims.hook`'s own
        # `_is_git_commit` (see tests/test_hook.py) does the fine-grained
        # "is it specifically a commit" narrowing in Python instead.
        manifest = _load(".claude-plugin/plugin.json")
        hooks_file = _load(manifest["hooks"])
        pre_tool_use = hooks_file["hooks"]["PreToolUse"][0]
        self.assertEqual(pre_tool_use["matcher"], "Bash")
        handler = pre_tool_use["hooks"][0]
        self.assertEqual(handler["if"], "Bash(git *)")
        self.assertIn("claims.hook", handler["command"])
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


if __name__ == "__main__":
    unittest.main()
