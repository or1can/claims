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

"""The `restatement` check.

Finds prose a diff retracted that is still asserted, verbatim, somewhere
else in the tree. Registered as an **advisory** check — see spec.md's check
inventory — so it never fails the run: a hit is a place to look, not a
verdict, since the same fact can legitimately appear twice on purpose (a
summary and the page it summarises).

Merged from two source tools that solved this independently, kept as two
reported modes on one `Finding.mode` rather than two maintained checks:

- `restatement-ngram` — a short run of words (`NGRAM_WORDS`, 6) removed
  from a diff and still found intact elsewhere. Ported from `ratect`'s
  `echoed-claims.py` (Apache-2.0 prior art, same author); the 6-word
  default is empirically tuned, not a guess — 8 missed a real case ("for
  every network *it* creates" against "...*Ratect* creates") that 6 caught.
- `restatement-whole-line` — a whole line (`MIN_LINE_WORDS`, 10 words),
  normalized, removed from a diff and still found intact elsewhere. This
  consolidation's own port of the private Swift project's `split-claims.py`
  (same author) — a Swift tool, so re-expressed here in Python rather than
  copied.

**Verbatim-only by design, not a solved paraphrase detector.** A file that
restates the same fact in different words shares too few consecutive words
(n-gram mode) and won't match line-for-line (whole-line mode) — this check
cannot and does not claim to see that. A private-project evaluation of
adopting the n-gram tool independently confirmed this: its real restatement
failures that session were paraphrase, not verbatim duplication, and the
tool "would have caught none of them." Paraphrase detection is judgement-
shaped, not mechanical — out of scope here.

Both modes read a diff's removed lines only after subtracting words/lines
the diff also *added* — reflowing a paragraph removes and re-adds most of
it, and a thing still said is not a thing retracted.

File-type scope is a config surface (`extensions`, a list of dotted
suffixes), *added* to the default union of both source tools' original
coverage (Markdown, Swift, Python, Shell, YAML) rather than replacing it —
e.g. `ratect` would add `.rs`, covered by neither source tool.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from ..git import DiffLine, iter_diff, tracked_files
from ..runner import Finding, register_check

NAME = "restatement"

MODE_NGRAM = "restatement-ngram"
MODE_WHOLE_LINE = "restatement-whole-line"

NGRAM_WORDS = 6
MIN_LINE_WORDS = 10

DEFAULT_EXTENSIONS = (".md", ".swift", ".py", ".sh", ".yml")

# Inline markup, links and punctuation are dropped before matching, so a
# sentence surviving with different emphasis or a re-pointed link still
# counts as the same claim. Only the words carry the assertion.
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
MARKUP_RE = re.compile(r"[`*_~<>\[\]()#|]")
NON_WORD_RE = re.compile(r"[^a-z0-9]+")


def _normalise(line: str) -> list[str]:
    """One line as the words it asserts, in order."""

    line = LINK_RE.sub(r"\1", line)
    line = MARKUP_RE.sub(" ", line)
    return NON_WORD_RE.sub(" ", line.lower()).split()


def _runs(words: Sequence[str], length: int) -> set[str]:
    """Every overlapping run of `length` words, as joined strings."""

    return {" ".join(words[i : i + length]) for i in range(0, len(words) - length + 1)}


def _extensions(config: Mapping[str, object]) -> set[str]:
    extra = config.get("extensions", [])
    return set(DEFAULT_EXTENSIONS) | set(extra)  # type: ignore[arg-type]


def _in_scope(path: str | None, extensions: set[str]) -> bool:
    return path is not None and path.endswith(tuple(extensions))


def _diff_by_file(
    repo_root: Path, diff_range: str, extensions: set[str]
) -> list[tuple[list[str], list[str]]]:
    """`[(removed, added), ...]` raw line text, one pair per file the diff
    touches, each restricted to in-scope lines from that file's own side(s).

    Kept per file rather than merged into one global removed/added stream:
    an unrelated file's incidental addition in the same diff must not cancel
    a genuine retraction elsewhere, which a global subtraction would allow.
    Each side of a hunk header is still judged separately within a pair, so
    a rename into or out of scope doesn't let one side cancel the other's
    lines either.

    Built on `claims.git.iter_diff`, which already resolves each side's
    path (or `None` for that side's `/dev/null`) unambiguously — see its
    own docstring for why that's not as simple as matching `+++`/`--- `
    line prefixes directly. Scope is computed fresh per `FileDiff`, never
    carried over — a file with no header at all (a pure rename, a binary
    file) is just a `FileDiff` with both paths `None` and an empty body.
    """

    segments: list[tuple[list[str], list[str]]] = []
    for file_diff in iter_diff(repo_root, diff_range):
        from_scope = _in_scope(file_diff.src, extensions)
        to_scope = _in_scope(file_diff.dst, extensions)
        removed: list[str] = []
        added: list[str] = []
        for item in file_diff.body:
            if isinstance(item, DiffLine):
                if item.sign == "-" and from_scope:
                    removed.append(item.text)
                elif item.sign == "+" and to_scope:
                    added.append(item.text)
        segments.append((removed, added))
    return segments


def _tracked_scoped(repo_root: Path, extensions: set[str]) -> list[str]:
    pathspecs = tuple(f"*{ext}" for ext in sorted(extensions))
    return tracked_files(repo_root, *pathspecs)


def _survivors(
    repo_root: Path,
    tracked: list[str],
    wanted_ngrams: set[str],
    wanted_lines: set[str],
) -> tuple[list[tuple[str, int, str]], list[tuple[str, int, str]]]:
    """`(ngram_hits, whole_line_hits)`, each `(file, line, text)`.

    One read and one normalization pass per tracked file, shared by both
    modes, rather than sweeping the whole scoped tree twice.
    """

    ngram_hits: list[tuple[str, int, str]] = []
    whole_line_hits: list[tuple[str, int, str]] = []
    for name in tracked:
        try:
            text = (repo_root / name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines = text.splitlines()
        located = [
            (word, number)
            for number, line in enumerate(lines, start=1)
            for word in _normalise(line)
        ]

        if wanted_ngrams:
            surviving: dict[str, int] = {}
            for i in range(0, len(located) - NGRAM_WORDS + 1):
                window = located[i : i + NGRAM_WORDS]
                surviving.setdefault(" ".join(word for word, _ in window), window[0][1])

            # Overlapping runs of one sentence all match; report each
            # surviving line once, with its longest matching run.
            best: dict[int, str] = {}
            for run in sorted(wanted_ngrams & surviving.keys()):
                line = surviving[run]
                if len(run) > len(best.get(line, "")):
                    best[line] = run
            ngram_hits.extend((name, line, run) for line, run in sorted(best.items()))

        if wanted_lines:
            for number, line in enumerate(lines, start=1):
                normalised = " ".join(_normalise(line))
                if normalised in wanted_lines:
                    whole_line_hits.append((name, number, normalised))

    return ngram_hits, whole_line_hits


def _wanted_whole_lines(removed_lines: Sequence[str], added_words: Sequence[str]) -> set[str]:
    """Removed lines (>= `MIN_LINE_WORDS`) whose exact word sequence doesn't
    also occur, as a contiguous run, in the diff's added words.

    Checked against the added *stream*, not added lines one-for-one — a
    rewrapped paragraph reflows a removed line across new line boundaries,
    and a line still said (just re-wrapped) is not a line retracted.
    """

    wanted = set()
    runs_by_length: dict[int, set[str]] = {}
    for line in removed_lines:
        words = _normalise(line)
        if len(words) < MIN_LINE_WORDS:
            continue
        length = len(words)
        if length not in runs_by_length:
            runs_by_length[length] = _runs(added_words, length)
        joined = " ".join(words)
        if joined not in runs_by_length[length]:
            wanted.add(joined)
    return wanted


def check(
    repo_root: Path, diff_range: str, config: Mapping[str, object]
) -> list[Finding]:
    extensions = _extensions(config)
    segments = _diff_by_file(repo_root, diff_range, extensions)

    wanted_ngrams: set[str] = set()
    wanted_lines: set[str] = set()
    for removed_lines, added_lines in segments:
        removed_words = [word for line in removed_lines for word in _normalise(line)]
        added_words = [word for line in added_lines for word in _normalise(line)]
        wanted_ngrams |= _runs(removed_words, NGRAM_WORDS) - _runs(added_words, NGRAM_WORDS)
        wanted_lines |= _wanted_whole_lines(removed_lines, added_words)

    if not wanted_ngrams and not wanted_lines:
        return []

    tracked = _tracked_scoped(repo_root, extensions)
    ngram_hits, whole_line_hits = _survivors(repo_root, tracked, wanted_ngrams, wanted_lines)

    findings: list[Finding] = [
        Finding(
            file=name,
            line=line,
            message=f"still says: ...{run}...",
            mode=MODE_NGRAM,
            gate=False,
        )
        for name, line, run in ngram_hits
    ]
    findings.extend(
        Finding(
            file=name,
            line=line,
            message=f"still says: {text}",
            mode=MODE_WHOLE_LINE,
            gate=False,
        )
        for name, line, text in whole_line_hits
    )

    findings.sort(key=lambda f: (f.file, f.line, f.mode))
    return findings


register_check(NAME, check)
