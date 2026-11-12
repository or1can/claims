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

"""Builds the tutorial's practice repository, and captures the tutorial.

`docs/tutorial.md` has a reader build a small fictional project, Acme,
inside their clone of this repository and then type each step themselves
against the real hooks. Two subcommands, each a function the test calls
too:

- `setup` deletes and rebuilds `.tutorial/acme`: `git init -b main`, a
  repo-local `commit.gpgsign=false`, the starting fixture from
  `examples/tutorial/start/` committed as one commit and pushed to a bare
  remote at `../remote.git`, the untracked grant from
  `examples/tutorial/local/` copied in, and last a repo-local
  `core.hooksPath` naming `examples/tutorial/hooks/` by absolute path. The
  initial push comes before the hooks, so during every later pre-push
  `origin/main` still names the remote's old tip. Those two settings,
  plus the `origin` remote and `main`'s upstream, are the only git
  configuration it writes, all of it in Acme's own; it forces no identity
  or dates on a reader's machine, and the initial commit and push pass `--no-verify`
  so a hook in the reader's own global configuration doesn't run either.
  Its only output is one line naming `.tutorial/acme`.

- `capture` runs every step of `examples/tutorial/steps.sh` against an
  Acme of its own, in a temporary directory under `.tutorial/`, so a
  reader's `.tutorial/acme` is never touched, and writes one file per
  step to `docs/captures/tutorial/<step>.txt`. The `setup` step runs from
  the clone's root, with `CLAIMS_TUTORIAL_ACME` pointing it at the
  temporary Acme, and every later step from that Acme. Before a step's
  commands, its `examples/tutorial/states/<step>/` is copied over the
  repository when there is one: the edit a reader makes by hand. Each line
  of `steps.sh` that is not a comment runs on its own with `sh -c`, and
  is recorded as `$ <command>`, then its output, then `[exit N]` only
  when N is not 0. The temporary Acme's path is written as
  `.tutorial/acme` wherever it appears, which is setup's own line, so the
  capture shows what a reader's run prints.

For byte-stability, every command runs with git's global and system
configuration switched off (`GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM`),
a fixed author and committer identity and date, and `PYTHONUNBUFFERED=1`.

Stdout and stderr are merged into one pipe, as a reader's terminal shows
them, rather than captured apart, and the order holds for three reasons,
argued here and not tested. git runs every hook with the hook's stdout
redirected to its stderr, so a hook's output is a single stream already.
git prints its own lines only after the hook it ran has exited, so the
two never interleave. And the one thing that could reorder a single
process's two streams is Python's buffering, block-buffered on a pipe
where a terminal would be line-buffered, which `PYTHONUNBUFFERED=1`
removes.

Run by hand, from the clone, to rewrite the captures after an intended
change to the fixture or to `claims`' output:
`uv run -q scripts/tutorial.py capture`.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = REPO_ROOT / "examples" / "tutorial"
STEPS = EXAMPLE / "steps.sh"
WORKSPACE = REPO_ROOT / ".tutorial"
ACME = WORKSPACE / "acme"
CAPTURES_DIR = REPO_ROOT / "docs" / "captures" / "tutorial"

# Where `setup` builds Acme instead of `.tutorial/acme`. Set by `capture`
# alone, so the `setup` line it runs from `steps.sh` builds the capture's
# own Acme and leaves a reader's alone.
ACME_ENV = "CLAIMS_TUTORIAL_ACME"

# The same fixed epoch `scripts/capture.py` commits at.
COMMIT_TIME = "1700000000 +0000"


def setup(acme: Path) -> None:
    """Deletes `acme` and its bare remote beside it, and rebuilds both."""

    remote = acme.parent / "remote.git"
    for path in (acme, remote):
        shutil.rmtree(path, ignore_errors=True)
    acme.parent.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", "--bare", "-b", "main", str(remote))
    _git("init", "-q", "-b", "main", str(acme))
    _git("-C", str(acme), "config", "commit.gpgsign", "false")
    _copy("start", acme)
    _git("-C", str(acme), "add", "-A")
    _git("-C", str(acme), "commit", "-q", "--no-verify", "-m", "Start Acme")
    _git("-C", str(acme), "remote", "add", "origin", "../remote.git")
    _git("-C", str(acme), "push", "-q", "--no-verify", "-u", "origin", "main")
    # After the commit, so the grant is never staged: a `claims.local.toml`
    # git tracks has its grants ignored.
    _copy("local", acme)
    _git("-C", str(acme), "config", "core.hooksPath", str(EXAMPLE / "hooks"))


def capture() -> dict[str, str]:
    """Each step's transcript, by anchor, in `steps.sh` order."""

    WORKSPACE.mkdir(exist_ok=True)
    transcripts: dict[str, str] = {}
    with tempfile.TemporaryDirectory(dir=WORKSPACE) as temp:
        acme = Path(temp) / "acme"
        temp_acme = str(acme.relative_to(REPO_ROOT))
        env = _isolated_env(acme)
        for step, commands in steps():
            if (EXAMPLE / "states" / step).is_dir():
                _copy(f"states/{step}", acme)
            entries: list[str] = []
            for command in commands:
                ran = subprocess.run(
                    ["sh", "-c", command],
                    cwd=REPO_ROOT if step == "setup" else acme,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
                output = ran.stdout.replace(temp_acme, str(ACME.relative_to(REPO_ROOT)))
                if output and not output.endswith("\n"):
                    output += "\n"
                exit_line = f"[exit {ran.returncode}]\n" if ran.returncode else ""
                entries.append(f"$ {command}\n{output}{exit_line}")
            transcripts[step] = "\n".join(entries)
    return transcripts


def steps() -> list[tuple[str, list[str]]]:
    """`steps.sh`'s commands, grouped by the anchor each sits inside."""

    grouped: list[tuple[str, list[str]]] = []
    current: list[str] | None = None
    for number, line in enumerate(STEPS.read_text(encoding="utf-8").splitlines(), 1):
        if line.startswith("# ANCHOR: "):
            current = []
            grouped.append((line.removeprefix("# ANCHOR: "), current))
        elif line.startswith("# ANCHOR_END: "):
            current = None
        elif line.strip() and not line.startswith("#"):
            if current is None:
                raise SystemExit(f"{STEPS}:{number}: a command outside any anchor")
            current.append(line)
    return grouped


def _isolated_env(acme: Path) -> dict[str, str]:
    # Whatever `GIT_*` the caller runs under (`GIT_DIR` and `GIT_INDEX_FILE`
    # when it is itself a hook) would point every command at the wrong
    # repository, so none is inherited.
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="Reader",
        GIT_AUTHOR_EMAIL="reader@example.com",
        GIT_AUTHOR_DATE=COMMIT_TIME,
        GIT_COMMITTER_NAME="Reader",
        GIT_COMMITTER_EMAIL="reader@example.com",
        GIT_COMMITTER_DATE=COMMIT_TIME,
        PYTHONUNBUFFERED="1",
    )
    env[ACME_ENV] = str(acme)
    return env


