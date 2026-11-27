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

"""A reading agent's report (`claims/subagent/reading_agent.md`), parsed,
and checked against the findings the session sent it (#299).

The parsing is shared: `check_reading`, which `claims.cli check-reading`
runs before the check-claims skill marks anything, and the golden
harness, `scripts/run_reading_agent_golden.py`, read a finding line, the
object naming it, a `read` entry and a claim's evidence the same way, so
neither can find a file or a line in a report that the other misses.

A path in a report is given from the root, or in a tree, as
`.claims/trees/<commit>/` and the path, or as the path beside the tree's
role or commit. A bare file name names a file only where the root holds
it under that name, so `store.py` for `src/store.py` names no file.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .checked import HEADING, _units, unit_kind
from .lines import git_lines, tracked_text
from .markdown import section_range

# Where `claims claim-trees` copies a commit's tree, under the root.
TREES = ".claims/trees/"
# A finding line, as the runner prints it: its `file:line` and mode.
FINDING_RE = re.compile(r"^\[advisory\] (\S+):(\d+) \(([^)]+)\)", re.M)
# A tree `claim-trees` printed, that a claim is read at: its role and commit.
TREE_RE = re.compile(r"^(written|before) (\w+) ", re.M)
SPAN = r"L?\d+(?:\s*[-–]\s*L?\d+)?"
# What comes between two spans of one file's lines: "9-13 (put), 20 and 31".
_NEXT = r"(?:\s*\([^()]*\))?(?:\s*[,;]\s*(?:and\s+|plus\s+)?|\s+and\s+|\s+plus\s+)"
_SPANS = rf"{SPAN}(?:{_NEXT}{SPAN})*"
# A file a claim's evidence cites, and the lines of it, if it gives any.
CITED_RE = re.compile(
    rf"(?:\blines?\s+(?P<before>{_SPANS})\s+(?:of|in)\s+`?)?"
    rf"(?<![\w./-])(?P<path>[\w./-]*[\w-]\.[A-Za-z]\w*)`?"
    rf"(?:(?P<mark>[:#]|[\s,(]*\blines?\s+)(?P<after>{_SPANS}))?"
)
_ANCHOR_RE = re.compile(r"#([\w-]+)")

# The trees a finding was sent with, each `(role, commit)`.
Trees = Sequence[tuple[str, str]]


def extract_array(text: str) -> tuple[Any, bool]:
    """The JSON array the agent's final message holds, or `None` when the
    first JSON value in it is not an array: a bare object's own `"claims": [`
    is not an array of reports. Beside it, whether the message is that array
    alone, with nothing before or after it but whitespace: no fence, no prose."""

    starts = [i for i in (text.find("["), text.find("{")) if i != -1]
    if not starts or text[min(starts)] != "[":
        return None, False
    try:
        array, end = json.JSONDecoder().raw_decode(text, min(starts))
    except ValueError:
        return None, False
    return array, not text[: min(starts)].strip() and not text[end:].strip()


def relative(path: str, root: Path) -> str:
    """`path`, as a `Read` call or a report gives it, relative to `root` when it is inside it."""

    return os.path.relpath(path, root) if path.startswith(f"{root}/") else os.path.normpath(path)


def names_finding(named: str, path: str, line: int, mode: str) -> bool:
    """Whether `named`, an object's `finding` field, names the finding at `path:line` of `mode`."""

    return bool(re.search(rf"(?<![\w./-]){re.escape(f'{path}:{line}')}(?!\d)", named)) and mode in named


def _tree_marks(trees: Trees) -> list[tuple[str, re.Pattern[str]]]:
    return [(commit, re.compile(rf"\b{role}\b|{commit[:7]}")) for role, commit in trees]


