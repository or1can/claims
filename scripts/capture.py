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

`capture` builds a throwaway git repository from the example and calls
the named check through the same `(repo_root, diff_range, config) ->
findings` seam every entry point and every check test calls, rendering
each finding the way the CLI prints it. The repository is built the way
the commit hook meets one: whatever the example's `history/` holds is
committed, one step per directory in name order, at fixed timestamps an
hour apart; the example's own files are then written over that and
staged, never committed, so they are the pending change `git commit` is
about to land and the diff range `HEAD` (the hook's own, working tree
against `HEAD`) is exactly that change. A whole-tree check reads the
staged files like any tracked file and needs no history at all; a check
keyed on history (`check-citations` flags a name the repository once
declared and no longer has; `stale-claims` counts the commits a subject
saw after a section's last touch, so its example is history alone) gets
it from the committed steps; a diff-scoped check (`restatement` starts
from a retracted line, `claim-words` reads added ones, `judgment-agent`
computes what the diff touched) reads the staged files as the diff. Every
step of the input is a checked-in file the page can include, rather than
a commit only the script knows about. What an example keeps under
`local/` is written into the working tree last and never staged, with its
executable bit carried over: `executable-claims` runs only a command
granted in a `claims.local.toml` that git does *not* track, so the drift
finding that check exists for cannot be captured from tracked files
alone, and the program a granted marker names is built rather than
committed too.

A check that sees nothing until a project configures it
(`check-config-defaults` verifies only a setting with a mapping entry;
`claim-words` sweeps only designated files) gets that configuration from
the same example too: a `claims.toml` under `examples/<check>/` is staged
with the example's own files and read through the same loader
`runner.run` uses, so the page can include the file that brings its claim
into scope.

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
from claims.git import tracked_files  # noqa: E402
from support import Repo  # noqa: E402

# Fixed rather than wall-clock, so a check that ranks by commit age sees
# the same history on every run and every machine.
COMMIT_TIME = 1_700_000_000


def capture(check: str) -> str:
    """`check`'s findings against `examples/<check>/`, one per line as the
    CLI prints them, headed by a one-line provenance note."""

    module = importlib.import_module(f"claims.checks.{check.replace('-', '_')}")
    example = f"examples/{check}"
    # Only what git tracks, not the directory as it sits on disk — a
    # stray editor or Finder file there would otherwise be committed
    # into the throwaway repository on one machine and not another.
    # (So a new example file is seen once it's `git add`ed.)
    history: dict[str, dict[str, str]] = {}  # step name -> files
    own: dict[str, str] = {}
    local: dict[str, Path] = {}  # name in the repo -> file to copy it from
    for rel in tracked_files(REPO_ROOT, example):
        parts = Path(rel).relative_to(example).parts
        source = REPO_ROOT / rel
        if parts[0] == "history":
            history.setdefault(parts[1], {})[str(Path(*parts[2:]))] = source.read_text(
                encoding="utf-8"
            )
        elif parts[0] == "local":
            local[str(Path(*parts[1:]))] = source
        else:
            own[str(Path(*parts))] = source.read_text(encoding="utf-8")
    with Repo() as repo:
        # `history/` steps in name order, one commit per step, an hour
        # apart, still fixed; then the example's own files, staged and
        # left uncommitted as the change a commit hook would be gating.
        for n, step in enumerate(sorted(history)):
            for name, text in history[step].items():
                repo.write(name, text)
            repo.commit(when=COMMIT_TIME + 3600 * n)
        for name, text in own.items():
            repo.write(name, text)
        # Last, and never staged: a `claims.local.toml` git tracks has its
        # grants ignored outright, so seeding this through `repo.write`
        # would capture that refusal instead of the granted marker's own
        # finding. After the commits above, too, since `repo.commit`
        # stages everything in the tree.
        for name, path in local.items():
            copied = repo.root / name
            copied.parent.mkdir(parents=True, exist_ok=True)
            copied.write_bytes(path.read_bytes())
            # git tracks one mode bit, so that is the one carried over: a
            # marker naming `./widget` needs the program it names to be
            # executable on the machine capturing it.
            copied.chmod(0o755 if path.stat().st_mode & 0o100 else 0o644)
        # The example's own `claims.toml`, if it has one, read exactly as
        # a real run reads a project's — `{}` for the check's section when
        # there is no file, the same as a project with no config at all.
        config = load_config(repo.root).get(check, {})
        findings = module.check(repo.root, "HEAD", config)
    lines = [
        f"# python3 scripts/capture.py: {check}, run against a throwaway git "
        f"repository seeded from {example}"
    ]
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
