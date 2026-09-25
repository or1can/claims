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

"""The Markdown-prose primitives more than one check reads a file with.

Generalized here once a second and third caller existed, the same trigger
`claims/execution_grants.py` was generalized on (ticket #19): `fence_state`
had been copied byte-identically into three check modules, and
`temporal_words` needed a fourth copy; `sentences_from` and the two
scope-independent retirement markers had one caller and needed a second.
Nothing here decides anything about a *claim* — a check still owns what it
looks for and which of these markers it honours.

`executable_claims` keeps its own `_fence_state` rather than calling this
one. It returns `(in_fence, dangling_open_line)` and marks a delimiter
line `False`, because a marker sitting on a fence delimiter is a finding
there and content everywhere else; that is a different function, not a
fourth copy of this one (ticket #52).

`mask_code_spans` is the only piece with no prior caller. Every existing
check asks whether something **is** backticked; `temporal-words` is the
first to need the opposite polarity — a match inside an inline code span
is example syntax, not prose making a claim.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import NamedTuple

FENCE_RE = re.compile(r"^\s*(`{3,})")

CODE_SPAN_RE = re.compile(r"`([^`]+)`")

# A terminator may be immediately followed by closing markup (the `*` of an
# `*italicised*` sentence, a closing quote or bracket) before the boundary —
# without this, "*claim.*" splits before the closing `*`, and a caller's
# italics check never sees a whole-wrapped sentence.
SENTENCE_RE = re.compile(r"\S.*?[.!?][*_'\")\]]*(?=\s|$)|\S.+$", re.DOTALL)

ITALIC_RE = re.compile(r"^(\*|_)(?!\1).+\1$", re.DOTALL)

RETIRED_LEAD_IN = "previously said:"

# What `mask_code_spans` writes over a span's own content. Not a word
# character, so a word boundary still holds either side of the span, and
# not a character any pattern here is looking for.
_MASK = "\x00"


def fence_state(lines: Sequence[str]) -> list[bool]:
    """Whether each of `lines` should be excluded from detection because
    it's a fenced code block's own delimiter line or content.

    Same nesting rule as `executable_claims._fence_state` (a fence only
    closes on a same-or-longer run of backticks), so example code inside a
    fence — illustrative, not a claim — isn't treated as a candidate at
    all. Unlike that function, this doesn't distinguish "the opening
    delimiter line" from "content": a delimiter line's own info string
    (` ```json title="config/app.json" `, a real Docusaurus/MkDocs
    convention) is excluded too, so a fence-opener's own trailing text is
    never scanned either.

    A fence that's opened but never closed silences every line after it
    for the rest of the file — deliberately not treated as its own failure
    case here (unlike `executable_claims`'s own dangling-fence gate
    finding, which exists because a marker could be trapped inside one):
    `executable-claims` already reports that over the same tracked `*.md`
    sweep, so relying on it rather than duplicating the check is a real
    cross-check dependency, not an oversight — it only lapses if a
    project's `[executable-claims]` and a calling check's own `exclude`
    lists ever name different files for the same fence.
    """

    in_fence: list[bool] = []
    open_fence: int | None = None
    for line in lines:
        match = FENCE_RE.match(line)
        if match and (open_fence is None or len(match.group(1)) >= open_fence):
            open_fence = None if open_fence is not None else len(match.group(1))
            in_fence.append(True)
            continue
        in_fence.append(open_fence is not None)
    return in_fence


def mask_code_spans(text: str) -> str:
    """`text` with each inline code span's own content written over, so a
    pattern can be matched against the prose alone.

    The backticks themselves survive, so a caller that also needs to know
    *whether* the text carries a citation can still ask `CODE_SPAN_RE`
    of the masked text. Length is preserved too, so an offset into the
    result is an offset into `text`.
    """

    return CODE_SPAN_RE.sub(lambda m: "`" + _MASK * len(m.group(1)) + "`", text)


class Sentence(NamedTuple):
    text: str
    start: int  # 0-based, inclusive
    end: int  # 0-based, inclusive


def sentences_from(text: str) -> list[Sentence]:
    """Every sentence in `text`, with the line span it occupies.

    Paragraphs (blank-line separated) are joined before splitting into
    sentences, so a sentence soft-wrapped across lines is read whole.
    """

    lines = text.splitlines()
    results: list[Sentence] = []
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
                        results.append(Sentence(sentence, start, end))
            para_start = i + 1
    return results
