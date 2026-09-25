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

"""The `temporal-words` check: a sentence a diff added to a designated
reference page that frames what a binary does in version history.
`docs/checks/temporal-words.md` is the account of the three modes, the
word list, the `files` key and the retirement markers; this docstring is
why the code is shaped the way it is.

Advisory, for `claim-words`' reason: a sweep for the words a claim is
made of cannot tell you the claim is wrong.

**Why not a fourth `claim-words` mode.** The two checks share sentence
splitting, diff scoping, severity and the shape of `files` — but not the
file set. A to-do list's temporal wording is *correct* — it exists to
say what is not done yet — while its claims are live and exactly what a
project designates for `claim-words`. Sharing one `files` key would
either sweep the to-do list for "not yet" or drop it from `claim-words`'
three modes. A per-mode scope is the same separation with a worse
config shape, so this is its own check with its own key (ticket #52).

**Three modes, one per matching strategy**, matching `claim_words`' own
stated contract — a consumer filters or counts by which kind fired
without parsing message text. `now` is the whole reason there are three
rather than two: at 3 defects in 12 hits over the corpus below it is the
one word cheap enough to rescue with a citation gate, and a gate that
applies to a single entry of `PHRASES` is unreadable as prose and
unrepresentable as one word-list regex.

**The word list is measured, not guessed.** It comes from a sweep of
or1can/ratect's `docs/` at or1can/ratect#185, every hit read: the
phrases carried 6/6, 4/4, 6/13 and 4/7 defects, and `now` 3/12 behind
the citation gate. `no longer` is deliberately absent — 0 defects in 3
hits, every one an external tool's status ("Earthly is no longer
maintained") rather than a claim about this project's own past. The
false positives that remain are runtime state ("a directory that doesn't
exist yet"), tutorial sequencing, and the reader's own project;
advisory severity is what makes that acceptable, per `AGENTS.md`'s
"recall over precision".

**Two components is somebody else's version.** Simulated over the same
tree before its sweep, a bare `X.Y.Z` scored 4 defects in 4 hits while
`X.Y` scored 0 in 6 — every one an external tool's (Docker 20.10, the
Docker API 1.41, OpenSSH 8.8). Prefixing on `since`/`from`/`in`/
`before`/`after` rescued none of those and added no three-component
match a bare version doesn't already make, so there is no prefix list.

`VERSION_RE`'s left boundary is `(?<![\\w.])`, **not** `claim_words`'
house `(?<![\\w-])`. That boundary exists to stop `always` matching
inside `--always-verify`; inherited here it would reject `pre-0.9.0`,
which is one of the four version defects the simulation found.

**Retirement markers: italics and the lead-in, not the blockquote.**
`decisions/0003-retirement-markers-are-scope-dependent.md` is the
reasoning and the measurement. In this check's file scope — reference
prose, with the changelog deliberately excluded — a `>` is a callout
making a live claim, and 62 such lines in the corpus confirm it.

**Exemption polarity is the opposite of every sibling check's.** They
ask whether a candidate *is* backticked, because backticking is what
marks a real named thing. Here a backticked span is example syntax
(`alpine:3.18.2`, `ref = "1.2.3"`), so the span's own content is masked
out before matching rather than searched — `claims.markdown`'s
`mask_code_spans`, which exists for this.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from ..config import path_matches, string_list_config
from ..git import added_lines_by_file
from ..markdown import (
    CODE_SPAN_RE,
    ITALIC_RE,
    RETIRED_LEAD_IN,
    fence_state,
    mask_code_spans,
    sentences_from,
)
from ..runner import Finding, register_check

NAME = "temporal-words"

MODE_VERSION = "temporal-words-version"
MODE_PHRASE = "temporal-words-phrase"
MODE_CITED = "temporal-words-cited"

# Framing that puts a reference page's sentence at a point in the
# project's own history. The word alone fires it.
PHRASES = [
    "yet", "not yet", "used to", "before this existed", "currently",
    "today", "this first version", "previously", "historically",
    "until now",
]
# The one word that needs a citation beside it to be worth reporting.
CITED = ["now"]

# Same boundary treatment as `claim_words`' own word lists: `\b` alone
# would still match a word inside a hyphenated identifier.
PHRASE_RE = re.compile(
    r"(?<![\w-])(" + "|".join(p.replace(" ", r"\s+") for p in PHRASES) + r")(?![\w-])",
    re.IGNORECASE,
)
CITED_RE = re.compile(
    r"(?<![\w-])(" + "|".join(CITED) + r")(?![\w-])",
    re.IGNORECASE,
)
# Three components exactly. The left boundary admits a preceding hyphen
# (`pre-0.9.0`) while rejecting a word character and a dot; the lookahead
# rejects a fourth component (`99.1.2.3`, a trace id, not a version)
# without rejecting the full stop that ends the sentence carrying it
# ("Added in 0.9.0.").
VERSION_RE = re.compile(r"(?<![\w.])\d+\.\d+\.\d+(?!\.?\w)")


def _is_retired_quote(sentence: str) -> bool:
    """Whether one of this check's two retirement markers exempts it.

    The blockquote marker `claim-words` honours is deliberately not here
    — ADR 0003. Neither of these two needs the surrounding lines to
    decide, which is why this takes the sentence alone.
    """

    if ITALIC_RE.match(sentence.strip()):
        return True
    return sentence.strip().lower().startswith(RETIRED_LEAD_IN)


def _classify(sentence: str) -> list[str]:
    """Every mode this sentence matches — see the `MODE_*` constants.

    Matching runs against the sentence with its inline code spans masked,
    so example syntax is never a match; the citation gate reads the same
    masked text, whose backticks survive the masking.
    """

    prose = mask_code_spans(sentence)
    modes = []
    if VERSION_RE.search(prose):
        modes.append(MODE_VERSION)
    if PHRASE_RE.search(prose):
        modes.append(MODE_PHRASE)
    if CITED_RE.search(prose) and CODE_SPAN_RE.search(prose):
        modes.append(MODE_CITED)
    return modes


def _prose_lines(lines: Sequence[str]) -> str:
    """`lines` with every fenced line blanked, rejoined.

    Blanking rather than dropping keeps each surviving sentence's line
    numbers the file's own, and makes a fenced block a paragraph break —
    a sentence never runs through one.
    """

    in_fence = fence_state(lines)
    return "\n".join("" if fenced else line for line, fenced in zip(lines, in_fence))


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
        zero_based_added = {n - 1 for n in added_line_numbers}

        for sentence, start, end in sentences_from(_prose_lines(text.splitlines())):
            if zero_based_added.isdisjoint(range(start, end + 1)):
                continue
            if _is_retired_quote(sentence):
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
