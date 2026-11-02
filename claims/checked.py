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

"""Checked marks: `claims.checked.toml`, a committed record that someone
read an advisory finding, which keeps it quiet until what it was read
against changes (`decisions/0010-checked-marks-expire-on-their-own.md`).
`docs/checked-marks.md` is the account of the file, the command and the
expiry rules; this docstring is why the code is shaped the way it is.

Applied by the runner after every check has run, never inside one, so
`Finding` keeps its contract and no check knows marks exist.

A mark is keyed by a hash of the finding's **unit**, not its line, so it
follows the text. `UNITS` is the fixed table of what that unit is per
check; a mode it doesn't name can't be marked. A `restatement` unit is
the surviving line plus the run its message quotes, so its hash is two:
the line's, which is what has to still exist in the file and what copies
are counted by, and the message's, since the same line surviving a
different retraction is a different finding.

Subjects are resolved by `stale_claims.subjects_named`, so a mark and
`stale-claims` read the same paths and names out of a sentence. They are
read as they are on disk, an anchor's heading included, where
`stale-claims` looks an anchor up at `HEAD` for `git log -L`: a mark
records a content hash per subject rather than a commit, which a rebase
or squash would take out of history, and that hash is of what the reader
had in front of them.
"""

from __future__ import annotations

import hashlib
import json
import re
import tomllib
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import NamedTuple

from .config import ConfigError
from .git import tracked_files
from .markdown import fence_state, prose_lines, section_range, sentences_from
from .runner import Finding
from .words import normalise

CHECKED_FILENAME = "claims.checked.toml"

# The `mode` an orphaned mark is reported under: no check produced it, the
# way `"config"` names no check either.
ORPHAN_MODE = "checked-mark"

SENTENCE = "sentence"
HEADING = "heading"
LINE = "surviving line"
DOC_COMMENT = "doc comment"

# Which unit each markable check's findings are keyed by, by check name;
# a mode is that name or `name-suffix`, as `gate._finding_check` reads it.
UNITS = {
    "claim-words": SENTENCE,
    "temporal-words": SENTENCE,
    "judgment-agent": SENTENCE,
    "stale-claims": HEADING,
    "restatement": LINE,
    "spliced-docs": DOC_COMMENT,
}

# `stale-claims`' own section split: a heading-shaped line starts one,
# fenced or not, so a mark's section is the one that check ranked.
_SECTION_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")
_DOC_RE = re.compile(r"^\s*///")
_MARK_HEADER_RE = re.compile(r"^\s*\[\[\s*mark\s*\]\]\s*(#.*)?$")
_KEYS = {"file", "mode", "unit", "copies", "subjects", "note", "by"}


def unit_kind(mode: str) -> str | None:
    for name, kind in UNITS.items():
        if mode == name or mode.startswith(f"{name}-"):
            return kind
    return None


@dataclass(frozen=True)
class Mark:
    file: str
    mode: str
    unit: str
    copies: int
    subjects: Mapping[str, str]
    note: str
    by: str | None = None
    # The 1-based line of this entry's `[[mark]]` header, which an orphan
    # finding cites; 0 for a mark not yet written.
    line: int = 0

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.file, self.mode, self.unit)


class _Unit(NamedTuple):
    start: int  # 0-based, inclusive
    end: int  # 0-based, inclusive
    digest: str  # its words, hashed
    body: str  # what subjects are read from


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _words_digest(text: str) -> str:
    return _digest(" ".join(normalise(text)))


def _in_file(unit_hash: str) -> str:
    """The part of a mark's `unit` that has to still exist in its file,
    and that copies are counted by: all of it but a `restatement`
    message's hash."""

    return unit_hash.split("-")[0]


def _repo_relative(rel: str) -> bool:
    """Whether `rel` is a path inside the repository as written: a
    committed sidecar is a pull request's to edit, and `/dev/zero` or
    `../` would have every reviewer's hook read outside it."""

    path = PurePosixPath(rel)
    return bool(rel) and not path.is_absolute() and ".." not in path.parts