def _copy(part: str, acme: Path) -> None:
    """Copies what git tracks under `examples/tutorial/<part>/` over `acme`,
    keeping each file's executable bit.

    Only what git tracks, as `scripts/capture.py` seeds its examples, so a
    stray editor or Finder file in the clone is never copied in."""

    prefix = f"examples/tutorial/{part}/"
    for rel in _git("-C", str(REPO_ROOT), "ls-files", "-z", prefix).split("\0"):
        if not rel:
            continue
        target = acme / rel.removeprefix(prefix)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / rel, target)


def _git(*args: str) -> str:
    ran = subprocess.run(["git", *args], capture_output=True, text=True)
    if ran.returncode:
        raise SystemExit(f"git {' '.join(args)} failed:\n{ran.stderr}")
    return ran.stdout


def main() -> int:
    parser = argparse.ArgumentParser(prog="scripts/tutorial.py")
    command = parser.add_subparsers(dest="command", required=True)
    command.add_parser("setup", help="Delete and rebuild .tutorial/acme.")
    command.add_parser("capture", help="Rewrite docs/captures/tutorial/.")
    args = parser.parse_args()
    if args.command == "setup":
        acme = Path(os.environ.get(ACME_ENV, ACME))
        setup(acme)
        print(f"Acme is ready: cd {acme.relative_to(REPO_ROOT)}")
        return 0
    CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
    for step, text in capture().items():
        target = CAPTURES_DIR / f"{step}.txt"
        target.write_text(text, encoding="utf-8")
        print(f"wrote {target.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
