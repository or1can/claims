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

"""Captures the real output of a check against its worked example.

Each check page under `docs/` shows a deliberately-broken input beside the
findings `claims` produces against it. The input is checked in under
`examples/<check>/`; the output is not typed or edited but captured here,
into `docs/captures/<check>.txt`, and `tests/test_captures.py` calls the
same `capture` function to assert the committed text still matches a
fresh run. One code path for writing and for verifying, so the two cannot
drift.

`capture` builds a throwaway git repository from the example, commits it
at a fixed timestamp, and calls the named check through the same
`(repo_root, diff_range, config) -> findings` seam every entry point and
every check test calls, rendering each finding the way the CLI prints it.
One check, not the whole CLI run: every other check sweeps the same tiny
repository too, and at least one of them always has something to say about
it (`executable-claims` gates a repository with no verify markers at all),
which on a page about a different check is noise a reader has to be told
to ignore. Findings render repo-relative paths, so no temporary directory
reaches the capture.

Run by hand to rewrite every capture after a check's output changes:
`python3 scripts/capture.py`. Not collected by `unittest discover` (it
lives under `scripts/`, not `tests/`, and isn't named `test_*.py`).
"""

from __future__ import annotations

import importlib
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
CAPTURES_DIR = REPO_ROOT / "docs" / "captures"

# Run as a script, neither the repo root nor `tests/` is on `sys.path` yet.
# `tests/support.py` is the throwaway-repository helper the check tests
# already use, with the same git isolation (fixed identity, no machine-wide
# excludes file) — so a capture built here matches one built anywhere.
sys.path[:0] = [str(REPO_ROOT), str(REPO_ROOT / "tests")]
from claims.config import load_config  # noqa: E402
from support import Repo  # noqa: E402

# Fixed rather than wall-clock, so a check that ranks by commit age sees
# the same history on every run and every machine.
COMMIT_TIME = 1_700_000_000


def capture(check: str) -> str:
    """`check`'s findings against `examples/<check>/`, one per line as the
    CLI prints them, headed by a one-line provenance note."""

    module = importlib.import_module(f"claims.checks.{check.replace('-', '_')}")
    with Repo() as repo:
        shutil.copytree(EXAMPLES_DIR / check, repo.root, dirs_exist_ok=True)
        repo.commit(when=COMMIT_TIME)
        # The example's own `claims.toml`, where it has one, is the check's
        # configuration — the same section `runner.run` would hand it.
        config = load_config(repo.root).get(check, {})
        findings = module.check(repo.root, "HEAD", config)
    lines = [f"# {check}, run against a throwaway git repository seeded from examples/{check}"]
    lines.extend(str(finding) for finding in findings)
    return "\n".join(lines) + "\n"


def main() -> int:
    CAPTURES_DIR.mkdir(exist_ok=True)
    for example in sorted(p for p in EXAMPLES_DIR.iterdir() if p.is_dir()):
        target = CAPTURES_DIR / f"{example.name}.txt"
        target.write_text(capture(example.name), encoding="utf-8")
        print(f"wrote {target.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
