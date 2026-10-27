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

"""Git `pre-commit` hook adapter, installed as the `claims-pre-commit`
console command (#127): the same per-repository decision as the
`PreToolUse` hook (`claims.gate`), for the repository git runs it in,
reported through stderr and the exit code alone — `1` blocks the commit.

An unexpected exception inside `claims`, an import error included, fails
open, with a warning, rather than blocking: a broken install would
otherwise block every commit in every repository using it, with
`--no-verify` the only way past.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TextIO


def main(repo_root: Path | None = None, stderr: TextIO = sys.stderr) -> int:
    try:
        # Imported here, not at the top, so a check module that fails to
        # import fails open too.
        from .gate import decide_repo

        decision = decide_repo(repo_root or Path.cwd())
    except Exception as e:
        print(f"claims: internal error, commit not checked: {e!r}", file=stderr)
        return 0
    if decision is None:
        return 0
    print(decision.message, file=stderr)
    return 1 if decision.block else 0


if __name__ == "__main__":
    sys.exit(main())
