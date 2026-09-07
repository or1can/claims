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

"""The `spliced-docs` check.

Inserting a declaration above an existing one, anchored on that one's `///`
lines, splices the new declaration into its neighbour's documentation.
Nothing catches it mechanically: the compiler/doc-renderer is happy, and the
text ends up rendered under whichever declaration ends up last, leaving the
declaration it was written for bare. Registered as an **advisory** check —
see spec.md's check inventory — so it never fails the run: a break in a doc
run is common (an ordinary second sentence), and only some are splices.

Ported from `ratect`'s `tools/spliced-docs.py` (Rust) and Project B's
`tools/spliced-docs.py` (Swift) — same author, both Apache-2.0/relicensed
prior art for this consolidation — onto the *union* of their evidence
rules (spec.md's "stronger variant" applied to both languages, not just
Swift's): a break is reported when the stranded prose names, in backticks,
either an undocumented declaration in the same file or a name that resolves
to nothing anywhere in the repo (in that language). No adapter interface is
introduced for this — spec.md defers that design; the two languages are
handled by two concrete, independent functions.

How it works, per language:

  run       one contiguous block of `///` lines, plus the attributes and
            declaration beneath it
  break     inside a run, a line ending a sentence followed — with no blank
            `///` between — by a line reading like a fresh summary. Each
            source codebase's own house style (a summary, a blank `///`,
            then detail) is what makes a summary mid-run mean two documents
  evidence  a break alone is far too noisy (an ordinary second sentence
            trips it constantly). What distinguishes a splice is that the
            stranded half names, in backticks, a declaration that is either
            undocumented in the same file or absent from the repo entirely

Not diff-scoped: every tracked `*.rs`/`*.swift` file is swept, matching the
source tools' whole-tree behaviour — a splice can predate the diff being
checked.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

from ..git import tracked_files
from ..runner import Finding, register_check

NAME = "spliced-docs"

MODE_UNDOCUMENTED = "spliced-docs-undocumented"
MODE_UNKNOWN = "spliced-docs-unknown"

DOC_RE = re.compile(r"^\s*///")


def _finding(file: str, line: int, mode: str, names: list[str], where: str) -> Finding:
    quoted = ", ".join(f"`{name}`" for name in names)
    return Finding(
        file=file,
        line=line,
        message=f"stranded doc comment names {quoted}, {where}",
        mode=mode,
        gate=False,
    )


def _emit(
    rel: str,
    line_no: int,
    named: frozenset[str],
    bare: dict[str, set[str]],
    all_names: set[str],
) -> list[Finding]:
    owners = sorted(name for name, idents in bare.items() if named & idents)
    unknown = sorted(name for name in named if name not in all_names)
    findings: list[Finding] = []
    if owners:
        findings.append(
            _finding(rel, line_no, MODE_UNDOCUMENTED, owners, "undocumented in this file")
        )
    if unknown:
        findings.append(
            _finding(rel, line_no, MODE_UNKNOWN, unknown, "resolves to nothing in the repo")
        )
    return findings


# --- Rust -------------------------------------------------------------

RUST_ATTR_RE = re.compile(r"^\s*#\[")
RUST_ITEM_RE = re.compile(
    r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+|unsafe\s+|const\s+)*"
    r"(fn|struct|enum|trait|type|mod|impl)\s+([A-Za-z_][A-Za-z_0-9]*)"
)
RUST_SUMMARY_RE = re.compile(
    r"^\s*/// (?:The|A|An) \S|^\s*/// [A-Z][a-z]+(?:s|es) [`\w]"
)
RUST_PARAM_RE = re.compile(r"^\s*(?:mut\s+)?([a-z_][a-z_0-9]*)\s*:")
RUST_BACKTICKED = re.compile(r"`([A-Za-z_][A-Za-z_0-9]*)`")


def _rust_runs(lines: list[str]):
    """Every `(doc_start, doc_end)` in `lines`, doc lines only."""

    i = 0
    while i < len(lines):
        if not DOC_RE.match(lines[i]):
            i += 1
            continue
        start = i
        while i < len(lines) and DOC_RE.match(lines[i]):
            i += 1
        yield start, i


def _rust_bare_items(lines: list[str]) -> dict[str, set[str]]:
    """Undocumented declarations in `lines`, as `name -> {name, param names}`.

    By *name*, not by position: a trait method is documented once on the
    trait and appears bare on every impl, which is not a stranding.
    """

    documented_at = {end for _, end in _rust_runs(lines)}
    documented_names = set()
    for i, line in enumerate(lines):
        matched = RUST_ITEM_RE.match(line)
        if not matched:
            continue
        attrs = i
        while attrs > 0 and RUST_ATTR_RE.match(lines[attrs - 1]):
            attrs -= 1
        if attrs in documented_at or (attrs > 0 and DOC_RE.match(lines[attrs - 1])):
            documented_names.add(matched.group(2))

    bare: dict[str, set[str]] = {}
    for i, line in enumerate(lines):
        matched = RUST_ITEM_RE.match(line)
        if not matched:
            continue
        name = matched.group(2)
        if name in documented_names:
            continue
        attrs = i
        while attrs > 0 and RUST_ATTR_RE.match(lines[attrs - 1]):
            attrs -= 1
        if attrs in documented_at or (attrs > 0 and DOC_RE.match(lines[attrs - 1])):
            continue
        idents = {name}
        for follow in lines[i : i + 12]:
            param = RUST_PARAM_RE.match(follow)
            if param:
                idents.add(param.group(1))
            if ")" in follow and follow.strip() != "(":
                break
        bare[name] = idents
    return bare


def _rust_all_names(all_lines: list[list[str]]) -> set[str]:
    names = set()
    for lines in all_lines:
        for line in lines:
            matched = RUST_ITEM_RE.match(line)
            if matched:
                names.add(matched.group(2))
    return names


def _rust_breaks(lines: list[str]):
    """Every `(break_line, {backticked names above it})` in `lines`."""

    for start, end in _rust_runs(lines):
        for i in range(start + 1, end):
            previous = lines[i - 1].rstrip()
            if not previous.endswith(".") or not RUST_SUMMARY_RE.match(lines[i]):
                continue
            stranded = " ".join(lines[start:i])
            named = frozenset(RUST_BACKTICKED.findall(stranded))
            if named:
                yield i + 1, named


def _check_rust(repo_root: Path) -> list[Finding]:
    files = {
        rel: (repo_root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        for rel in tracked_files(repo_root, "*.rs")
    }
    all_names = _rust_all_names(list(files.values()))

    findings: list[Finding] = []
    for rel, lines in sorted(files.items()):
        if not lines:
            continue
        bare = _rust_bare_items(lines)
        for line_no, named in _rust_breaks(lines):
            findings.extend(_emit(rel, line_no, named, bare, all_names))
    return findings


# --- Swift --------------------------------------------------------------

SWIFT_ATTR_RE = re.compile(r"^\s*@")
# Ported from Project B's `tools/claims.py::DECL_RE` — the one answer to "what
# is a declaration" shared by that repo's own spliced-docs and check-citations
# tools, kept as one regex there specifically to avoid two answers drifting.
SWIFT_DECL_RE = re.compile(
    r"^\s*(?:(?:public|internal|private|fileprivate|open)(?:\(set\))?\s+)*"
    r"(?:(?:static|class|final|mutating|nonmutating|override|convenience|"
    r"required|lazy|weak|indirect)\s+)*"
    r"(?:func|var|let|struct|class|enum|protocol|actor|typealias|case|init)"
    r"\s+([A-Za-z_][A-Za-z_0-9]*)"
)
SWIFT_SUMMARY_RE = re.compile(
    r"^\s*/// (?:The|A|An|Whether|Why|What|Where|One|Every)\s\S"
    r"|^\s*/// [A-Z][a-z]+(?:s|es)\s[`\w]"
)
SWIFT_SENTENCE_END_RE = re.compile(r"[.!?][)`\"']?\s*$")
# Ported from Project B's `tools/spliced-docs.py::NAME_RE` — deliberately has
# no closing-backtick requirement (unlike Rust's `RUST_BACKTICKED`), so a
# malformed/unclosed backtick reference still names its declaration.
SWIFT_NAME_RE = re.compile(r"`([A-Za-z_][A-Za-z_0-9]*)")


def _swift_declarations(lines: list[str]):
    """Every `(line_index, name, documented)` declaration in `lines`."""

    found = []
    documented = False
    for i, line in enumerate(lines):
        if DOC_RE.match(line):
            documented = True
            continue
        if SWIFT_ATTR_RE.match(line) or not line.strip():
            continue
        match = SWIFT_DECL_RE.match(line)
        if match:
            found.append((i, match.group(1), documented))
        documented = False
    return found


def _swift_runs(lines: list[str]):
    """Every contiguous block of `///` lines, as `(start, end)` exclusive."""

    start = None
    for i, line in enumerate(lines):
        if DOC_RE.match(line):
            if start is None:
                start = i
        elif start is not None:
            yield start, i
            start = None
    if start is not None:
        yield start, len(lines)


def _swift_breaks(lines: list[str]):
    """Every `(break_line, {backticked names above it})` in `lines`."""

    for start, end in _swift_runs(lines):
        for i in range(start + 1, end):
            previous = lines[i - 1]
            if not SWIFT_SENTENCE_END_RE.search(previous) or previous.strip() == "///":
                continue
            if not SWIFT_SUMMARY_RE.match(lines[i]):
                continue
            stranded = " ".join(lines[start:i])
            named = frozenset(SWIFT_NAME_RE.findall(stranded))
            if named:
                yield i + 1, named


def _check_swift(repo_root: Path) -> list[Finding]:
    files = {
        rel: (repo_root / rel).read_text(encoding="utf-8", errors="replace").splitlines()
        for rel in tracked_files(repo_root, "*.swift")
    }

    all_names: set[str] = set()
    for lines in files.values():
        for _, name, _ in _swift_declarations(lines):
            all_names.add(name)

    findings: list[Finding] = []
    for rel, lines in sorted(files.items()):
        if not lines:
            continue
        bare = {
            name: {name}
            for _, name, documented in _swift_declarations(lines)
            if not documented
        }
        for line_no, named in _swift_breaks(lines):
            findings.extend(_emit(rel, line_no, named, bare, all_names))
    return findings


def check(
    repo_root: Path, diff_range: str, config: Mapping[str, object]
) -> list[Finding]:
    return _check_rust(repo_root) + _check_swift(repo_root)


register_check(NAME, check)