def listing(path: str, read: Sequence[str], root: Path, trees: Trees) -> list[str]:
    """Each entry of a report's `read` naming `path`, with the root's own
    prefix taken off: a file of the root by its path, in an entry that
    isn't a tree's alone; a file in a tree by its path, or by its relative
    path beside its tree's commit or role."""

    entries = [entry.replace(f"{root}/", "") for entry in read]
    named = re.compile(rf"(?<![\w./-])(?:\./)?{re.escape(path)}(?![\w/-])")
    marks = _tree_marks(trees)
    if path.startswith(TREES):
        commit, _, inner = path.removeprefix(TREES).partition("/")
        own = [mark for c, mark in marks if c == commit] or [re.compile(commit[:7])]
        return [e for e in entries if named.search(e) or (inner in e and any(m.search(e) for m in own))]
    return [e for e in entries if named.search(e) and ("root" in e or not any(m.search(e) for _, m in marks))]


def _lines(match: re.Match[str]) -> set[int]:
    """The lines a `CITED_RE` match gives, before its path or after it."""

    lines: set[int] = set()
    for span in re.findall(SPAN, re.sub(r"\([^()]*\)", "", f"{match['before'] or ''} {match['after'] or ''}")):
        numbers = [int(n) for n in re.findall(r"\d+", span)]
        lines.update(range(numbers[0], numbers[-1] + 1))
    return lines


def cited(evidence: str, tree: str, root: Path, trees: Trees) -> tuple[list[tuple[list[str], set[int]]], list[str]]:
    """Each file `evidence` cites, with the lines of it, if it gives any, and
    each path it cites lines of that is no file. A file is every path it may
    be at: in each of `trees` that `tree`, a claim's own `tree` field,
    names, in the root when it names that or no tree, or else in the root,
    for a file the trees don't hold."""

    named = [c for role, c in trees if re.search(rf"\b{role}\b|{c[:7]}", tree)]
    places = [f"{TREES}{commit}/" for commit in named]
    if "root" in tree or not named:
        places.append("")
    found: list[tuple[list[str], set[int]]] = []
    missing: list[str] = []
    for match in CITED_RE.finditer(evidence):
        path = relative(match["path"], root)
        paths = [p + path for p in places if (root / p / path).is_file()]
        if not paths and (root / path).is_file():
            paths = [path]
        if not paths or path.startswith(("/", "..")):
            if match["mark"] in {":", "#"}:
                missing.append(path)
            continue
        found.append((paths, _lines(match)))
    return found, missing


@dataclass(frozen=True)
class Sent:
    """A finding as the session sent it to the reading agent: where its
    unit starts and its mode, read from its finding line, the subjects it
    named, its root, and the trees it carried."""

    path: str
    line: int
    mode: str
    subjects: tuple[str, ...]
    root: Path
    trees: tuple[tuple[str, str], ...] = ()

    @property
    def name(self) -> str:
        return f"{self.path}:{self.line} {self.mode}"


# What an object naming no finding sent is reported against.
NOT_SENT = "(not sent)"


@dataclass(frozen=True)
class Flag:
    """One item `check_reading` flags: the finding it is in, by its
    `file:line` and mode, or `NOT_SENT`, its type, and what it is. A
    `read` flag names, in `path`, the file it is about."""

    finding: str
    type: str
    detail: str
    path: str = ""

    def __str__(self) -> str:
        return f"{self.finding} {self.type}: {self.detail}"


