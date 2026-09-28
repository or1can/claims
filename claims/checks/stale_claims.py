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

"""The `stale-claims` check: prose sections ranked by how much the code they
name has changed since the section was last touched.
`docs/checks/stale-claims.md` is the account of sections, subjects, the
score, which keys it takes and the same-commit blind spot; this docstring
is why the code is shaped the way it is.

Advisory (spec.md's check inventory): a churn-ranked candidate list, not
a verdict — a hot file makes an accurate claim look suspicious, and a
claim can rot while its subject sits still.

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
extension pattern, and no hardcoded per-project directory allowlist gates a
bare-name match. `MODULE_RE` (bare backtick names) keeps the original's one
behaviour worth keeping exactly — an optional trailing extension is stripped
before the stem lookup, so `` `docker.rs` `` and `` `docker` `` name the same
subject — generalised past `.rs` to any extension, so this stays useful
outside a Rust-only repo. A stem shared by more than one file names no
single subject and is dropped rather than guessed at. A written extension
must then equal the indexed file's own suffix (#102): the original only ever
saw `.rs`, but here `` `hook.json` `` with only `hook.py` tracked used to
resolve to that file, the extension serving as nothing more than the flag
that lets a qualified name bypass `module_reference_scope`. A name with the
wrong extension now names nothing, since the author meant a file of another
type, and a bare name still resolves by stem alone. The comparison is
case-sensitive, as `path_matches` is, because tracked paths are.

`PATH_RE` and its helpers come from `claims.paths` (#87, #108) so that
both checks agree on which prose paths are repo-relative. This check had
its own copy of the pattern, anchored with a leading `\b`, which never
matched before a leading `.`: a cited `.github/workflows/ci.yml` was read
as `github/workflows/ci.yml` and never resolved, and a `~/` or `/` path
lost that prefix and was read as repo-relative. As in `check-file-refs`,
a path is tried from the repository root and then from the citing file's
directory. The one difference: a `../` path, which that check skips, is
tried here from the citing file's directory alone — a rule this check
states in its own loop, since `claims.paths` makes no `../` decision.
The old `\b` skipped the `../`, which let ADR links from `docs/` resolve
by accident, and dropping `../` outright would lose those subjects. A
missed subject is invisible, where a wrong one only fails to resolve.

A *bare* citation (`` `cache` ``, no extension) is ambiguous in a way the
qualified and path forms are not — it's also ordinary English or a
config-field name as often as it's a module — so `module_reference_scope`
lets a project say where module names are actually discussed; key absent
means the pre-key default, a bare citation counting everywhere.
`CHANGELOG.md` is excluded built-in because its entries describe a
release as it shipped, so their subjects moving afterwards is expected,
not suspicious; `exclude` (ticket #43) is the same idea under a project's
own control, not a substitute for it. An excluded file is also left out of
the stem index (#92): a bare name is a guess at a subject, and a file the
project has excluded is the one it least means, so a stem it shares with
one other file resolves to that other file. An explicit path is not a
guess, so it still reaches an excluded file. The built-in `CHANGELOG.md`
exclusion stays out of this — a bare `` `CHANGELOG` `` names that file as
much as it ever did.

The root `claims.toml` is left out of the stem index built-in (#100), the
reverse case: every project running this check has one, and a bare
`` `claims` `` names the tool, never its config file. Dropping it also
drops `` `claims.toml` ``, since a root-level file has no directory to
give an explicit-path match; a section about the config format is not
made stale by a project tuning its own config, which is all that file's
history records.

A `page.md#anchor` subject is scored against that section's history
alone (#110): whole-file history made every page linking one heading of
a busy page look stale. The anchor is read as whatever follows the
`PATH_RE` match, so the link and bare-prose forms agree, and is resolved
by `claims.markdown`'s slug rule, the one `check-links` gates anchors
with, so the two agree on which heading it names. One difference: a
heading-shaped line inside a fence is no heading here, since a shell
`# comment` would otherwise end a section early, so an anchor only such
a line matches falls back to the whole file.
History is `git log -L` over the section's numeric line range at HEAD,
not a `/regex/`, which a heading's own metacharacters would break. An
anchor naming no heading falls back to the whole file, since
`check-links` already reports it. The accepted cost is recall: an edit
just outside the section goes uncounted; the page states it beside the
same-commit blind spot.
"""

from __future__ import annotations

import bisect
import re
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import NamedTuple

