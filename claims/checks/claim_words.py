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

"""The `claim-words` check.

Diff-scoped sweep over added lines in **designated record-like files**
(`files`, a config list of glob patterns — nothing is swept unless a project
opts a file in) for totalising words ("every", "only", "never"), spelled-out
or digit counts, and words asserting something "elsewhere" only when they
sit beside a backticked citation. Registered as an **advisory** check — see
spec.md's check inventory — so it never fails the run: it cannot tell you
whether a claim is true, only that a sentence is making one.

Ported from Project B's `tools/claim-words.py` (same author, relicensed for
this consolidation), narrowed from that tool's per-paragraph, per-language
(Python/Swift/Shell/Markdown comment) sweep to whole *sentences* within
*designated* files only — spec.md user story 17. Two source-tool choices
don't carry over:

- Scope is opt-in (`files` config), not a blanket sweep with a `CHANGELOG.md`
  exemption — the ticket's "specifically-designated record-like files" is
  the opposite default from the source tool's "everywhere, minus one path".
- The count word list is uncapped (any run of spelled-out number words, not
  a fixed `two`..`twelve` list) — a count's *size* isn't what makes it a
  claim.

**House style for retiring a sentence**, established here since no prior
check in this codebase's history defines one: a sentence a record-like file
quotes to explain what was wrong with it is exempt when it is a Markdown
blockquote (`>` ...), wrapped whole in `*italics*`/`_italics_`, or opens with
the fixed lead-in phrase "Previously said:". Any one of the three suppresses
that sentence; nothing else does — an unmarked quotation of a retired claim
still fires, on the theory that an unmarked quotation is indistinguishable
from the claim still being made.

**A count that measures the world, not the tree, is not this check's
business.** "the file grew to twelve megabytes" and "the API waited three
seconds" describe something outside the diff that a count of tree elements
("the only three checks", "seven of these") does not — flagged only when
the counted noun isn't a known unit of measurement (`UNIT_WORDS`).

Three modes, one per matching strategy — `runner.Finding`'s own contract —
so a consumer can filter or count by which kind of claim fired without
parsing the message text.
"""

from __future__ import annotations

import fnmatch
import re
import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path

from ..runner import Finding, register_check

NAME = "claim-words"

MODE_TOTALISING = "claim-words-totalising"
MODE_COUNTS = "claim-words-counts"
MODE_ABOUT_ELSEWHERE = "claim-words-about-elsewhere"

# Asserts over a set; wrong the moment one member disagrees. Reported
# wherever it appears in an in-scope sentence.
STRONG = [
    "every", "only", "never", "always", "exactly", "none of", "the one",
    "unchanged", "cannot", "can never", "no other", "nothing else",
    "each of", "all three", "all four",
]
# How a sentence reaches for code/content it is not itself showing. On its
# own this is ordinary English; beside a backticked citation it is a claim
# about that citation.
ELSEWHERE = [
    "would", "otherwise", "without", "instead of", "rather than",
    "which means", "which is why",
]

_UNITS = [
    "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen",
]
_TENS = [
    "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty",
    "ninety",
]
_SCALES = ["hundred", "thousand", "million", "billion", "trillion"]
_NUMBER_TOKEN = "(?:" + "|".join(_UNITS + _TENS + _SCALES) + ")"

# A number that measures the world rather than the tree — see module
# docstring. Not exhaustive, just the common units a spelled-out or digit
# count is likely to precede.
UNIT_WORDS = {
    "byte", "bytes", "kb", "mb", "gb", "tb",
    "kilobyte", "kilobytes", "megabyte", "megabytes",
    "gigabyte", "gigabytes", "terabyte", "terabytes",
    "second", "seconds", "ms", "millisecond", "milliseconds",
    "minute", "minutes", "hour", "hours",
    "day", "days", "week", "weeks", "month", "months", "year", "years",
    "decade", "decades", "century", "centuries",
    "percent", "%", "dollar", "dollars", "degree", "degrees",
}

# `(?<![\w-])`/`(?![\w-])` rather than `\b`: a hyphen is a non-word
# character, so `\b` alone still matches "always" inside a hyphenated
# identifier like `--always-verify` — the boundary needs to reject a
# neighbouring hyphen too, not just a neighbouring letter.
STRONG_RE = re.compile(
    r"(?<![\w-])(" + "|".join(w.replace(" ", r"\s+") for w in STRONG) + r")(?![\w-])",
    re.IGNORECASE,
)
ELSEWHERE_RE = re.compile(
    r"(?<![\w-])(" + "|".join(w.replace(" ", r"\s+") for w in ELSEWHERE) + r")(?![\w-])",
    re.IGNORECASE,
)
# Any run of spelled-out number words (joined by space, hyphen, or "and"),
# or a bare digit run, immediately before the noun it counts.
COUNT_RE = re.compile(
    r"\b(?:\d+|"
    + _NUMBER_TOKEN
    + r"(?:[-\s]+(?:and[-\s]+)?"
    + _NUMBER_TOKEN
    + r")*)\s+(?P<noun>[\w%]+)",
    re.IGNORECASE,
)