def _regular_file(repo_root: Path, rel: str) -> Path | None:
    """`rel` as a regular file inside `repo_root` once symlinks are
    followed, or `None`: a link to a device or out of the tree is never
    read."""

    try:
        resolved = (repo_root / rel).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if not resolved.is_relative_to(repo_root.resolve()) or not resolved.is_file():
        return None
    return resolved


def _units(kind: str, lines: Sequence[str]) -> list[_Unit]:
    if kind == SENTENCE:
        units = [
            _Unit(start, end, _words_digest(sentence), sentence)
            for sentence, start, end in sentences_from(prose_lines(lines))
        ]
        # A fenced line is in no sentence, and `judgment-agent` cites a
        # name wherever it appears: there, the line is the unit.
        units.extend(
            _Unit(i, i, _words_digest(line), line)
            for i, (line, fenced) in enumerate(zip(lines, fence_state(lines)))
            if fenced and normalise(line)
        )
        return units
    if kind == HEADING:
        # A repeated heading is a different anchor, as `-1` makes it on
        # GitHub, not a second copy of one section: each has its own body.
        # `#` is never in normalised words, so `foo#1` can't be a heading's.
        # A file with no heading is one section, reported at its first line.
        starts = [i for i, line in enumerate(lines) if _SECTION_HEADING_RE.match(line)]
        if not starts:
            return [_Unit(0, 0, _digest(""), "\n".join(lines))] if lines else []
        seen: Counter[str] = Counter()
        units = []
        for start, end in zip(starts, starts[1:] + [len(lines)]):
            heading = _SECTION_HEADING_RE.match(lines[start])
            assert heading is not None
            words = " ".join(normalise(heading.group(2)))
            digest = _digest(f"{words}#{seen[words]}" if seen[words] else words)
            seen[words] += 1
            units.append(_Unit(start, start, digest, "\n".join(lines[start:end])))
        return units
    if kind == LINE:
        return [
            _Unit(i, i, _words_digest(line), line) for i, line in enumerate(lines) if normalise(line)
        ]
    units = []
    i = 0
    while i < len(lines):
        if not _DOC_RE.match(lines[i]):
            i += 1
            continue
        start = i
        while i < len(lines) and _DOC_RE.match(lines[i]):
            i += 1
        text = "\n".join(lines[start:i])
        units.append(_Unit(start, i - 1, _words_digest(text), text))
    return units


