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

"""The `restatement` check: prose a diff retracted that is still asserted,
verbatim, somewhere else in the tree. `docs/checks/restatement.md` is the
account of the two modes, the word reduction, which keys it takes and
what it misses; this docstring is why the code is shaped the way it is.

Advisory (spec.md's check inventory): a hit is a place to look, not a
verdict, since the same fact can legitimately appear twice on purpose (a
summary and the page it summarises).

Merged from two source tools that solved this independently, kept as two
reported modes on one `Finding.mode` rather than two maintained checks:

- `restatement-ngram`, ported from `ratect`'s `echoed-claims.py`
  (Apache-2.0 prior art, same author). `NGRAM_WORDS` (6) is empirically
  tuned, not a guess — 8 missed a real case ("for every network *it*
  creates" against "...*Ratect* creates") that 6 caught.
- `restatement-whole-line` (`MIN_LINE_WORDS`, 10 words), this
  consolidation's own port of the private Swift project's
  `split-claims.py` (same author) — a Swift tool, so re-expressed here in
  Python rather than copied.

**Verbatim-only by design, not a solved paraphrase detector.** A
private-project evaluation of adopting the n-gram tool independently
confirmed this: its real restatement failures that session were
paraphrase, not verbatim duplication, and the tool "would have caught none
of them." Paraphrase detection is judgement-shaped, not mechanical — out
of scope here.

Words/lines the diff also *added* are subtracted before its removed lines
are searched for, because reflowing a paragraph removes and re-adds most
of it, and a thing still said is not a thing retracted.

**A line the diff added is never a survivor.** Subtraction is per file,
so text moved from one file to another counts as retracted from the
first, and the sweep would otherwise find its new copy and report the
move as a survivor of itself. Whoever wrote the line in this change meant
it. Only a run lying wholly on added lines is skipped: one that starts
on an untouched line may be a real survivor wrapping onto a line the
diff edited, and a miss stays invisible where a false positive does not
(`CLAUDE.md`'s "recall over precision"). The added lines are dropped before the duplication threshold counts files, so a moved copy neither pushes a real survivor over the threshold
nor stands in for one.

`extensions` is *added* to the default union of both source tools'
original coverage rather than replacing it — e.g. `ratect` would add
`.rs`, covered by neither source tool.

**Source files contribute comments only.** Read whole-line, a source
file's code is prose to this check, and a deleted line of code reported
its identical twin elsewhere as a retraction: 769 of 1,055 findings over
one `ratect` release were Rust code lines. `COMMENT_SYNTAX` is a table of
plain rows rather than code per language, so a later config key could
add one. The diff is taken with whole files as context because a line
inside a block comment or docstring can only be classified from where
its file opened that comment, which the hunk alone may not show.

**Duplication threshold.** The default of **1** is chosen to land exactly
on this check's own documented tolerance above: "twice on purpose" is 2
total copies (the edited file plus one survivor), so threshold 1 keeps
that case reported and only suppresses once a third copy existed. Text
duplicated across many files by design (a shared license header, a
generated-file banner) is the common case this exists to filter: removing
one copy of many is not evidence a fact drifted, the other copies were
never at risk because this one existed and aren't now because it's gone.
The count comes for free from the existing survivor-sweep (how many
distinct files, besides the one the diff touched, still hold the exact
matched text) — no extra git-history walk.

`exclude` has the same shape and matching as `executable-claims`' and
`check-links`' own. An excluded file is dropped from the survivor sweep
entirely, not just from candidate extraction, so it neither counts toward
nor is reported as another file's duplication.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import NamedTuple

from ..config import exclude_patterns, numeric_config, path_matches, string_list_config
from ..git import DiffLine, added_lines_by_file, iter_diff, tracked_files
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


class CommentSyntax(NamedTuple):
    """How one source language marks prose. Plain data, so a later config
    key could add a row of the same shape without code per language."""

    line: tuple[str, ...]
    block: tuple[str, str] | None
    nested: bool
    docstrings: bool


C_LIKE = CommentSyntax(line=("//",), block=("/*", "*/"), nested=True, docstrings=False)
HASH = CommentSyntax(line=("#",), block=None, nested=False, docstrings=False)

# A file with one of these extensions contributes only its comment text;
# every other in-scope extension is read whole-line, code and all.
COMMENT_SYNTAX: dict[str, CommentSyntax] = {
    ".py": HASH._replace(docstrings=True),
    ".sh": HASH,
    ".rs": C_LIKE,
    ".swift": C_LIKE,
}

TRIPLE_QUOTE = r"(?P<prefix>[A-Za-z]*)(?P<quote>\"\"\"|''')"
# Listed after `TRIPLE_QUOTE`, so at a `"""` the triple quote wins.
ONE_LINE_STRING = r"""(?P<string>"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*')"""
DOCSTRING_PREFIXES = ("", "r", "u", "b")
TRIPLE_QUOTE_CLOSE = {q: re.compile(rf"(?<!\\){q}") for q in ('"""', "'''")}


def _code_opener(syntax: CommentSyntax) -> re.Pattern[str]:
    """The earliest thing in a stretch of code that starts comment text or
    a string worth following. A comment opener counts only at the start of
    the line or after whitespace, so `${x#y}`, `$#` and `http://` stay
    code. Strings are recognised only in a language with docstrings, and
    only so triple quotes inside a one-line string aren't taken for a
    string that opens."""

    starts = [*syntax.line, *(syntax.block[:1] if syntax.block else ())]
    alternatives = [rf"(?<!\S)(?P<comment>{'|'.join(map(re.escape, starts))})"]
    if syntax.docstrings:
        alternatives += [TRIPLE_QUOTE, ONE_LINE_STRING]
    return re.compile("|".join(alternatives))


def _comment_lines(syntax: CommentSyntax, lines: Sequence[str]) -> list[str]:
    """Each line's comment text, `""` for a line of code only.

    Read over the whole file, never line by line, because a line inside a
    block comment or docstring can't be recognised on its own. Block
    comments track nesting where the language nests them, so an inner `*/`
    doesn't end the outer comment. In Python, a triple-quoted string is a
    docstring when its opening quotes begin a line after indentation; any
    other one is followed to its close only so its lines aren't read as
    code that might hold a `#`.
    """

    opener = _code_opener(syntax)
    depth = 0
    quote: str | None = None
    docstring = False
    comments: list[str] = []
    for number, line in enumerate(lines, start=1):
        parts: list[str] = []
        # A shebang is an interpreter path, not a comment.
        i = len(line) if number == 1 and line.startswith("#!") else 0
        while i < len(line):
            if depth and syntax.block:
                start, end = syntax.block
                close = line.find(end, i)
                inner = line.find(start, i) if syntax.nested else -1
                if inner != -1 and (close == -1 or inner < close):
                    parts.append(line[i:inner])
                    depth += 1
                    i = inner + len(start)
                elif close == -1:
                    parts.append(line[i:])
                    break
                else:
                    parts.append(line[i:close])
                    depth -= 1
                    i = close + len(end)
            elif quote:
                found = TRIPLE_QUOTE_CLOSE[quote].search(line, i)
                close = found.start() if found else -1
                if docstring:
                    parts.append(line[i:] if close == -1 else line[i:close])
                if close == -1:
                    break
                i = close + len(quote)
                quote = None
            else:
                match = opener.search(line, i)
                if not match:
                    break
                comment = match.group("comment")
                if comment in syntax.line:
                    parts.append(line[match.end() :])
                    break
                if comment:
                    depth = 1
                elif match.group("quote"):
                    quote = match.group("quote")
                    docstring = (
                        not line[: match.start()].strip()
                        and match.group("prefix").lower() in DOCSTRING_PREFIXES
                    )
                i = match.end()
        comments.append(" ".join(parts))
    return comments


def _prose_lines(path: str, lines: Sequence[str]) -> list[str]:
    """`lines` as the prose this check reads: comment text only for an
    extension in `COMMENT_SYNTAX`, each line whole for any other."""

    syntax = COMMENT_SYNTAX.get(Path(path).suffix)
    return _comment_lines(syntax, lines) if syntax else list(lines)


def _normalise(line: str) -> list[str]:
    """One line as the words it asserts, in order."""

    line = LINK_RE.sub(r"\1", line)
    line = MARKUP_RE.sub(" ", line)
    return NON_WORD_RE.sub(" ", line.lower()).split()


def _runs(words: Sequence[str], length: int) -> set[str]:
    """Every overlapping run of `length` words, as joined strings."""

    return {" ".join(words[i : i + length]) for i in range(0, len(words) - length + 1)}


def _extensions(config: Mapping[str, object]) -> set[str]:
    # `string_list_config`, not a raw `set(extra)`: the latter iterates a
    # bare string's own *characters* (`extensions = ".rs"` silently became
    # `{'.', 'r', 's'}`, matching nearly every path in the tree) instead of
    # treating it as the one-element list every other check's own list
    # config already coerces a bare string into.
    return set(DEFAULT_EXTENSIONS) | set(string_list_config(config, "extensions"))


def _duplication_threshold(config: Mapping[str, object]) -> int:
    """This check's own `duplication_threshold`, from its `claims.toml`
    section — default 1. See the module docstring's "Duplication
    threshold" section for why 1."""

    return int(numeric_config(config, NAME, "duplication_threshold", 1, allow_float=False))


def _in_scope(path: str | None, extensions: set[str], exclude: Sequence[str]) -> bool:
    return (
        path is not None
        and path.endswith(tuple(extensions))
        and not path_matches(path, exclude)
    )


def _diff_by_file(
    repo_root: Path, diff_range: str, extensions: set[str], exclude: Sequence[str]
) -> list[tuple[list[str], list[str]]]:
    """`[(removed, added), ...]`: line text, one pair per file the diff
    touches, each restricted to in-scope lines from that file's own
    side(s) and read as `_prose_lines` reads them, against the file's whole
    old or new version.

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
    for file_diff in iter_diff(repo_root, diff_range, whole_files=True):
        old: list[str] = []
        new: list[str] = []
        removed_at: list[int] = []
        added_at: list[int] = []
        for item in file_diff.body:
            if isinstance(item, DiffLine):
                if item.sign == "-":
                    removed_at.append(len(old))
                elif item.sign == "+":
                    added_at.append(len(new))
                if item.sign != "+":
                    old.append(item.text)
                if item.sign != "-":
                    new.append(item.text)
        removed: list[str] = []
        added: list[str] = []
        if file_diff.src and _in_scope(file_diff.src, extensions, exclude):
            old_prose = _prose_lines(file_diff.src, old)
            removed = [old_prose[at] for at in removed_at]
        if file_diff.dst and _in_scope(file_diff.dst, extensions, exclude):
            new_prose = _prose_lines(file_diff.dst, new)
            added = [new_prose[at] for at in added_at]
        segments.append((removed, added))
    return segments


def _tracked_scoped(
    repo_root: Path, extensions: set[str], exclude: Sequence[str]
) -> list[str]:
    pathspecs = tuple(f"*{ext}" for ext in sorted(extensions))
    return [
        rel
        for rel in tracked_files(repo_root, *pathspecs)
        if not path_matches(rel, exclude)
    ]


def _below_duplication_threshold(
    hits: list[tuple[str, int, str]], threshold: int
) -> list[tuple[str, int, str]]:
    """`hits`, dropping every candidate (grouped by its matched text)
    whose distinct survivor-file count exceeds `threshold`."""

    files_by_text: dict[str, set[str]] = {}
    for file, _, text in hits:
        files_by_text.setdefault(text, set()).add(file)
    return [hit for hit in hits if len(files_by_text[hit[2]]) <= threshold]


def _survivors(
    repo_root: Path,
    tracked: list[str],
    wanted_ngrams: set[str],
    wanted_lines: set[str],
    added: Mapping[str, set[int]],
) -> tuple[list[tuple[str, int, str]], list[tuple[str, int, str]]]:
    """`(ngram_hits, whole_line_hits)`, each `(file, line, text)`.

    One read and one normalization pass per tracked file, shared by both
    modes, rather than sweeping the whole scoped tree twice.

    A line in `added` is never a hit, and neither is a run lying wholly on
    such lines. Skipped while sweeping, not filtered afterwards, so a run
    first met on an added line can still be found on a later untouched
    one.
    """

    ngram_hits: list[tuple[str, int, str]] = []
    whole_line_hits: list[tuple[str, int, str]] = []
    for name in tracked:
        try:
            text = (repo_root / name).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines = _prose_lines(name, text.splitlines())
        added_here = added.get(name, set())
        located = [
            (word, number)
            for number, line in enumerate(lines, start=1)
            for word in _normalise(line)
        ]

        if wanted_ngrams:
            surviving: dict[str, int] = {}
            for i in range(0, len(located) - NGRAM_WORDS + 1):
                window = located[i : i + NGRAM_WORDS]
                if all(number in added_here for _, number in window):
                    continue
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
                if number not in added_here and normalised in wanted_lines:
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
    exclude = exclude_patterns(config)
    threshold = _duplication_threshold(config)
    segments = _diff_by_file(repo_root, diff_range, extensions, exclude)

    wanted_ngrams: set[str] = set()
    wanted_lines: set[str] = set()
    for removed_lines, added_lines in segments:
        removed_words = [word for line in removed_lines for word in _normalise(line)]
        added_words = [word for line in added_lines for word in _normalise(line)]
        wanted_ngrams |= _runs(removed_words, NGRAM_WORDS) - _runs(added_words, NGRAM_WORDS)
        wanted_lines |= _wanted_whole_lines(removed_lines, added_words)

    if not wanted_ngrams and not wanted_lines:
        return []

    tracked = _tracked_scoped(repo_root, extensions, exclude)
    added = added_lines_by_file(repo_root, diff_range)
    ngram_hits, whole_line_hits = _survivors(
        repo_root, tracked, wanted_ngrams, wanted_lines, added
    )
    ngram_hits = _below_duplication_threshold(ngram_hits, threshold)
    whole_line_hits = _below_duplication_threshold(whole_line_hits, threshold)

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
