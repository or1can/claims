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
`Finding` keeps its contract. Some checks read marks, and none applies
them. `restatement` asks `retractions_held` which committed marks record
a retraction whose surviving line a pending change rewords (#250). That
mark is the only record left of a retraction an earlier commit made, and
without it the commit doing the rewording raises nothing where the
branch run raises a finding no commit's own run showed. `claim-words`,
`temporal-words` and `judgment-agent`, which report only what a range
added, ask `expired_units` which marks the range expired, and read those
units as if the range had added them (#263), for the same reason: the
change that expires a mark is the one that can mark it again.

A mark is "expired by the range" when it is current at the range's old
side and not in the working tree, so `_Tree` reads either: the old side
through git's objects, the new one from disk. One already expired at the
old side was an earlier change's to raise.

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

An append-only subject (ADR 0011) records its git blob id instead, the
one record of what the reader saw that its later growth can be compared
against: the blob is read back from the object store, never from
history, so a rebase or squash still leaves the mark alone. The id is
never written to the store here: a blob committed is in every clone that
fetches the commit, where one written for this clone alone would hold
the mark here and expire it everywhere else.

A navigation page (ADR 0013) named without an anchor is neither recorded
nor compared, so a mark written before the page was listed keeps its
entry for it and stops reading it, with no rewrite of the sidecar.

A mark records its claim's kind (ADR 0019). A past or superseded claim
is read at a tree that doesn't move, so its mark compares no subject:
it records its unit's whole text, which for a section is its body as
well as the heading the unit hash covers, and the evidence its kind
rests on, and expires when either changes. Both are hashed as words, as
a unit is, so a reflow keeps the mark. The evidence is also what the
approval listing compares with the range's base, so a change can't
quietly add the Status note that supersedes a claim it breaks.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tomllib
from collections import Counter
from collections.abc import Callable, Container, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import Path, PurePosixPath
from typing import NamedTuple

from .config import ConfigError, append_only, counts_as_subject, load_config
from .git import (
    DiffLine,
    blob_bytes,
    blob_id,
    blob_text,
    head_commit,
    iter_diff,
    parent_commits,
    path_blobs,
    range_base,
    read_blob,
    tracked_files,
)
from .lines import git_lines
from .markdown import CODE_SPAN_RE, fence_state, prose_lines, section_range, sentences_from
from .runner import Finding
from .words import normalise

CHECKED_FILENAME = "claims.checked.toml"

# The `mode` an orphaned mark is reported under: no check produced it, the
# way `"config"` names no check either.
ORPHAN_MODE = "checked-mark"

SENTENCE = "sentence"
# `judgment-agent` cites a name wherever it appears, a fenced line
# included, where no sentence holds it: there, the line is the unit.
CITATION = "sentence or fenced line"
HEADING = "heading"
LINE = "surviving line"
DOC_COMMENT = "doc comment"
# A demoted historical reference (ADR 0020): the line, and the path or
# link its message quotes first, since one line can name several.
REFERENCE = "reference"

# Which unit each markable check's findings are keyed by, by check name;
# a mode is that name or `name-suffix`, as `gate._finding_check` reads it.
UNITS = {
    "claim-words": SENTENCE,
    "temporal-words": SENTENCE,
    "judgment-agent": CITATION,
    "stale-claims": HEADING,
    "restatement": LINE,
    "spliced-docs": DOC_COMMENT,
    "check-links": REFERENCE,
    "check-file-refs": REFERENCE,
}

# A check whose only markable findings are one mode of it: a gate check's
# demoted historical reference (ADR 0020), and not, say, `check-file-refs`'
# dangling example marker, which deleting the marker settles.
_ONLY_MODE = {
    "check-links": "check-links-historical",
    "check-file-refs": "check-file-refs-historical",
}

# `stale-claims`' own section split: a heading-shaped line starts one,
# fenced or not, so a mark's section is the one that check ranked.
_SECTION_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)")
_DOC_RE = re.compile(r"^\s*///")
_MARK_HEADER_RE = re.compile(r"^\s*\[\[\s*mark\s*\]\]\s*(#.*)?$")
_KEYS = {
    "file", "mode", "unit", "copies", "subjects", "note", "by", "approved_by", "extent", "review",
    "kind", "text", "evidence",
}
# A claim's kinds (ADR 0019) as a mark records them; a mark with none is
# current. `SETTLED` are the kinds read at a tree that doesn't move.
KINDS = ("intended", "superseded", "past")
SETTLED = ("superseded", "past")
# A full SHA-1 or SHA-256 object id: what an append-only subject records.
# Nothing else is passed to `git cat-file`: the sidecar is committed, so a
# pull request could otherwise hand it a revision or an option.
_BLOB_ID_RE = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?")


def markable_check(mode: str) -> str | None:
    """The `UNITS` check whose findings `mode` names, or `None`."""

    for name in UNITS:
        if mode == name or mode.startswith(f"{name}-"):
            only = _ONLY_MODE.get(name)
            return name if only is None or mode == only else None
    return None


def unmarkable_names(names: Sequence[str]) -> str | None:
    """Why `names` can't be a list of markable checks to fail on, or
    `None`: the one wording `--fail-on-unmarked` and `[hook]
    fail_on_unmarked` both report."""

    unknown = [n for n in names if n not in UNITS]
    if not unknown:
        return None
    return f"{', '.join(unknown)} is not a markable check (one of {', '.join(UNITS)})"


def failing_unmarked(count: int) -> str:
    """The closing line of a run or commit failing on `count` unmarked
    findings."""

    return f"failing: {count} unmarked advisory finding(s); fix or mark each"


def unit_kind(mode: str) -> str | None:
    name = markable_check(mode)
    return None if name is None else UNITS[name]


@dataclass(frozen=True)
class Mark:
    file: str
    mode: str
    unit: str
    copies: int
    subjects: Mapping[str, str]
    note: str
    # Who read it; `approved_by`, who approved that reading (ADR 0018).
    by: str | None = None
    approved_by: str | None = None
    # Whether the reading was partial (ADR 0010); a sidecar records an
    # `extent` only for a partial mark, so an entry without one is full.
    partial: bool = False
    # Whether no person has reviewed the reading yet (ADR 0014); a sidecar
    # records `review = "pending"` only for a pending mark.
    pending: bool = False
    # The claim's kind, one of `KINDS`, or `None` for current (ADR 0019).
    kind: str | None = None
    # For a `SETTLED` kind only: the hash of the unit's whole text, and of
    # each file or section its kind rests on, by `path` or `path#anchor`.
    text: str | None = None
    evidence: Mapping[str, str] = field(default_factory=dict)
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


def message_hash(message: str) -> str:
    """The second half of a `LINE` unit: the hash of the finding's
    message, since the same line surviving a different retraction is a
    different finding."""

    return _words_digest(message)


def _evidence_digest(lines: Sequence[str], anchor: str) -> str | None:
    """The hash a mark records for evidence in a file of `lines`: its
    words, or its section's when `anchor` names one, or `None` when no
    heading has that slug."""

    if anchor:
        span = section_range("\n".join(lines), anchor)
        if span is None:
            return None
        lines = lines[span[0] - 1 : span[1]]
    return _words_digest("\n".join(lines))


def _blob_lines(data: bytes) -> list[str]:
    """`data`'s lines, numbered by `\n` alone as git numbers them, with a
    `\r\n` read as `\n`, so a working-tree copy checked out with `\r\n`
    compares line for line with the blob it was checked out from."""

    return git_lines(data.decode("utf-8", errors="replace").replace("\r\n", "\n"))


def _only_grew(old: Sequence[str], new: Sequence[str]) -> bool:
    """Whether every line of `old` is still in `new`, in order: a diff
    from one to the other removes no lines."""

    remaining = iter(new)
    return all(line in remaining for line in old)


def _in_file(unit_hash: str) -> str:
    """The part of a mark's `unit` that has to still exist in its file,
    and that copies are counted by: all of it but a `restatement`
    message's hash, or a demoted reference's."""

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
    if kind in (SENTENCE, CITATION):
        units = [
            _Unit(start, end, _words_digest(sentence), sentence)
            for sentence, start, end in sentences_from(prose_lines(lines))
        ]
        if kind == CITATION:
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
        # A heading-shaped line inside a fence starts none, as `stale-claims`
        # splits sections.
        in_fence = fence_state(lines)
        starts = [
            i
            for i, line in enumerate(lines)
            if not in_fence[i] and _SECTION_HEADING_RE.match(line)
        ]
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
    if kind in (LINE, REFERENCE):
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
    """What applying or writing marks reads from the working tree, or
    with `commit`, from that commit's tree, each read once per run."""

    def __init__(
        self, repo_root: Path, config: Mapping[str, object], commit: str | None = None
    ) -> None:
        self.repo_root = repo_root
        self.config = config
        self.commit = commit
        self._lines: dict[str, list[str] | None] = {}
        self._units: dict[tuple[str, str], list[_Unit] | None] = {}
        self._resolver: tuple[set[str], dict[str, str]] | None = None
        self._hashes: dict[tuple[str, bool], str | None] = {}
        self._grown: dict[tuple[str, str], bool] = {}
        self._blobs: dict[str, set[str]] = {}

    def _bytes(self, rel: str) -> bytes | None:
        if self.commit is not None:
            return blob_bytes(self.repo_root, self.commit, rel)
        path = _regular_file(self.repo_root, rel)
        try:
            return None if path is None else path.read_bytes()
        except OSError:
            return None

    def lines(self, rel: str) -> list[str] | None:
        if rel not in self._lines:
            data = self._bytes(rel)
            self._lines[rel] = None if data is None else git_lines(data.decode("utf-8", errors="replace"))
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
        # Two sentences can share a line. `claim-words` and
        # `temporal-words` quote their sentence; `judgment-agent` quotes
        # the name it cites, which its sentence holds.
        cited = CODE_SPAN_RE.findall(finding.message)
        unit = next(
            (u for u in covering if u.body == finding.message),
            next(
                (u for u in covering if cited and f"`{cited[0]}`" in u.body),
                covering[0],
            ),
        )
        digest = unit.digest
        if kind == LINE:
            digest += "-" + message_hash(finding.message)
        elif kind == REFERENCE and cited:
            # Not the whole message: it names commits, which a rebase or
            # the line's own commit landing would change.
            digest += "-" + _digest(cited[0])
        return unit, digest

    def counts(self, subject: str) -> bool:
        """Whether `subject` is one a mark records and compares: anything
        but a navigation page named without an anchor (ADR 0013), which a
        mark written before the page was listed may still hold."""

        path, _, anchor = subject.partition("#")
        return counts_as_subject(self.config, path, anchor)

    def subject_hash(self, subject: str) -> str | None:
        """What a mark records for `subject`: an append-only file's blob
        id, anything else's content hash."""

        return self._hash(subject, append_only(self.config, subject.partition("#")[0]))

    def _hash(self, subject: str, blob: bool) -> str | None:
        if (subject, blob) not in self._hashes:
            self._hashes[subject, blob] = self._read_hash(subject, blob)
        return self._hashes[subject, blob]

    def _read_hash(self, subject: str, blob: bool) -> str | None:
        path, _, anchor = subject.partition("#")
        text = self._bytes(path)
        if text is None:
            return None
        if not anchor:
            return blob_id(self.repo_root, path, text) if blob else hashlib.sha256(text).hexdigest()[:16]
        decoded = text.decode("utf-8", errors="replace")
        span = section_range(decoded, anchor)
        if span is None:
            return None
        if blob:
            return blob_id(self.repo_root, path, text)
        return _digest("\n".join(git_lines(decoded)[span[0] - 1 : span[1]]))

    def subject_holds(self, subject: str, recorded: str) -> bool:
        """Whether `subject` is as it was when a mark recorded `recorded`
        for it. An append-only file's blob id holds while the recorded
        blob is in `HEAD`'s history of the file or in the index, and its
        lines, or its section's, are all still there (ADR 0011).
        Any other value has to equal the content hash, which is how a mark
        written before a file was append-only goes on being compared."""

        path, _, anchor = subject.partition("#")
        if not (_BLOB_ID_RE.fullmatch(recorded) and append_only(self.config, path)):
            return self._hash(subject, blob=False) == recorded
        current = self._hash(subject, blob=True)
        if current == recorded:
            return True
        if current is None:
            return False
        if (subject, recorded) not in self._grown:
            self._grown[subject, recorded] = self._grew(path, anchor, recorded)
        return self._grown[subject, recorded]

    def _grew(self, path: str, anchor: str, recorded: str) -> bool:
        # Only a blob `HEAD`'s history or the index gives `path` counts: a
        # dangling one a rewrite left in this clone's store is in no other
        # clone's, so it would hold here and expire in CI (#242).
        if path not in self._blobs:
            self._blobs[path] = path_blobs(self.repo_root, path)
        if recorded not in self._blobs[path]:
            return False
        old = read_blob(self.repo_root, recorded)
        current = self._bytes(path)
        if old is None or current is None:
            return False
        old_lines, new_lines = _blob_lines(old), _blob_lines(current)
        if anchor:
            old_span = section_range("\n".join(old_lines), anchor)
            new_span = section_range("\n".join(new_lines), anchor)
            if old_span is None or new_span is None:
                return False
            old_lines = old_lines[old_span[0] - 1 : old_span[1]]
            new_lines = new_lines[new_span[0] - 1 : new_span[1]]
        return _only_grew(old_lines, new_lines)

    def evidence_hash(self, ref: str) -> str | None:
        """What a mark records for evidence `ref`, `path` or
        `path#anchor`, or `None` when it isn't there."""

        path, _, anchor = ref.partition("#")
        lines = self.lines(path)
        return None if lines is None else _evidence_digest(lines, anchor)

    def subjects(self, rel: str, unit: _Unit) -> dict[str, str]:
        """`{subject: subject_hash}` for each subject `unit`, in `rel`,
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
            if self.counts(subject)
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
    # Committed, so a pull request's to make a symlink, and `mark-checked`
    # would write through it to whatever file it names.
    resolved = _regular_file(repo_root, CHECKED_FILENAME)
    if path.is_symlink() or resolved is None:
        raise ConfigError("is not a regular file inside the repository")
    try:
        # Not `tracked_text`: this file is only parsed as TOML, never matched
        # against git's line numbers, and `write_marks` reads it the same way.
        text = resolved.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise ConfigError(str(e)) from e
    return _parse_marks(text)


def _parse_marks(text: str) -> list[Mark]:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(str(e)) from e
    unknown = set(data) - {"mark"}
    if unknown:
        raise ConfigError(f"unknown top-level key {sorted(unknown)[0]!r}")
    entries = data.get("mark", [])
    headers = [n for n, line in enumerate(git_lines(text), 1) if _MARK_HEADER_RE.match(line)]
    if not isinstance(entries, list) or len(headers) != len(entries):
        raise ConfigError("marks must be written as [[mark]] tables")

    marks = []
    # Each key's first `[[mark]]` line: `write_marks` replaces by key, so a
    # second entry for one would be listed as approved yet left as written.
    first_line: dict[tuple[str, str, str], int] = {}
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
        approved_by = entry.get("approved_by")
        if approved_by is not None and not isinstance(approved_by, str):
            raise _invalid(line, "has an 'approved_by' that is not a string")
        extent = entry.get("extent", "full")
        if extent not in ("full", "partial"):
            raise _invalid(line, "has an 'extent' that is neither \"full\" nor \"partial\"")
        if "review" in entry and entry["review"] != "pending":
            raise _invalid(line, "has a 'review' that is not \"pending\"")
        kind = entry.get("kind")
        if kind is not None and kind not in KINDS:
            raise _invalid(line, f"has a 'kind' that is not one of {', '.join(map(repr, KINDS))}")
        unit_text = entry.get("text")
        evidence = entry.get("evidence", {})
        if kind in SETTLED:
            if not isinstance(unit_text, str) or not unit_text.strip():
                raise _invalid(line, f"of kind {kind!r} needs a non-empty string 'text'")
            if not isinstance(evidence, dict) or not all(isinstance(v, str) for v in evidence.values()):
                raise _invalid(line, "needs 'evidence', if any, a table of path to hash")
            if kind == "superseded" and not evidence:
                raise _invalid(line, "of kind 'superseded' needs 'evidence'")
            if not all(_repo_relative(ref.partition("#")[0]) for ref in evidence):
                raise _invalid(line, "has evidence outside the repository")
        elif "text" in entry or "evidence" in entry:
            raise _invalid(line, "has a 'text' or 'evidence', which only a past or superseded 'kind' takes")
        mark = Mark(
            file=entry["file"],
            mode=entry["mode"],
            unit=entry["unit"],
            copies=copies,
            subjects=dict(subjects),
            note=entry["note"],
            by=by,
            approved_by=approved_by,
            partial=extent == "partial",
            pending="review" in entry,
            kind=kind,
            text=unit_text,
            evidence=dict(evidence),
            line=line,
        )
        if mark.key in first_line:
            raise _invalid(
                line, f"has the file, mode and unit of the one at line {first_line[mark.key]}"
            )
        first_line[mark.key] = line
        marks.append(mark)
    return marks


def marks_added(repo_root: Path, diff_range: str) -> tuple[int, int]:
    """`(added, pending)`: how many entries `claims.checked.toml` holds on
    `diff_range`'s new side and not its old one, each entry known by its
    file, mode and unit, and how many of those are pending. A side that
    doesn't parse holds none: the run reports the file. No range git can
    diff, outside a repository included, adds none."""

    old_lines: list[str] = []
    new_lines: list[str] = []
    try:
        diffs = list(iter_diff(repo_root, diff_range, whole_files=True, paths=[CHECKED_FILENAME]))
    except subprocess.CalledProcessError:
        return 0, 0
    for diff in diffs:
        for line in diff.body:
            if isinstance(line, DiffLine):
                if line.sign in " -":
                    old_lines.append(line.text)
                if line.sign in " +":
                    new_lines.append(line.text)
    old = {m.key for m in _parse_or_none("\n".join(old_lines))}
    added = [m for m in _parse_or_none("\n".join(new_lines)) if m.key not in old]
    return len(added), sum(m.pending for m in added)


def _parse_or_none(text: str) -> list[Mark]:
    try:
        return _parse_marks(text)
    except ConfigError:
        return []


def marks_at(repo_root: Path, commit: str) -> list[Mark]:
    """Every mark in `claims.checked.toml` as committed at `commit`, `[]`
    when the commit has no such file. Raises `ConfigError` as
    `load_marks` does."""

    text = blob_text(repo_root, commit, CHECKED_FILENAME)
    return [] if text is None else _parse_marks(text)


def _unit_line(mark: Mark, lines: Sequence[str] | None) -> int:
    """The 1-based first line, in `lines`, of the first copy of `mark`'s
    unit, or 0 when it has none there: an orphan's unit is gone."""

    kind = unit_kind(mark.mode)
    if kind is None or lines is None:
        return 0
    return next((u.start + 1 for u in _units(kind, lines) if u.digest == _in_file(mark.unit)), 0)


def _evidence_at(repo_root: Path, base: str | None) -> Callable[[str], str | None]:
    """What a mark would record for an evidence reference at commit
    `base`, `None` where it isn't there or there is no `base`."""

    def at(ref: str) -> str | None:
        path, _, anchor = ref.partition("#")
        text = None if base is None else blob_text(repo_root, base, path)
        return None if text is None else _evidence_digest(git_lines(text), anchor)

    return at


def _describe(
    marks: Iterable[Mark],
    lines_of: Callable[[str], Sequence[str] | None],
    evidence_at: Callable[[str], str | None],
) -> list[str]:
    """Each of `marks` as a `mark-checked` entry, `file:line mode note`,
    its line looked up in what `lines_of` gives for its file, followed by
    ` (by <by>)` for a mark that names its reader, then its kind in
    brackets. A kind that rests on evidence `evidence_at`, the range's
    base, doesn't give the recorded hash for names that evidence too: it
    was added or changed in the range that wrote the mark."""

    cache: dict[str, Sequence[str] | None] = {}
    described = []
    for mark in marks:
        if mark.file not in cache:
            cache[mark.file] = lines_of(mark.file)
        reader = "" if mark.by is None else f" (by {mark.by})"
        label = mark.kind or "current"
        changed = [ref for ref, h in mark.evidence.items() if evidence_at(ref) != h]
        if changed:
            label += f"; evidence {', '.join(changed)} added or changed in range"
        described.append(
            f"{mark.file}:{_unit_line(mark, cache[mark.file])} {mark.mode} {mark.note}{reader} [{label}]"
        )
    return described


def _first_parent(repo_root: Path, commit: str) -> str | None:
    parents = parent_commits(repo_root, commit)
    return parents[0] if parents else None


def own_pending(repo_root: Path, commit: str) -> list[Mark]:
    """The marks pending at `commit` that its first parent lacks or holds
    otherwise: the ones `commit` itself wrote, not those it inherited
    unchanged. Raises `ConfigError` for a file invalid at either."""

    parents = parent_commits(repo_root, commit)
    before = {m.key: replace(m, line=0) for m in marks_at(repo_root, parents[0])} if parents else {}
    return [
        m for m in marks_at(repo_root, commit) if m.pending and before.get(m.key) != replace(m, line=0)
    ]


def pending_marks(
    repo_root: Path, commit: str | None = None, own: bool = False, base: str | None = None
) -> list[str]:
    """Every pending mark in `claims.checked.toml`, expired and orphaned
    ones included, as `_describe` gives them: from the working tree, or
    with `commit`, from the file and the marked files as committed there,
    and with `own` too, only `own_pending`'s. Evidence is compared with
    `base`, by default `HEAD` for the working tree and `commit`'s first
    parent otherwise. Raises `ConfigError` for an invalid file."""

    if commit is None:
        tree = _Tree(repo_root, {})
        evidence_at = _evidence_at(repo_root, base or head_commit(repo_root))
        return _describe((m for m in load_marks(repo_root) if m.pending), tree.lines, evidence_at)

    def lines_at(rel: str) -> list[str] | None:
        text = blob_text(repo_root, commit, rel)
        return None if text is None else git_lines(text)

    marks = own_pending(repo_root, commit) if own else [m for m in marks_at(repo_root, commit) if m.pending]
    return _describe(marks, lines_at, _evidence_at(repo_root, base or _first_parent(repo_root, commit)))


def approve_marks(
    repo_root: Path,
    commit: str,
    rev: str,
    approver: str | None = None,
    only: Container[tuple[str, str, str]] | None = None,
    base: str | None = None,
) -> tuple[list[str], list[str]]:
    """`(approved, left)`: approve every mark pending in the working tree
    and, with every other key the same, pending at `commit` too, writing
    the file through `write_marks`, with `approver`, when given, as each
    approved mark's `approved_by` and its `by`, the reader, left as it
    is (ADR 0018); describe each approved mark, and each left
    pending with why, naming `commit` as `rev`. With `only`, a mark whose
    key it lacks is neither approved nor described. Evidence is compared
    with `base`, by default `commit`'s first parent. Raises `ConfigError`
    for a file invalid at either side, writing nothing."""

    reviewed = {m.key: replace(m, line=0) for m in marks_at(repo_root, commit)}
    approving: list[Mark] = []
    left: list[tuple[Mark, str]] = []
    for mark in load_marks(repo_root):
        if not mark.pending or (only is not None and mark.key not in only):
            continue
        seen = reviewed.get(mark.key)
        if seen is None:
            left.append((mark, f"not in {rev}"))
        elif seen != replace(mark, line=0):
            left.append((mark, f"changed since {rev}"))
        else:
            approved_by = mark.approved_by if approver is None else approver
            approving.append(replace(mark, pending=False, approved_by=approved_by))
    if approving:
        write_marks(repo_root, approving)
    lines_of = _Tree(repo_root, {}).lines
    evidence_at = _evidence_at(repo_root, base or _first_parent(repo_root, commit))
    return (
        _describe(approving, lines_of, evidence_at),
        [
            f"{entry}: {why}"
            for entry, (_, why) in zip(_describe((m for m, _ in left), lines_of, evidence_at), left)
        ],
    )


def _current(tree: _Tree, mark: Mark, rel: str, unit: _Unit) -> bool:
    """Whether everything `mark` was read against is as it was: for a
    `SETTLED` kind, its unit's text and its evidence; otherwise, its
    subjects."""

    if mark.kind in SETTLED:
        return _words_digest(unit.body) == mark.text and all(
            tree.evidence_hash(ref) == h for ref, h in mark.evidence.items()
        )
    if not all(tree.subject_holds(s, h) for s, h in mark.subjects.items() if tree.counts(s)):
        return False
    return tree.subjects(rel, unit).keys() <= mark.subjects.keys()


def apply_marks(
    repo_root: Path, findings: Sequence[Finding], config: Mapping[str, object]
) -> tuple[list[Finding], list[Finding], list[Finding], list[Finding]]:
    """`(shown, quieted, partly, pending)`: `findings` with every one a
    current mark keeps quiet moved to `quieted`, and an orphan finding
    added to `shown` for each mark whose unit is gone from its file.
    `partly` is the part of `quieted` a partial mark keeps quiet, and
    `pending` the part a pending one does. Raises `ConfigError` for an
    invalid `claims.checked.toml`."""

    marks = load_marks(repo_root)
    if not marks:
        return list(findings), [], [], []
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
    partly: list[Finding] = []
    pending: list[Finding] = []
    for key, group in groups.items():
        mark = by_key[key]
        if not _current(tree, mark, mark.file, units[key]):
            continue
        kind = unit_kind(mark.mode)
        assert kind is not None
        # The file's copies beyond the mark's are unread, and which of the
        # reported ones they are can't be told, so that many stay shown.
        held = tree.copies(mark.file, kind)[_in_file(mark.unit)]
        kept = group[: max(0, len(group) - (held - mark.copies))]
        quiet.extend(kept)
        if mark.partial:
            partly.extend(kept)
        if mark.pending:
            pending.extend(kept)

    quieted = {id(f) for f in quiet}
    shown = [f for f in findings if id(f) not in quieted]
    shown.extend(_orphans(tree, marks))
    return shown, quiet, partly, pending


def _orphan_problem(tree: _Tree, mark: Mark) -> str | None:
    """Why `mark` is an orphan, or `None` when it isn't: the one rule both
    the orphan finding and `orphaned_marks` read."""

    kind = unit_kind(mark.mode)
    if kind is None:
        return f"is for {mark.mode}, which can't be marked"
    if not tree.copies(mark.file, kind)[_in_file(mark.unit)]:
        return f"is for a {kind} no longer in {mark.file}"
    return None


def _orphans(tree: _Tree, marks: Iterable[Mark]) -> list[Finding]:
    found = []
    for mark in marks:
        problem = _orphan_problem(tree, mark)
        if problem is None:
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


def retractions_held(repo_root: Path, mode: str) -> dict[str, set[str]]:
    """`{file: {message hash}}`, one per mark of `mode`, a `LINE` mode,
    committed at `HEAD` whose line is no longer in its file in the working
    tree: a retraction an earlier commit made, read before the change
    being made reworded the line that still held it.

    Read at `HEAD`, not from the working tree, so pruning the orphan the
    rewording leaves doesn't erase the one record of the retraction. A
    sidecar at `HEAD` that doesn't parse holds none: the working tree's is
    what a run reports as invalid."""

    try:
        marks = marks_at(repo_root, "HEAD")
    except ConfigError:
        return {}
    # Only line hashes are read, never a subject, so no config is needed.
    tree = _Tree(repo_root, {})
    held: dict[str, set[str]] = {}
    for mark in marks:
        line, _, message = mark.unit.partition("-")
        if mark.mode == mode and message and not tree.copies(mark.file, LINE)[line]:
            held.setdefault(mark.file, set()).add(message)
    return held


class ExpiredUnit(NamedTuple):
    """One copy, in the working tree, of a unit whose mark a range expired."""

    file: str
    mode: str
    start: int  # 1-based, inclusive
    end: int  # 1-based, inclusive


def expired_units(repo_root: Path, diff_range: str, check: str) -> list[ExpiredUnit]:
    """Each copy in the working tree of the unit of every mark on `check`'s
    findings that `diff_range` expired: committed at the range's old side,
    current there, and not current in the working tree (#263).

    A check scoped to what a range added raises nothing for a unit the
    range left alone, so without this a change to a mark's subject expires
    it with no run of its own showing the finding. A mark already expired
    at the old side is left out: its expiry was an earlier change's to
    raise. Marks are read at the old side, so one the range rewrites or
    removes is still found; a sidecar there that doesn't parse holds none,
    the working tree's being what a run reports as invalid."""

    base = range_base(repo_root, diff_range)
    if base is None:
        return []
    try:
        marks = [m for m in marks_at(repo_root, base) if markable_check(m.mode) == check]
    except ConfigError:
        return []
    if not marks:
        return []
    try:
        config: Mapping[str, object] = load_config(repo_root)
    except ConfigError:
        # The run reports the bad `claims.toml`; read with defaults.
        config = {}
    before, after = _Tree(repo_root, config, base), _Tree(repo_root, config)
    kind = UNITS[check]
    expired: list[ExpiredUnit] = []
    for mark in marks:
        digest = _in_file(mark.unit)
        old = next((u for u in before.units(mark.file, kind) or [] if u.digest == digest), None)
        if old is None or not _current(before, mark, mark.file, old):
            continue
        now = [u for u in after.units(mark.file, kind) or [] if u.digest == digest]
        if now and not _current(after, mark, mark.file, now[0]):
            expired.extend(ExpiredUnit(mark.file, mark.mode, u.start + 1, u.end + 1) for u in now)
    return expired


def expired_lines(repo_root: Path, diff_range: str, check: str) -> dict[str, set[int]]:
    """`{file: {0-based line}}`: every line `expired_units` covers, for a
    check whose units are found by line whatever their mode."""

    lines: dict[str, set[int]] = {}
    for unit in expired_units(repo_root, diff_range, check):
        lines.setdefault(unit.file, set()).update(range(unit.start - 1, unit.end))
    return lines


def orphaned_marks(repo_root: Path, config: Mapping[str, object]) -> list[Mark]:
    """Every mark in `claims.checked.toml` a run reports as an orphan.
    Raises `ConfigError` for an invalid file."""

    tree = _Tree(repo_root, config)
    return [mark for mark in load_marks(repo_root) if _orphan_problem(tree, mark) is not None]


ENTRY_RE = re.compile(r"^(?P<file>.+?):(?P<line>\d+)\s+(?P<mode>\S+)(?:\s+(?P<note>.*))?$")


def new_marks(
    repo_root: Path,
    findings: Sequence[Finding],
    config: Mapping[str, object],
    entries: Iterable[str],
    by: str | None,
    partial: bool = False,
    pending: bool = False,
    claim_kind: str | None = None,
    evidence: Sequence[str] = (),
) -> tuple[list[Mark], list[str]]:
    """`(marks, problems)`: a mark for each of `entries`, one
    `<file>:<line> <mode> <note>` per item, looked up among `findings`,
    and a message naming each entry that can't be marked. Blank entries
    are skipped. With `partial`, each mark records a partial reading, and
    an entry whose mode has no section or doc comment to read part of, or
    whose key a current full mark holds, can't be marked. With `pending`,
    each mark awaits a person's review. Each mark records `claim_kind`, and for
    a `SETTLED` one its unit's text and the hash of each of `evidence`,
    one that isn't there being a problem of its own."""

    tree = _Tree(repo_root, config)
    evidence_hashes = {ref: tree.evidence_hash(ref) for ref in evidence}
    missing = [ref for ref, h in evidence_hashes.items() if h is None]
    if missing:
        return [], [f"--evidence {ref}: no such file or section" for ref in missing]
    full_marks = {m.key: m for m in load_marks(repo_root) if not m.partial} if partial else {}
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
        elif partial and unit_kind(mode) not in (HEADING, DOC_COMMENT):
            # A sentence or a line is read whole or not at all.
            problems.append(f"{entry}: {mode} findings can't be marked partial")
        elif not matching:
            problems.append(f"{entry}: no advisory finding at {file}:{line} ({mode})")
        elif not note:
            problems.append(f"{entry}: needs a note saying what was verified")
        else:
            # Every finding of `mode` at the citation: two sentences that
            # share a line print at one citation, and the entry names both.
            kind = unit_kind(mode)
            assert kind is not None
            for finding in matching:
                found = tree.unit_of(finding)
                if found is None:
                    problems.append(f"{entry}: the finding's line is in no {kind}")
                    break
                unit, digest = found
                full_mark = full_marks.get((file, mode, digest))
                if full_mark is not None and _current(tree, full_mark, file, unit):
                    problems.append(f"{entry}: a partial reading can't replace a current full one")
                    break
                marks.append(
                    Mark(
                        file=file,
                        mode=mode,
                        unit=digest,
                        copies=tree.copies(file, kind)[_in_file(digest)],
                        subjects=dict(sorted(tree.subjects(file, unit).items())),
                        note=note,
                        by=by,
                        partial=partial,
                        pending=pending,
                        kind=claim_kind,
                        text=_words_digest(unit.body) if claim_kind in SETTLED else None,
                        evidence={ref: h for ref, h in evidence_hashes.items() if h is not None},
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
    if mark.approved_by is not None:
        lines.append(f"approved_by = {_toml_string(mark.approved_by)}")
    if mark.partial:
        lines.append('extent = "partial"')
    if mark.pending:
        lines.append('review = "pending"')
    if mark.kind is not None:
        lines.append(f"kind = {_toml_string(mark.kind)}")
    if mark.text is not None:
        lines.append(f"text = {_toml_string(mark.text)}")
    if mark.evidence:
        evidence = ", ".join(f"{_toml_string(r)} = {_toml_string(h)}" for r, h in mark.evidence.items())
        lines.append(f"evidence = {{ {evidence} }}")
    subjects = ", ".join(f"{_toml_string(s)} = {_toml_string(h)}" for s, h in mark.subjects.items())
    lines.append(f"subjects = {{ {subjects} }}" if subjects else "subjects = {}")
    return "\n".join(lines) + "\n"


def write_marks(repo_root: Path, marks: Sequence[Mark], pruned: Iterable[Mark] = ()) -> None:
    """Add `marks` to `claims.checked.toml`, each replacing an existing
    entry with its key, drop each entry `pruned` has the key of, and write
    every entry sorted by key, so branches marking different findings edit
    different places in the file. Every other entry's text, comments
    included, is kept as written; a comment directly above an entry moves
    with it."""

    load_marks(repo_root)  # Refuses a symlink or an invalid file before writing.
    write_marks_file(repo_root / CHECKED_FILENAME, marks, pruned)


def write_marks_file(path: Path, marks: Sequence[Mark], pruned: Iterable[Mark] = ()) -> None:
    """`write_marks` on the file at `path`, which need not be the one in a
    working tree: the fold's merge driver writes git's temporary copy.
    Raises `ConfigError` for a file that doesn't parse."""

    # Read as `load_marks` reads it, so each entry is numbered the same.
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    existing = _parse_marks(text)
    latest = {mark.key: mark for mark in marks}
    pruned_keys = {mark.key for mark in pruned}

    def is_comment(line: str) -> bool:
        return line.lstrip().startswith("#")

    def comments_above(region: list[str]) -> int:
        """Where the comments directly above the end of `region` start."""
        i = len(region)
        while i and is_comment(region[i - 1]):
            i -= 1
        return i

    # Numbered as `load_marks` numbers each entry's `line`.
    lines = [line + "\n" for line in git_lines(text)]
    starts = [m.line - 1 for m in existing]
    # Each entry as `(mark, gap, lead, body)`: the blank lines above it
    # (`None` when it has none of its own, as the first entry hasn't),
    # written above it wherever it lands except first, where none are;
    # then the rest of what lies between it and the entry before; then its
    # own lines. All three move with it, so a sorted file is rewritten
    # byte for byte. A comment closing an entry's lines sits above the
    # next one, so is the next one's.
    entries: list[tuple[Mark, str | None, str, str]] = []
    head = ""
    end_of_last = 0
    for mark, start, end in zip(existing, starts, starts[1:] + [len(lines)]):
        tail = end
        while tail > start + 1 and (not lines[tail - 1].strip() or is_comment(lines[tail - 1])):
            tail -= 1
        region = lines[end_of_last:start]
        if entries:
            blank = 0
            while blank < len(region) and not region[blank].strip():
                blank += 1
            gap, lead = "".join(region[:blank]), "".join(region[blank:])
        else:
            # Above the first entry only the comments directly above it are
            # its own; the rest heads the file, and stays there.
            split = comments_above(region)
            head, gap, lead = "".join(region[:split]), None, "".join(region[split:])
        entries.append((mark, gap, lead, "".join(lines[start:tail])))
        end_of_last = tail
    foot = "".join(lines[end_of_last:])
    if not entries and foot.strip():
        # A file of only comments heads the file, above the entries added.
        head, foot = foot.rstrip("\n") + "\n\n", ""

    kept: list[tuple[tuple[str, str, str], str | None, str, str]] = []
    # What a pruned entry leaves to the next one kept: its gap, and any
    # comments above it that aren't directly above it. Those directly above
    # it are about it, and go with it.
    left: tuple[str | None, str] | None = None
    for mark, gap, lead, body in entries:
        if left is not None:
            gap, lead = left[0], left[1] + lead
            left = None
        if mark.key in pruned_keys and mark.key not in latest:
            region = lead.splitlines(keepends=True)
            left = (gap, "".join(region[: comments_above(region)]))
            continue
        if mark.key in latest:
            body = _render(latest.pop(mark.key))
        kept.append((mark.key, gap, lead, body))
    if left is not None:
        foot = left[1] + foot
    kept.extend((mark.key, None, "", _render(mark)) for mark in latest.values())
    kept.sort(key=lambda entry: entry[0])

    out = [head]
    for slot, (_, gap, lead, body) in enumerate(kept):
        if slot:
            out.append("\n" if gap is None else gap)
        out.append(lead + body)
    out.append(foot)
    path.write_text("".join(out).rstrip("\n") + "\n", encoding="utf-8")
