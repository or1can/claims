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

Diff-scoped (ADR 0009): a section is ranked only when the range changed
one of its subjects, so the hook stops printing the same whole-tree
ranking on every commit. The paths come from `changed_paths`, not
`iter_diff`, which has no path to give for a pure rename; the score
still reads each subject's whole history, so a section scores the same
whichever range brings it in. An explicit path the range deleted or
renamed away still names a subject, though no longer tracked: a section
citing a file that just went is the one most worth reading.

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

Excluding `CHANGELOG.md` as a place claims are made leaves it as a
subject, and as one it grows on almost every commit. An append-only file
(ADR 0011, `config.append_only`) drops each commit whose diff for it
removes no lines from its history, read from `git log --numstat` of the
whole file: a section-scoped subject is filtered on that too, rather than
on `git log -L`'s patch for the section, which would need its own hunk
parser. A commit removing lines elsewhere in the file still counts for
the section, which misses less. `[subjects]` is project-wide, so it is
read from `claims.toml` here rather than from this check's own section.

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
from collections.abc import Callable, Collection, Mapping
from pathlib import Path
from typing import NamedTuple

from ..config import (
    CONFIG_FILENAME,
    append_only,
    exclude_patterns,
    load_config,
    path_matches,
    string_list_config,
)
from ..git import blob_text, changed_paths, tracked_files
from ..lines import git_lines, tracked_text
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


def _appends(repo_root: Path, path: str) -> set[str]:
    """The commits whose diff for `path` removes no lines: an append-only
    file's growth, which ADR 0011 doesn't count as its content changing.
    A commit with no line counts, a binary one, is no append. A merge is
    read against its first parent, as what it brought to the branch it
    landed on: `git log` gives a merge no line counts otherwise."""

    log = ("log", "--format=%x00%H", "--numstat", "--diff-merges=first-parent", "--", path)
    appends: set[str] = set()
    for block in _git(repo_root, *log).split("\0")[1:]:
        commit, *stats = [line for line in block.split("\n") if line]
        if stats and all(stat.split("\t")[1] == "0" for stat in stats):
            appends.add(commit)
    return appends


def _module_index(tracked: list[str]) -> dict[str, str]:
    """Maps a file stem to its path, dropping any stem shared by >1 file."""

    stems: dict[str, list[str]] = {}
    for rel in tracked:
        stems.setdefault(Path(rel).stem, []).append(rel)
    return {stem: files[0] for stem, files in stems.items() if len(files) == 1}


def module_index(tracked: list[str], config: Mapping[str, object]) -> dict[str, str]:
    """The stems a bare backtick name can resolve to: `tracked` less the
    root `claims.toml` and whatever `exclude` names."""

    exclude = exclude_patterns(config)
    return _module_index(
        [rel for rel in tracked if rel != CONFIG_FILENAME and not path_matches(rel, exclude)]
    )


def subjects_named(
    rel: str,
    body: str,
    config: Mapping[str, object],
    citable: Collection[str],
    modules: Mapping[str, str],
    section: Callable[[str, str], object],
) -> set[tuple[str, str]]:
    """Every `(path, anchor)` subject `body`, prose in `rel`, names.
    `anchor` is "" unless it names a heading `section(path, anchor)`
    finds in a `.md` path, so an unscoped subject is one key per file.
    Checked marks resolve a unit's subjects through this too (ADR 0010),
    so the two can't disagree about what a sentence names."""

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
            if path in citable
        }
    bare_in_scope = _in_module_scope(rel, config)
    subjects |= {
        (modules[name], "")
        for name, ext in MODULE_RE.findall(body)
        if name in modules
        and (Path(modules[name]).suffix == ext if ext else bare_in_scope)
    }
    return subjects


def check(
    repo_root: Path, diff_range: str, config: Mapping[str, object]
) -> list[Finding]:
    changed = changed_paths(repo_root, diff_range)
    if not changed:
        return []
    tracked = tracked_files(repo_root)
    # A path the range deleted or renamed away is no longer tracked, and
    # is still the subject of a section that names it.
    citable = set(tracked) | changed
    exclude = exclude_patterns(config)
    modules = module_index(tracked, config)
    # `[subjects]` belongs to no check, so isn't in this one's `config`.
    project = load_config(repo_root)
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
    appends: dict[str, set[str]] = {}

    def commits(path: str, anchor: str) -> list[int]:
        if (path, anchor) not in history:
            span = section(path, anchor) if anchor else None
            scope = ("-s", "-L", f"{span[0]},{span[1]}:{path}") if span else ("--", path)
            if path not in appends:
                appends[path] = _appends(repo_root, path) if append_only(project, path) else set()
            logged = _git(repo_root, "log", "--format=%H %ct", *scope).split()
            history[path, anchor] = sorted(
                int(t) for h, t in zip(logged[::2], logged[1::2]) if h not in appends[path]
            )
        return history[path, anchor]

    ranked: list[_Candidate] = []
    for rel in docs:
        lines = git_lines(tracked_text(repo_root / rel, errors="replace"))
        if not lines:
            continue
        starts = [i for i, l in enumerate(lines) if HEADING_RE.match(l)] or [0]
        for start, end in zip(starts, starts[1:] + [len(lines)]):
            matched = HEADING_RE.match(lines[start])
            body = "\n".join(lines[start:end])
            subjects = subjects_named(rel, body, config, citable, modules, section)
            if not any(path in changed for path, _ in subjects):
                continue

            blame = _git(
                repo_root, "blame", "-L", f"{start + 1},{end}", "--line-porcelain", "--", rel
            )
            stamps = [
                int(l.split()[1])
                for l in git_lines(blame)
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