from ..config import CONFIG_FILENAME, exclude_patterns, path_matches, string_list_config
from ..git import blob_text, tracked_files
from ..markdown import section_range
from ..paths import PATH_RE, citing_relative, host_relative, repo_relative
from ..runner import Finding, register_check

NAME = "stale-claims"


class _Candidate(NamedTuple):
    score: float
    file: str
    line: int
    message: str

MODULE_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_-]*)(\.[A-Za-z0-9]+)?`")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")
ANCHOR_RE = re.compile(r"#([\w-]+)")


def _in_module_scope(rel: str, config: Mapping[str, object]) -> bool:
    """Whether a *bare* backtick citation in `rel` counts as a module
    reference — always true when `module_reference_scope` is unset (this
    check's default), else true only when `rel` matches one of its globs.
    """

    return "module_reference_scope" not in config or path_matches(
        rel, string_list_config(config, "module_reference_scope")
    )


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
    exclude = exclude_patterns(config)
    modules = _module_index(
        [
            rel
            for rel in tracked
            if rel != CONFIG_FILENAME and not path_matches(rel, exclude)
        ]
    )
    docs = sorted(
        rel
        for rel in tracked
        if rel.endswith(".md")
        and Path(rel).name.lower() != "changelog.md"
        and not path_matches(rel, exclude)
    )

    sections: dict[tuple[str, str], tuple[int, int] | None] = {}

    def section(path: str, anchor: str) -> tuple[int, int] | None:
        # Read at HEAD, not from the working tree: `git log -L` resolves
        # the range against HEAD, and the commit hook runs while the linked
        # page itself may carry uncommitted edits that shift its lines.
        if (path, anchor) not in sections:
            text = blob_text(repo_root, "HEAD", path)
            sections[path, anchor] = None if text is None else section_range(text, anchor)
        return sections[path, anchor]

    history: dict[tuple[str, str], list[int]] = {}

    def commits(path: str, anchor: str) -> list[int]:
        if (path, anchor) not in history:
            span = section(path, anchor) if anchor else None
            scope = ("-s", "-L", f"{span[0]},{span[1]}:{path}") if span else ("--", path)
            history[path, anchor] = sorted(
                int(t) for t in _git(repo_root, "log", "--format=%ct", *scope).split()
            )
        return history[path, anchor]

    ranked: list[_Candidate] = []
    for rel in docs:
        lines = (repo_root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        if not lines:
            continue
        bare_in_scope = _in_module_scope(rel, config)
        starts = [i for i, l in enumerate(lines) if HEADING_RE.match(l)] or [0]
        for start, end in zip(starts, starts[1:] + [len(lines)]):
            matched = HEADING_RE.match(lines[start])
            body = "\n".join(lines[start:end])
            # (path, anchor): anchor is "" unless it names a heading in a
            # tracked `.md` path, so an unscoped subject is one key per file.
            subjects: set[tuple[str, str]] = set()
            for match in PATH_RE.finditer(body):
                if host_relative(body, match.start()):
                    continue
                raw = match.group(0)
                paths = (citing_relative(rel, raw),)
                if not raw.startswith("../"):
                    paths = (repo_relative(raw),) + paths
                anchored = ANCHOR_RE.match(body, match.end())
                anchor = anchored.group(1) if anchored else ""
                subjects |= {
                    (path, anchor if anchor and path.endswith(".md") and section(path, anchor) else "")
                    for path in paths
                    if path in tracked_set
                }
            subjects |= {
                (modules[name], "")
                for name, ext in MODULE_RE.findall(body)
                if name in modules
                and (Path(modules[name]).suffix == ext if ext else bare_in_scope)
            }
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

            moved: dict[tuple[str, str], tuple[int, float]] = {}
            for subject in sorted(subjects):
                times = commits(*subject)
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
                f"{Path(p).name}{'#' + a if a else ''} {n} commit{'s' if n != 1 else ''} ({f:.0%} of its history)"
                for (p, a), (n, f) in sorted(moved.items(), key=lambda kv: -kv[1][1])[:3]
            )
            message = f"'{label}' names code {score:.0%} changed since last touched — {detail}"
            ranked.append(_Candidate(score, rel, start + 1, message))

    ranked.sort(key=lambda candidate: candidate.score, reverse=True)
    return [
        Finding(file=c.file, line=c.line, message=c.message, mode=NAME, gate=False)
        for c in ranked
    ]


register_check(NAME, check)
