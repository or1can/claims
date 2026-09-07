"""The `executable-claims` check.

A `<!-- verify: cmd -->` marker directly above a fenced block runs `cmd`
through the shell and diffs its combined stdout+stderr, and its exit code,
against the block. Registered as a **gate** check — see spec.md's check
inventory.

The command runs through a shell rather than `shlex.split`, so a marker
needing a pipe works; that also means it runs exactly what it says, with the
same trust boundary as running the repo's own tests.

Not diff-scoped: every tracked `*.md` file is swept, matching the check's
job of catching a claim that's false right now, not just one a diff just
introduced.
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from ..runner import Finding, register_check

NAME = "executable-claims"
TIMEOUT_SECONDS = 30

MARKER_RE = re.compile(r"^\s*<!--\s*verify:\s*(.+?)\s*-->\s*$")
FENCE_RE = re.compile(r"^\s*```")
PROMPT_RE = re.compile(r"^\s*\$ ")


def _blocks(lines: Sequence[str]):
    """Yields `(line_no, command, expected_lines)` for every marker in `lines`.

    `expected_lines` is `None` when the marker isn't followed (allowing
    blank lines) by a fenced block — a malformed marker.
    """

    for i, line in enumerate(lines):
        marker = MARKER_RE.match(line)
        if not marker:
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        if j >= len(lines) or not FENCE_RE.match(lines[j]):
            yield i + 1, marker.group(1), None
            continue
        end = j + 1
        while end < len(lines) and not FENCE_RE.match(lines[end]):
            end += 1
        yield i + 1, marker.group(1), lines[j + 1 : end]


def _dedent(lines: Sequence[str]) -> list[str]:
    body = [line for line in lines if line.strip()]
    common = min((len(l) - len(l.lstrip()) for l in body), default=0)
    return [line[common:] if line.strip() else line for line in lines]


def _trim(lines: Sequence[str]) -> str:
    return "\n".join(line.rstrip() for line in lines).strip("\n")


def _finding(file: str, line: int, message: str) -> Finding:
    return Finding(file=file, line=line, message=message, mode=NAME, gate=True)


def check(
    repo_root: Path, diff_range: str, config: Mapping[str, object]
) -> list[Finding]:
    findings: list[Finding] = []
    checked = 0
    # A repo's CLAUDE.md is conventionally a symlink to AGENTS.md (both
    # tracked), so without this a marker in one would be swept, and any
    # failure reported, twice.
    seen: set[Path] = set()

    tracked = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "*.md"],
        capture_output=True,
        text=True,
    ).stdout.split()

    for rel in tracked:
        real = (repo_root / rel).resolve()
        if real in seen:
            continue
        seen.add(real)
        lines = (repo_root / rel).read_text(encoding="utf-8").splitlines()
        for line_no, command, expected in _blocks(lines):
            if expected is None:
                findings.append(
                    _finding(rel, line_no, "verify marker is not above a fenced block")
                )
                continue
            checked += 1
            try:
                done = subprocess.run(
                    command,
                    shell=True,
                    cwd=repo_root,
                    capture_output=True,
                    text=True,
                    timeout=TIMEOUT_SECONDS,
                )
            except subprocess.TimeoutExpired:
                findings.append(
                    _finding(
                        rel, line_no, f"`{command}` timed out after {TIMEOUT_SECONDS}s"
                    )
                )
                continue
            if done.returncode != 0:
                findings.append(
                    _finding(rel, line_no, f"`{command}` exited {done.returncode}")
                )
                continue
            # Kept apart: concatenated, a stdout not ending in a newline
            # would weld its last line onto stderr's first and report the
            # seam as drift.
            actual = _trim(done.stdout.splitlines() + done.stderr.splitlines())
            want = _trim([l for l in _dedent(expected) if not PROMPT_RE.match(l)])
            if actual != want:
                findings.append(
                    _finding(
                        rel,
                        line_no,
                        f"output of `{command}` no longer matches the documented block",
                    )
                )

    if checked == 0 and not findings:
        findings.append(_finding(".", 0, "no verify markers found in repo"))

    return findings


register_check(NAME, check)
