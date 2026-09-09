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

"""The `stale-claims` check.

Ranks prose sections in tracked Markdown by how much the code they name has
changed since the section was last touched. A churn-ranked candidate list,
not a verdict: a hot file makes an accurate claim look suspicious, and a
claim can rot while its subject sits still. Registered as an **advisory**
check — see spec.md's check inventory — so it never fails the run.

A claim is a Markdown *section* (heading to next heading, or the whole file
if it has none). Its subject is the code it names: an explicit relative path
that exists in the tree, or a backtick-quoted bare name that uniquely
matches a tracked file's stem — a stem shared by more than one file names no
single subject and is dropped rather than guessed at. `CHANGELOG.md` is
excluded: its entries describe a release as it shipped, so their subjects
moving afterwards is expected, not suspicious.

Score is the largest fraction of any subject's commit history that happened
strictly after the section was last touched (via `git blame`), so a claim
predating most of a quiet file's life outranks one predating a sliver of a
busier one.

**Known blind spot, not a silently accepted gap:** a claim and its subject
edited in the same commit score zero for that subject — the commit that
touched both isn't counted as "after" the claim, since it *is* the claim's
last touch. The comparison is by committer timestamp (`git blame`'s
`committer-time`, second resolution), so two genuinely separate commits that
happen to share a timestamp hit the same gap. A same-commit (or
same-timestamp) rewrite of a claim to match a matching code change is
therefore invisible to this check; nothing here catches it, and nothing
here claims to.

Ported from `ratect`'s `stale-claims.py` (Apache-2.0 prior art, same author),
generalised: `PATH_RE` (explicit relative paths) has no per-language
extension pattern, and no per-project directory allowlist gates a bare-name
match — a bare-name match applies uniformly here, at the cost of the noise a
project-specific allowlist would otherwise have filtered. `MODULE_RE` (bare
backtick names) keeps the original's one behaviour worth keeping exactly —
an optional trailing extension is stripped before the stem lookup, so
`` `docker.rs` `` and `` `docker` `` name the same subject — generalised past
`.rs` to any extension, so this stays useful outside a Rust-only repo.

Not diff-scoped, matching the check inventory: every tracked `*.md` file is
swept, not just one a diff touched.
"""

from __future__ import annotations

import bisect
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

from ..git import tracked_files
from ..runner import Finding, register_check

NAME = "stale-claims"


class _Candidate(NamedTuple):
    score: float
    file: str
    line: int
    message: str

PATH_RE = re.compile(r"\b(?:[\w.-]+/)+[\w.-]+\.[A-Za-z0-9]+\b")
MODULE_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_-]*)(?:\.[A-Za-z0-9]+)?`")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")


def _git(repo_root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        text=True,
        errors="replace",
    ).stdout


def _module_index(tracked: list[str]) -> dict[str, str]:
    """Maps a file stem to its path, dropping any stem shared by >1 file."""

    stems: dict[str, list[str]] = {}
    for rel in tracked:
        stems.setdefault(Path(rel).stem, []).append(rel)
    return {stem: files[0] for stem, files in stems.items() if len(files) == 1}


def check(
    repo_root: Path, diff_range: str, config: Mapping[str, object]
) -> list[Finding]:
    tracked = tracked_files(repo_root)
    tracked_set = set(tracked)
    modules = _module_index(tracked)
    docs = sorted(
        rel
        for rel in tracked
        if rel.endswith(".md") and Path(rel).name.lower() != "changelog.md"
    )

    history: dict[str, list[int]] = {}

    def commits(path: str) -> list[int]:
        if path not in history:
            history[path] = sorted(
                int(t) for t in _git(repo_root, "log", "--format=%ct", "--", path).split()
            )
        return history[path]

    ranked: list[_Candidate] = []
    for rel in docs:
        lines = (repo_root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        if not lines:
            continue
        starts = [i for i, l in enumerate(lines) if HEADING_RE.match(l)] or [0]
        for start, end in zip(starts, starts[1:] + [len(lines)]):
            matched = HEADING_RE.match(lines[start])
            body = "\n".join(lines[start:end])
            subjects = {m for m in PATH_RE.findall(body) if m in tracked_set}
            subjects |= {modules[m] for m in MODULE_RE.findall(body) if m in modules}
            if not subjects:
                continue

            blame = _git(
                repo_root, "blame", "-L", f"{start + 1},{end}", "--line-porcelain", "--", rel
            )
            stamps = [
                int(l.split()[1])
                for l in blame.splitlines()
                if l.startswith("committer-time ")
            ]
            if not stamps:
                continue
            touched = max(stamps)

            moved: dict[str, tuple[int, float]] = {}
            for subject in sorted(subjects):
                times = commits(subject)
                if not times:
                    continue
                # Strictly-after: a commit that also touched the claim (same
                # timestamp) is the claim's own last touch, not drift since
                # it — this is the same-commit-move blind spot documented
                # above, not an oversight here.
                since = len(times) - bisect.bisect_right(times, touched)
                if since:
                    moved[subject] = (since, since / len(times))
            if not moved:
                continue

            score = max(fraction for _, fraction in moved.values())
            label = matched.group(2).strip() if matched else rel
            detail = ", ".join(
                f"{Path(p).name} {n} commit{'s' if n != 1 else ''} ({f:.0%} of its history)"
                for p, (n, f) in sorted(moved.items(), key=lambda kv: -kv[1][1])[:3]
            )
            message = f"'{label}' names code {score:.0%} changed since last touched — {detail}"
            ranked.append(_Candidate(score, rel, start + 1, message))

    ranked.sort(key=lambda candidate: candidate.score, reverse=True)
    return [
        Finding(file=c.file, line=c.line, message=c.message, mode=NAME, gate=False)
        for c in ranked
    ]


register_check(NAME, check)