def load_sent(data: Any) -> list[Sent]:
    """The findings a session sent, from the JSON it wrote: an array of
    objects, each with `finding`, the finding line verbatim, `subjects`,
    the subjects it named, `root`, and optionally `trees`, each a line
    `claim-trees` printed for it. Raises `ValueError` on any other shape."""

    if not isinstance(data, list):
        raise ValueError("the findings sent are not a JSON array")
    sent: list[Sent] = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError(f"not a finding: {item!r}")
        line, subjects, root, trees = (item.get(k) for k in ("finding", "subjects", "root", "trees"))
        unit = FINDING_RE.match(line) if isinstance(line, str) else None
        if unit is None:
            raise ValueError(f"no finding line in {item!r}")
        if not isinstance(subjects, list) or not all(isinstance(s, str) for s in subjects):
            raise ValueError(f"subjects are not a list of strings in {item!r}")
        if not isinstance(root, str) or not Path(root).is_dir():
            raise ValueError(f"root is no directory in {item!r}")
        if trees is None:
            trees = []
        if not isinstance(trees, list) or not all(isinstance(t, str) for t in trees):
            raise ValueError(f"trees are not a list of strings in {item!r}")
        sent.append(
            Sent(
                path=unit.group(1),
                line=int(unit.group(2)),
                mode=unit.group(3),
                subjects=tuple(subjects),
                root=Path(root).resolve(),
                trees=tuple((m.group(1), m.group(2)) for t in trees if (m := TREE_RE.match(f"{t} "))),
            )
        )
    return sent


def matched(reports: Any, sent: Sequence[Sent]) -> tuple[dict[Sent, list[dict[str, Any]]], list[Flag]]:
    """The objects in `reports` naming each finding in `sent`, none for
    any when `reports` is no array, and a flag for each object naming no
    finding sent."""

    if not isinstance(reports, list):
        return {s: [] for s in sent}, []
    found: dict[Sent, list[dict[str, Any]]] = {s: [] for s in sent}
    flags: list[Flag] = []
    for report in reports:
        named = str(report.get("finding", "")) if isinstance(report, dict) else ""
        finding = next((s for s in sent if names_finding(named, s.path, s.line, s.mode)), None)
        if finding is None:
            flags.append(Flag(NOT_SENT, "matching", f"an object for no finding sent: {named or report!r}"))
        else:
            found[finding].append(report)
    return found, flags


def _text(root: Path, path: str) -> list[str] | None:
    file = root / path
    return git_lines(tracked_text(file, errors="replace")) if file.is_file() else None


def _entry_lines(entry: str, path: str, root: Path, lines: Sequence[str]) -> set[int] | None:
    """The lines of `path`, of `lines`, that `entry`, a `read` entry
    naming it, gives: those it numbers, or its `#anchor` section's, or
    `None` for the whole file."""

    inner = path.removeprefix(TREES).partition("/")[2] if path.startswith(TREES) else path
    for match in CITED_RE.finditer(entry):
        if relative(match["path"], root) not in {path, inner}:
            continue
        if numbered := _lines(match):
            return numbered
        anchor = _ANCHOR_RE.match(entry, match.end())
        if anchor is None:
            return None
        section = section_range("\n".join(lines), anchor.group(1))
        return set(range(section[0], section[1] + 1)) if section else set()
    return None


def _covered(path: str, wanted: set[int] | None, report_read: Sequence[str], sent: Sent) -> bool | None:
    """Whether `report_read` gives `wanted` of `path`, the whole file for
    `None`: `None` when it doesn't list `path` at all."""

    entries = listing(path, report_read, sent.root, sent.trees)
    if not entries:
        return None
    lines = _text(sent.root, path) or []
    given: set[int] = set()
    for entry in entries:
        extent = _entry_lines(entry, path, sent.root, lines)
        if extent is None:
            return True
        given |= extent
    return (set(range(1, len(lines) + 1)) if wanted is None else wanted) <= given


def _unit_lines(sent: Sent, lines: Sequence[str]) -> set[int]:
    """The lines of `sent`'s unit, less blank ones at its end, by the unit
    `claims.checked` keys its mark by; its line alone when none starts there."""

    kind = unit_kind(sent.mode)
    ends = [
        unit.start + unit.body.count("\n") if kind == HEADING else unit.end
        for unit in (_units(kind, lines) if kind else [])
        if unit.start == sent.line - 1
    ]
    end = max(ends, default=sent.line - 1)
    while end > sent.line - 1 and not lines[end].strip():
        end -= 1
    return set(range(sent.line, end + 2))


