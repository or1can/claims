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

"""Shared test scaffolding."""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from claims import runner


class RegistryClearingTestCase(unittest.TestCase):
    """Base for tests that register checks: keeps the global registry isolated per test."""

    def setUp(self) -> None:
        runner.clear_registry()
        self.addCleanup(runner.clear_registry)


class Repo:
    """A throwaway git repository for check fixtures.

    `write` stages a file without committing — enough for a check that reads
    the working tree via `git ls-files`. `commit` actually commits, with an
    optional fixed timestamp for checks that rank by commit history.
    """

    def __enter__(self) -> "Repo":
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(
            ["git", "-C", str(self.root), "config", "user.email", "test@example.com"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.root), "config", "user.name", "Test"], check=True
        )
        return self

    def __exit__(self, *_exc: object) -> None:
        self._temp.cleanup()

    def config(self, key: str, value: str) -> None:
        subprocess.run(["git", "-C", str(self.root), "config", key, value], check=True)

    def write(self, name: str, text: str) -> None:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        subprocess.run(["git", "-C", str(self.root), "add", name], check=True)

    def commit(self, when: int | None = None) -> None:
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True)
        env = None
        if when is not None:
            date = f"{when} +0000"
            env = {**os.environ, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
        subprocess.run(
            ["git", "-C", str(self.root), "commit", "-q", "-m", "commit"],
            check=True,
            env=env,
        )
