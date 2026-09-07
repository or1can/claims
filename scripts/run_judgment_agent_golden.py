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

"""Golden-fixture harness for the judgment-agent subagent's verdict half.

Ticket 15's own test criterion is explicit that this half needs "behavioral/
golden fixtures ... not unit tests, since the subagent's output is
LLM-driven rather than a pure function" (spec.md's Testing Decisions). This
script is that harness: it shells out to a live `claude -p` invocation per
fixture under `tests/fixtures/judgment_agent_golden/`, which costs a real API
call and is not guaranteed deterministic across model versions.

Deliberately **not** collected by `unittest discover -s tests -p 'test_*.py'`
(it lives under `scripts/`, not `tests/`, and isn't named `test_*.py`) —
run it by hand: `python3 scripts/run_judgment_agent_golden.py`.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SUBAGENT_PROMPT = REPO_ROOT / "claims" / "subagent" / "judgment_agent.md"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "judgment_agent_golden"

_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _system_prompt() -> str:
    text = SUBAGENT_PROMPT.read_text(encoding="utf-8")
    # Strip the `---`-delimited YAML frontmatter; `claude -p` takes the
    # subagent's instructions as a system prompt, not its Claude Code
    # frontmatter (name/description/tools are for agent *discovery*, which
    # this harness bypasses by invoking the prompt directly).
    _, _, body = text.partition("---\n")
    _, _, body = body.partition("---\n")
    return body.strip()


def _extract_verdict(result_text: str) -> dict[str, object]:
    match = _JSON_OBJECT_RE.search(result_text)
    if not match:
        raise ValueError(f"no JSON object found in subagent output: {result_text!r}")
    return json.loads(match.group(0))


def _run_fixture(fixture_dir: Path, system_prompt: str) -> tuple[bool, str]:
    claim = (fixture_dir / "claim.md").read_text(encoding="utf-8").strip()
    expected = json.loads((fixture_dir / "expected_verdict.json").read_text(encoding="utf-8"))
    repo_dir = fixture_dir / "repo"

    message = (
        f"Candidate claim (from claim.md, in the current working directory's "
        f"parent):\n\n{claim}\n\nThe code it cites is in this working "
        f"directory. Produce your verdict."
    )

    done = subprocess.run(
        [
            "claude",
            "-p",
            message,
            "--append-system-prompt",
            system_prompt,
            "--output-format",
            "json",
            "--allowedTools",
            "Read,Glob,Grep",
        ],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        return False, f"claude exited {done.returncode}: {done.stderr.strip()}"

    try:
        envelope = json.loads(done.stdout)
        result_text = envelope.get("result", done.stdout) if isinstance(envelope, dict) else done.stdout
    except json.JSONDecodeError:
        result_text = done.stdout

    try:
        verdict = _extract_verdict(result_text)
    except ValueError as exc:
        return False, str(exc)

    if not verdict.get("evidence"):
        return False, f"no evidence cited: {verdict!r}"
    if verdict.get("verdict") != expected["verdict"]:
        return False, f"expected verdict {expected['verdict']!r}, got {verdict!r}"
    return True, f"verdict={verdict['verdict']!r} evidence={verdict['evidence']!r}"


def main() -> int:
    system_prompt = _system_prompt()
    fixture_dirs = sorted(p for p in FIXTURES_DIR.iterdir() if p.is_dir())
    if not fixture_dirs:
        print(f"no fixtures found under {FIXTURES_DIR}", file=sys.stderr)
        return 2

    failures = 0
    for fixture_dir in fixture_dirs:
        ok, detail = _run_fixture(fixture_dir, system_prompt)
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {fixture_dir.name}: {detail}")
        if not ok:
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