class _Tree:
    """What applying or writing marks reads from the working tree, each
    read once per run."""

    def __init__(self, repo_root: Path, config: Mapping[str, object]) -> None:
        self.repo_root = repo_root
        self.config = config
        self._lines: dict[str, list[str] | None] = {}
        self._units: dict[tuple[str, str], list[_Unit] | None] = {}
        self._resolver: tuple[set[str], dict[str, str]] | None = None
        self._hashes: dict[str, str | None] = {}

    def lines(self, rel: str) -> list[str] | None:
        if rel not in self._lines:
            path = _regular_file(self.repo_root, rel)
            try:
                text = None if path is None else path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = None
            self._lines[rel] = None if text is None else text.splitlines()
        return self._lines[rel]

    def units(self, rel: str, kind: str) -> list[_Unit] | None:
        if (rel, kind) not in self._units:
            lines = self.lines(rel)
            self._units[rel, kind] = None if lines is None else _units(kind, lines)
        return self._units[rel, kind]

    def copies(self, rel: str, kind: str) -> Counter[str]:
        return Counter(u.digest for u in self.units(rel, kind) or [])

    def unit_of(self, finding: Finding) -> tuple[_Unit, str] | None:
        """The unit `finding` sits in and its hash, or `None` when its
        mode can't be marked or its line is in no unit."""

        kind = unit_kind(finding.mode)
        if kind is None:
            return None
        index = finding.line - 1
        covering = [
            unit
            for unit in self.units(finding.file, kind) or []
            if unit.start <= index <= unit.end and (kind != HEADING or unit.start == index)
        ]
        if not covering:
            return None
        # Two sentences can share a line. A sentence check's message is
        # its sentence, and it cites the line the sentence starts on.
        unit = next(
            (u for u in covering if u.body == finding.message),
            next((u for u in covering if u.start == index), covering[0]),
        )
        digest = unit.digest
        if kind == LINE:
            digest += "-" + _words_digest(finding.message)
        return unit, digest

    def subject_hash(self, subject: str) -> str | None:
        if subject not in self._hashes:
            self._hashes[subject] = self._read_hash(subject)
        return self._hashes[subject]

    def _read_hash(self, subject: str) -> str | None:
        path, _, anchor = subject.partition("#")
        resolved = _regular_file(self.repo_root, path)
        if resolved is None:
            return None
        try:
            text = resolved.read_bytes()
        except OSError:
            return None
        if not anchor:
            return hashlib.sha256(text).hexdigest()[:16]
        decoded = text.decode("utf-8", errors="replace")
        span = section_range(decoded, anchor)
        if span is None:
            return None
        return _digest("\n".join(decoded.splitlines()[span[0] - 1 : span[1]]))

    def subjects(self, rel: str, unit: _Unit) -> dict[str, str]:
        """`{subject: content hash}` for each subject `unit`, in `rel`,
        names that exists on disk: one tracked but deleted has no content
        to record or compare."""

        # Imported here: `stale_claims` registers itself with the runner on
        # import, and this module is imported by the runner.
        from .checks.stale_claims import NAME, module_index, subjects_named

        stale_config = self.config.get(NAME, {})
        if not isinstance(stale_config, Mapping):
            stale_config = {}
        if self._resolver is None:
            tracked = tracked_files(self.repo_root)
            try:
                modules = module_index(tracked, stale_config)
            except (ConfigError, TypeError):
                # `stale-claims` reports its own bad `exclude` when it
                # runs; this is no reason to call the sidecar invalid.
                modules = module_index(tracked, {})
            self._resolver = (set(tracked), modules)
        citable, modules = self._resolver

        def section(path: str, anchor: str) -> bool:
            lines = self.lines(path)
            return lines is not None and section_range("\n".join(lines), anchor) is not None

        try:
            found = subjects_named(rel, unit.body, stale_config, citable, modules, section)
        except (ConfigError, TypeError):
            # `stale-claims` reports its own bad key; read with defaults.
            found = subjects_named(rel, unit.body, {}, citable, modules, section)
        hashes = {
            subject: self.subject_hash(subject)
            for subject in (f"{path}#{anchor}" if anchor else path for path, anchor in found)
        }
        return {subject: h for subject, h in hashes.items() if h is not None}


def _invalid(line: int, problem: str) -> ConfigError:
    return ConfigError(f"the [[mark]] at line {line} {problem}")


