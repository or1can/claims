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

import importlib
import os
import pkgutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import claims.checks as checks_package
from claims import runner


def every_check_name() -> set[str]:
    """Every check's own `NAME`, discovered by walking `claims/checks/`'s
    actual module files rather than a second hand-maintained import list —
    a check module added to the package but never wired into the
    package's own imports would otherwise leave a completeness test
    checking against itself, unable to fail for the case it exists to
    catch. `NAME` is what each module passes to `register_check`, so this
    is the registry's own key set, read without depending on the global
    registry's state (which `RegistryClearingTestCase` empties per test).
    """

    names: set[str] = set()
    for module_info in pkgutil.iter_modules(checks_package.__path__):
        module = importlib.import_module(f"{checks_package.__name__}.{module_info.name}")
        names.add(module.NAME)
    return names


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
        # A contributor's own machine-wide `core.excludesFile` (a personal
        # global gitignore) would otherwise silently shadow this throwaway
        # repo too — `git add -A` staging a different set of files here
        # than on a machine with no such global config, or than CI, purely
        # by coincidence of filename (discovered via ticket #33's own
        # `.claude/settings.local.json` fixture, which one contributor's
        # own global gitignore happens to also name).
        subprocess.run(
            ["git", "-C", str(self.root), "config", "core.excludesFile", ""], check=True
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
