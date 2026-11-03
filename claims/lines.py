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

"""A text's lines, split where git splits them.

`str.splitlines()` also breaks on `\\x0b`, a form feed, `\\x1c`–`\\x1e`,
`\\x85`, U+2028 and U+2029; git numbers lines by `\\n` alone. A file
holding any of those would shift every later line's number against
`git diff`'s and `git blame`'s, so a finding would cite the wrong line
and a line set from git would be matched against the wrong lines (#185).
Every check splits a tracked file's content here, and so does git output
that carries it unless, like `iter_diff`'s, it already splits on `\\n`.

A tracked file is read with `tracked_text`, not `Path.read_text`: that
opens in universal-newlines mode, turning a lone `\\r` into `\\n` before
`git_lines` ever sees it, which shifts every later line just the same (#191).
"""

from __future__ import annotations

from pathlib import Path


def git_lines(text: str) -> list[str]:
    """`text`'s lines, as git numbers them.

    Only `\\n` ends a line. A single `\\r` before it is dropped, so a CRLF
    file reads as `splitlines()` reads it, and a final `\\n` starts no
    further empty line.
    """

    if not text:
        return []
    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()
    return [line[:-1] if line.endswith("\r") else line for line in lines]


def tracked_text(path: Path, errors: str = "strict") -> str:
    """`path`'s text with every line ending as written, for `git_lines`.

    `errors` is the caller's policy for bytes that aren't UTF-8, as
    `open` takes it.
    """

    with path.open(encoding="utf-8", errors=errors, newline="") as f:
        return f.read()