def load_marks(repo_root: Path) -> list[Mark]:
    """Every mark in `repo_root`'s `claims.checked.toml`, `[]` when there
    is no file. Raises `ConfigError` for a file that doesn't parse or an
    entry of the wrong shape, an empty note included."""

    path = repo_root / CHECKED_FILENAME
    if not path.exists() and not path.is_symlink():
        return []
    # Committed, so a pull request's to make a symlink out of the tree.
    resolved = _regular_file(repo_root, CHECKED_FILENAME)
    if resolved is None:
        raise ConfigError("is not a regular file inside the repository")
    try:
        text = resolved.read_text(encoding="utf-8")
        data = tomllib.loads(text)
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        raise ConfigError(str(e)) from e
    unknown = set(data) - {"mark"}
    if unknown:
        raise ConfigError(f"unknown top-level key {sorted(unknown)[0]!r}")
    entries = data.get("mark", [])
    headers = [n for n, line in enumerate(text.splitlines(), 1) if _MARK_HEADER_RE.match(line)]
    if not isinstance(entries, list) or len(headers) != len(entries):
        raise ConfigError("marks must be written as [[mark]] tables")

    marks = []
    for line, entry in zip(headers, entries):
        if not isinstance(entry, dict):
            raise _invalid(line, "is not a table")
        unknown = set(entry) - _KEYS
        if unknown:
            raise _invalid(line, f"has an unknown key {sorted(unknown)[0]!r}")
        for key in ("file", "mode", "unit", "note"):
            if not isinstance(entry.get(key), str) or not entry[key].strip():
                raise _invalid(line, f"needs a non-empty string {key!r}")
        copies = entry.get("copies")
        if isinstance(copies, bool) or not isinstance(copies, int) or copies < 1:
            raise _invalid(line, "needs 'copies', a positive integer")
        subjects = entry.get("subjects")
        if not isinstance(subjects, dict) or not all(
            isinstance(v, str) for v in subjects.values()
        ):
            raise _invalid(line, "needs 'subjects', a table of path to content hash")
        if not _repo_relative(entry["file"]):
            raise _invalid(line, "has a 'file' outside the repository")
        if not all(_repo_relative(s.partition("#")[0]) for s in subjects):
            raise _invalid(line, "has a subject outside the repository")
        by = entry.get("by")
        if by is not None and not isinstance(by, str):
            raise _invalid(line, "has a 'by' that is not a string")
        marks.append(
            Mark(
                file=entry["file"],
                mode=entry["mode"],
                unit=entry["unit"],
                copies=copies,
                subjects=dict(subjects),
                note=entry["note"],
                by=by,
                line=line,
            )
        )
    return marks


def _current(tree: _Tree, mark: Mark, rel: str, unit: _Unit) -> bool:
    """Whether everything `mark` was read against is as it was."""

    if any(tree.subject_hash(s) != h for s, h in mark.subjects.items()):
        return False
    return tree.subjects(rel, unit).keys() <= mark.subjects.keys()


def apply_marks(
    repo_root: Path, findings: Sequence[Finding], config: Mapping[str, object]
) -> tuple[list[Finding], list[Finding]]:
    """`(shown, quieted)`: `findings` with every one a current mark keeps
    quiet moved to `quieted`, and an orphan finding added to `shown` for
    each mark whose unit is gone from its file. Raises `ConfigError` for
    an invalid `claims.checked.toml`."""

    marks = load_marks(repo_root)
    if not marks:
        return list(findings), []
    by_key = {mark.key: mark for mark in marks}
    marked_files = {mark.file for mark in marks}
    tree = _Tree(repo_root, config)

    groups: dict[tuple[str, str, str], list[Finding]] = {}
    units: dict[tuple[str, str, str], _Unit] = {}
    for finding in findings:
        if finding.gate or finding.file not in marked_files:
            continue
        found = tree.unit_of(finding)
        if found is None:
            continue
        key = (finding.file, finding.mode, found[1])
        if key in by_key:
            groups.setdefault(key, []).append(finding)
            units[key] = found[0]

    quiet: list[Finding] = []
    for key, group in groups.items():
        mark = by_key[key]
        if not _current(tree, mark, mark.file, units[key]):
            continue
        kind = unit_kind(mark.mode)
        assert kind is not None
        # The file's copies beyond the mark's are unread, and which of the
        # reported ones they are can't be told, so that many stay shown.
        held = tree.copies(mark.file, kind)[_in_file(mark.unit)]
        quiet.extend(group[: max(0, len(group) - (held - mark.copies))])

    quieted = {id(f) for f in quiet}
    shown = [f for f in findings if id(f) not in quieted]
    shown.extend(_orphans(tree, marks))
    return shown, quiet


def _orphans(tree: _Tree, marks: Iterable[Mark]) -> list[Finding]:
    found = []
    for mark in marks:
        kind = unit_kind(mark.mode)
        if kind is None:
            problem = f"is for {mark.mode}, which can't be marked"
        elif not tree.copies(mark.file, kind)[_in_file(mark.unit)]:
            problem = f"is for a {kind} no longer in {mark.file}"
        else:
            continue
        found.append(
            Finding(
                file=CHECKED_FILENAME,
                line=mark.line,
                message=f"checked mark ({mark.mode}) {problem}",
                mode=ORPHAN_MODE,
                gate=False,
            )
        )
    return found