BACKTICKED = re.compile(r"`([^`]+)`")

# A terminator may be immediately followed by closing markup (the `*` of an
# `*italicised*` sentence, a closing quote or bracket) before the boundary —
# without this, "*claim.*" splits before the closing `*`, and the retired-
# quote suppression's italics check never sees a whole-wrapped sentence.
SENTENCE_RE = re.compile(r"\S.*?[.!?][*_'\")\]]*(?=\s|$)|\S.+$", re.DOTALL)
ITALIC_RE = re.compile(r"^(\*|_)(?!\1).+\1$", re.DOTALL)
# A bare `>` used as a threshold marker ("> 5 failures") isn't a Markdown
# blockquote — CommonMark's own marker is `>` followed by whitespace or
# end-of-line, so that's what's required here too.
BLOCKQUOTE_RE = re.compile(r"^>(\s|$)")
LEAD_IN = "previously said:"


def _added_lines(repo_root: Path, diff_range: str) -> dict[str, set[int]]:
    """`{path: {added line numbers, in the new file}}` for `diff_range`."""

    diff = subprocess.run(
        ["git", "diff", "--unified=0", "--no-color", diff_range or "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    added: dict[str, set[int]] = {}
    path = None
    line_no = 0
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
        elif line.startswith("@@"):
            header = re.search(r"\+(\d+)", line)
            line_no = int(header.group(1)) if header else 0
        elif line.startswith("+") and not line.startswith("+++"):
            if path:
                added.setdefault(path, set()).add(line_no)
            line_no += 1
    return added


def _files(config: Mapping[str, object]) -> Sequence[str]:
    patterns = config.get("files", [])
    # A project meaning to designate one file (`files = "record.md"`) is a
    # one-character typo away from `["record.md"]`; treated as a bare list
    # of characters instead, `fnmatch` against `"*"` and similar chars would
    # turn "opt in one file" into "sweep everything" without any error.
    if isinstance(patterns, str):
        return [patterns]
    return list(patterns)  # type: ignore[arg-type]


def _designated(path: str, patterns: Sequence[str]) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


def _is_count_claim(sentence: str) -> bool:
    return any(
        match.group("noun").lower().strip(".,;:") not in UNIT_WORDS
        for match in COUNT_RE.finditer(sentence)
    )


def _is_retired_quote(sentence: str, lines: Sequence[str], start: int, end: int) -> bool:
    """Whether the house style for retiring a sentence exempts it.

    `start`/`end` are 0-based, inclusive line indices the sentence spans.
    """

    if any(BLOCKQUOTE_RE.match(lines[i].lstrip()) for i in range(start, end + 1)):
        return True
    if ITALIC_RE.match(sentence.strip()):
        return True
    return sentence.strip().lower().startswith(LEAD_IN)


def _classify(sentence: str) -> list[str]:
    """Every mode this sentence matches — see the `MODE_*` constants."""

    modes = []
    if STRONG_RE.search(sentence):
        modes.append(MODE_TOTALISING)
    if _is_count_claim(sentence):
        modes.append(MODE_COUNTS)
    if BACKTICKED.search(sentence) and ELSEWHERE_RE.search(sentence):
        modes.append(MODE_ABOUT_ELSEWHERE)
    return modes


def _sentences_from(text: str) -> list[tuple[str, int, int]]:
    """`(sentence, start_line, end_line)`, 0-based inclusive line indices.

    Paragraphs (blank-line separated) are joined before splitting into
    sentences, so a sentence soft-wrapped across lines is read whole.
    """

    lines = text.splitlines()
    results: list[tuple[str, int, int]] = []
    para_start = 0
    for i in range(len(lines) + 1):
        at_end = i == len(lines)
        if at_end or not lines[i].strip():
            if i > para_start:
                para_text = "\n".join(lines[para_start:i])
                for match in SENTENCE_RE.finditer(para_text):
                    before = para_text[: match.start()]
                    start = para_start + before.count("\n")
                    end = para_start + para_text[: match.end()].count("\n")
                    sentence = " ".join(match.group(0).split())
                    if sentence:
                        results.append((sentence, start, end))
            para_start = i + 1
    return results


def check(
    repo_root: Path, diff_range: str, config: Mapping[str, object]
) -> list[Finding]:
    patterns = _files(config)
    if not patterns:
        return []

    added = _added_lines(repo_root, diff_range)
    findings: list[Finding] = []

    for path, added_line_numbers in sorted(added.items()):
        if not _designated(path, patterns):
            continue
        try:
            text = (repo_root / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines = text.splitlines()
        zero_based_added = {n - 1 for n in added_line_numbers}

        for sentence, start, end in _sentences_from(text):
            if zero_based_added.isdisjoint(range(start, end + 1)):
                continue
            if _is_retired_quote(sentence, lines, start, end):
                continue
            for mode in _classify(sentence):
                findings.append(
                    Finding(
                        file=path,
                        line=start + 1,
                        message=f"[{mode}] {sentence}",
                        mode=mode,
                        gate=False,
                    )
                )

    return findings


register_check(NAME, check)
