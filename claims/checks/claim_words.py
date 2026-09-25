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

"""The `claim-words` check: a sentence a diff added to a designated
file that is shaped like a claim. `docs/checks/claim-words.md`
is the account of the three modes, the word lists, the `files` key and
the retirement markers; this docstring is why the code is shaped the way
it is.

Advisory (spec.md's check inventory): it cannot tell you whether a claim
is true, only that a sentence is making one.

Ported from Project B's `tools/claim-words.py` (same author, relicensed
for this consolidation), narrowed from that tool's per-paragraph,
per-language (Python/Swift/Shell/Markdown comment) sweep to whole
*sentences* within *designated* files only — spec.md user story 17. Two
source-tool choices don't carry over:

- Scope is opt-in (`files` config), not a blanket sweep with a
  `CHANGELOG.md` exemption — designating files is the opposite default
  from the source tool's "everywhere, minus one path".
- The count word list is uncapped (any run of spelled-out number words,
  not a fixed `two`..`twelve` list) — a count's *size* isn't what makes a
  claim.

**House style for retiring a sentence** — blockquote, whole-sentence
italics, or the lead-in "Previously said:" — is established here, since
no prior check in this codebase's history defines one. An unmarked
quotation of a retired claim still fires, on the theory that an unmarked
quotation is indistinguishable from the claim still being made. ADR 0003
is why the set is this check's own rather than a shared one.

`UNIT_WORDS` exists because **a count that measures the world, not the
tree, is not this check's business.** "the file grew to twelve megabytes"
and "the API waited three seconds" describe something outside the diff
that a count of tree elements ("the only three checks", "seven of these")
does not.

Three modes, one per matching strategy — `runner.Finding`'s own contract —
so a consumer can filter or count by which kind of claim fired without
parsing the message text.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from ..config import path_matches, string_list_config
from ..git import added_lines_by_file
from ..markdown import CODE_SPAN_RE, ITALIC_RE, RETIRED_LEAD_IN, sentences_from
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

# A bare `>` used as a threshold marker ("> 5 failures") isn't a Markdown
# blockquote — CommonMark's own marker is `>` followed by whitespace or
# end-of-line, so that's what's required here too.
BLOCKQUOTE_RE = re.compile(r"^>(\s|$)")


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
    return sentence.strip().lower().startswith(RETIRED_LEAD_IN)


def _classify(sentence: str) -> list[str]:
    """Every mode this sentence matches — see the `MODE_*` constants."""

    modes = []
    if STRONG_RE.search(sentence):
        modes.append(MODE_TOTALISING)
    if _is_count_claim(sentence):
        modes.append(MODE_COUNTS)
    if CODE_SPAN_RE.search(sentence) and ELSEWHERE_RE.search(sentence):
        modes.append(MODE_ABOUT_ELSEWHERE)
    return modes


def check(
    repo_root: Path, diff_range: str, config: Mapping[str, object]
) -> list[Finding]:
    patterns = string_list_config(config, "files")
    if not patterns:
        return []

    added = added_lines_by_file(repo_root, diff_range)
    findings: list[Finding] = []

    for path, added_line_numbers in sorted(added.items()):
        if not path_matches(path, patterns):
            continue
        try:
            text = (repo_root / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        lines = text.splitlines()
        zero_based_added = {n - 1 for n in added_line_numbers}

        for sentence, start, end in sentences_from(text):
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