ENTRY_RE = re.compile(r"^(?P<file>.+?):(?P<line>\d+)\s+(?P<mode>\S+)(?:\s+(?P<note>.*))?$")


def new_marks(
    repo_root: Path,
    findings: Sequence[Finding],
    config: Mapping[str, object],
    entries: Iterable[str],
    by: str | None,
) -> tuple[list[Mark], list[str]]:
    """`(marks, problems)`: a mark for each of `entries`, one
    `<file>:<line> <mode> <note>` per item, looked up among `findings`,
    and a message naming each entry that can't be marked. Blank entries
    are skipped."""

    tree = _Tree(repo_root, config)
    marks: list[Mark] = []
    problems: list[str] = []
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        parsed = ENTRY_RE.match(entry)
        if parsed is None:
            problems.append(f"{entry}: not `<file>:<line> <mode> <note>`")
            continue
        file, line, mode = parsed["file"], int(parsed["line"]), parsed["mode"]
        note = (parsed["note"] or "").strip()
        matching = [f for f in findings if (f.file, f.line, f.mode) == (file, line, mode)]
        if any(f.gate for f in matching):
            problems.append(f"{entry}: a gate finding can't be marked")
        elif unit_kind(mode) is None:
            problems.append(f"{entry}: {mode} findings can't be marked")
        elif not matching:
            problems.append(f"{entry}: no advisory finding at {file}:{line} ({mode})")
        elif not note:
            problems.append(f"{entry}: needs a note saying what was verified")
        else:
            found = tree.unit_of(matching[0])
            if found is None:
                problems.append(f"{entry}: the finding's line is in no {unit_kind(mode)}")
                continue
            unit, digest = found
            kind = unit_kind(mode)
            assert kind is not None
            subjects = dict(sorted(tree.subjects(file, unit).items()))
            marks.append(
                Mark(
                    file=file,
                    mode=mode,
                    unit=digest,
                    copies=tree.copies(file, kind)[_in_file(digest)],
                    subjects=subjects,
                    note=note,
                    by=by,
                )
            )
    return marks, problems


def _toml_string(value: str) -> str:
    # A JSON string is a valid TOML basic string.
    return json.dumps(value, ensure_ascii=False)


def _render(mark: Mark) -> str:
    lines = [
        "[[mark]]",
        f"file = {_toml_string(mark.file)}",
        f"mode = {_toml_string(mark.mode)}",
        f"unit = {_toml_string(mark.unit)}",
        f"copies = {mark.copies}",
        f"note = {_toml_string(mark.note)}",
    ]
    if mark.by is not None:
        lines.append(f"by = {_toml_string(mark.by)}")
    subjects = ", ".join(f"{_toml_string(s)} = {_toml_string(h)}" for s, h in mark.subjects.items())
    lines.append(f"subjects = {{ {subjects} }}" if subjects else "subjects = {}")
    return "\n".join(lines) + "\n"


def write_marks(repo_root: Path, marks: Sequence[Mark]) -> None:
    """Add `marks` to `claims.checked.toml`, each replacing an existing
    entry with its key. Every other entry's text, comments included, is
    kept as written."""

    path = repo_root / CHECKED_FILENAME
    existing = load_marks(repo_root)
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    replaced = {mark.key for mark in marks}

    lines = text.splitlines(keepends=True)
    starts = [m.line - 1 for m in existing]
    kept = "".join(lines[: starts[0]] if starts else lines)
    for mark, start, end in zip(existing, starts, starts[1:] + [len(lines)]):
        if mark.key not in replaced:
            kept += "".join(lines[start:end])
    blocks = [kept.rstrip("\n")] if kept.strip() else []
    latest = {mark.key: mark for mark in marks}
    blocks.extend(_render(mark).rstrip("\n") for mark in latest.values())
    path.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")
