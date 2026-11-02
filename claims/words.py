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

"""Prose reduced to the words it asserts, and the rule the sentence
checks use it for.

`normalise` was `restatement`'s own reduction until `claim-words` and
`temporal-words` needed to ask the same question of a sentence — is it
still saying what it said? — moved here so the three can't disagree about
which differences are only markup (#152).

`removed_sentences_by_file` and `rewrapped` are that question. A diff
that edits one word of a wrapped paragraph removes and re-adds every line
the edit reflows, so a sentence touching an added line may be one the
diff only moved. It was only moved if its words are exactly those of a
whole sentence the same file's old version held on a removed line. A
whole sentence, read as the checks read the new one, rather than any run
of removed words: a sentence that lost its qualifier ("Every check runs,
except the slow ones." to "Every check runs.") is a run of the old one's
words and a different claim. Another file's removed sentences never
count: copied in from elsewhere, it is new to this file, the same
per-file subtraction `restatement` makes.
"""

from __future__ import annotations

import re
from pathlib import Path

from .git import DiffLine, iter_diff
from .markdown import prose_lines, sentences_from

# Inline markup, links and punctuation are dropped before matching, so a
# sentence surviving with different emphasis or a re-pointed link still
# counts as the same claim. Only the words carry the assertion.
LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")
MARKUP_RE = re.compile(r"[`*_~<>\[\]()#|]")
NON_WORD_RE = re.compile(r"[^a-z0-9]+")


def normalise(line: str) -> list[str]:
    """One line as the words it asserts, in order."""

    line = LINK_RE.sub(r"\1", line)
    line = MARKUP_RE.sub(" ", line)
    return NON_WORD_RE.sub(" ", line.lower()).split()


def removed_sentences_by_file(
    repo_root: Path, diff_range: str
) -> dict[str, set[tuple[str, ...]]]:
    """`{path: normalised sentences}` for `diff_range`, keyed by the
    file's new path: every sentence of its old version that a removed line
    is part of, as `normalise` reads it. A file with no removed line is
    absent."""

    removed: dict[str, set[tuple[str, ...]]] = {}
    for file_diff in iter_diff(repo_root, diff_range, whole_files=True):
        old: list[str] = []
        removed_at: set[int] = set()
        for item in file_diff.body:
            if isinstance(item, DiffLine) and item.sign != "+":
                if item.sign == "-":
                    removed_at.add(len(old))
                old.append(item.text)
        if not file_diff.dst or not removed_at:
            continue
        removed[file_diff.dst] = {
            tuple(normalise(sentence))
            for sentence, start, end in sentences_from(prose_lines(old))
            if not removed_at.isdisjoint(range(start, end + 1))
        }
    return removed


def rewrapped(sentence: str, removed: set[tuple[str, ...]]) -> bool:
    """Whether `sentence`'s words are those of one of `removed`, one
    file's entry from `removed_sentences_by_file`."""

    return tuple(normalise(sentence)) in removed