def _unread(report: dict[str, Any], sent: Sent) -> list[Flag]:
    """A flag for the unit, and each subject the root holds, that the
    report's `read` doesn't list, or gives only part of."""

    report_read = _read_of(report)
    lines = _text(sent.root, sent.path)
    needed = [(sent.path, "the unit", None if lines is None else _unit_lines(sent, lines))]
    for subject in sent.subjects:
        path, _, anchor = subject.partition("#")
        subject_lines = _text(sent.root, path)
        if subject_lines is None:
            continue
        section = section_range("\n".join(subject_lines), anchor) if anchor else None
        needed.append((path, f"subject {subject}", set(range(section[0], section[1] + 1)) if section else None))
    flags: list[Flag] = []
    for path, what, wanted in needed:
        covered = _covered(path, wanted, report_read, sent)
        if covered is None:
            flags.append(Flag(sent.name, "read", f"{what}, {path}, is not in read", path))
        elif not covered:
            flags.append(Flag(sent.name, "read", f"{what}, {path}, is listed with only part of it", path))
    return flags


def _read_of(report: dict[str, Any]) -> list[str]:
    listed_read = report.get("read")
    return [str(r) for r in listed_read] if isinstance(listed_read, list) else []


def _claim_flags(report: dict[str, Any], sent: Sent) -> list[Flag]:
    """A flag for a report listing no claims, for each `not checked` claim,
    for each `true` one whose evidence names no file, and for each file a
    `true` claim cites, at the claim's own tree, that the report's `read`
    doesn't list, or lines of one outside what its `read` entry gives,
    whatever else the claim cites was read."""

    claims = report.get("claims")
    flags: list[Flag] = []
    if not isinstance(claims, list) or not claims:
        return [Flag(sent.name, "no-claims", "the object lists no claims, so nothing in its unit was read")]
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        quoted = _quoted(claim)
        if claim.get("verdict") == "not checked":
            detail = f"{quoted}: {' '.join(str(claim.get('reasoning', '')).split())}"
            if claim.get("tree_line"):
                detail += f" (tree_line {claim['tree_line']})"
            flags.append(Flag(sent.name, "not-checked", detail))
        if claim.get("verdict") != "true":
            continue
        files, missing = cited(str(claim.get("evidence", "")), str(claim.get("tree", "")), sent.root, sent.trees)
        if missing or not files:
            flags.append(Flag(sent.name, "no-file", f"{quoted} has evidence naming no file: {claim.get('evidence', '')!r}"))
        for paths, lines in files:
            covered = [c for p in paths if (c := _covered(p, lines or set(), _read_of(report), sent)) is not None]
            if not covered:
                flags.append(Flag(sent.name, "cited", f"{quoted} cites {paths[0]}, which is not in read"))
            elif not any(covered):
                flags.append(Flag(sent.name, "cited", f"{quoted} cites lines of {paths[0]} outside what read gives"))
    return flags


def _quoted(claim: dict[str, Any]) -> str:
    text = " ".join(str(claim.get("claim", "")).split())
    return json.dumps(text if len(text) <= 60 else f"{text[:57]}...")


def check_reading(reports: Any, sent: Sequence[Sent]) -> list[Flag]:
    """Every item a reading agent's `reports` leaves for the session to
    settle before marking, per finding in `sent`, in order, then each
    object naming no finding sent (the check-claims skill's steps 4 and 6)."""

    found, unsent = matched(reports, sent)
    flags: list[Flag] = []
    for finding, objects in found.items():
        if len(objects) != 1:
            if not isinstance(reports, list):
                detail = "the output holds no JSON array"
            else:
                detail = f"{len(objects)} objects for it" if objects else "no object for it"
            flags.append(Flag(finding.name, "matching", detail))
            continue
        flags += _unread(objects[0], finding) + _claim_flags(objects[0], finding)
    return flags + unsent
