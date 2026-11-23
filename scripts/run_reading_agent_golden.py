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

"""Golden-fixture harness for the reading-agent subagent (#259).

The same shape as `scripts/run_judgment_agent_golden.py`, and run the same
way, by hand: each fixture under `tests/fixtures/reading_agent_golden/`
is one live `claude -p` call, which costs a real API call and is not
guaranteed deterministic across model versions, so this is not collected
by `unittest discover`.

    python3 scripts/run_reading_agent_golden.py [--model sonnet|haiku|...]

A fixture holds `finding.txt`, the finding as the session hands it over;
`repo/`, the files it cites; and `expected.json`, whose `false_claims`
lists a fragment of each claim that has to come back `false`, and its
optional `not_checked` one of each that has to come back `not checked`.
Every other claim has to come back `true`, so a known-true fixture lists
none. Its optional `kinds` maps a fragment to the kind the claim holding
it has to be reported as (ADR 0019).
`outside_unit` lists fragments of sentences beyond the unit, such as the
next section's, which no claim may hold: a unit read past its end is
read wrong, whatever the verdicts say. A
fixture also fails unless the agent opened the unit's file and every
subject in `finding.txt`'s `Subjects:` line with `Read`: a verdict reached
from `Grep` matches alone is the failure the agent exists to prevent.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from run_judgment_agent_golden import _extract_verdict, _tool_calls

REPO_ROOT = Path(__file__).resolve().parent.parent
SUBAGENT_PROMPT = REPO_ROOT / "claims" / "subagent" / "reading_agent.md"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "reading_agent_golden"
_UNIT_RE = re.compile(r"^\[advisory\] (\S+):\d+ ", re.M)
_SUBJECTS_RE = re.compile(r"^Subjects: (.*)$", re.M)


def _system_prompt() -> str:
    # The body below the frontmatter, as `run_judgment_agent_golden.py` does.
    _, _, body = SUBAGENT_PROMPT.read_text(encoding="utf-8").partition("---\n")
    _, _, body = body.partition("---\n")
    return body.strip()


def _judge(report: dict[str, Any], expected: dict[str, Any]) -> str | None:
    """Why `report`'s verdicts or kinds don't match `expected`, or one of
    its claims holds an `outside_unit` fragment, or `None`."""

    false_claims: list[str] = expected["false_claims"]
    not_checked: list[str] = expected.get("not_checked", [])
    outside_unit: list[str] = expected["outside_unit"]
    claims = report.get("claims")
    if not isinstance(claims, list) or not claims:
        return f"no claims listed: {report!r}"
    for verdict, fragments in (("false", false_claims), ("not checked", not_checked)):
        for fragment in fragments:
            if not any(fragment in c.get("claim", "") and c.get("verdict") == verdict for c in claims):
                return f"no claim holding {fragment!r} came back {verdict}: {claims!r}"
    for fragment, kind in expected.get("kinds", {}).items():
        if not any(fragment in c.get("claim", "") and c.get("kind") == kind for c in claims):
            return f"no claim holding {fragment!r} came back of kind {kind}: {claims!r}"
    for claim in claims:
        if any(fragment in claim.get("claim", "") for fragment in outside_unit):
            return f"claim from outside the unit: {claim!r}"
        if not claim.get("evidence"):
            return f"no evidence cited: {claim!r}"
        listed = any(fragment in claim.get("claim", "") for fragment in false_claims + not_checked)
        if not listed and claim.get("verdict") != "true":
            return f"expected true: {claim!r}"
    return None


def _run_fixture(fixture_dir: Path, system_prompt: str, model: str) -> tuple[bool, str]:
    finding = (fixture_dir / "finding.txt").read_text(encoding="utf-8").strip()
    expected = json.loads((fixture_dir / "expected.json").read_text(encoding="utf-8"))
    unit = _UNIT_RE.search(finding)
    subjects = _SUBJECTS_RE.search(finding)
    assert unit and subjects, f"{fixture_dir.name}/finding.txt has no finding or Subjects: line"
    must_read = [unit.group(1), *subjects.group(1).split(", ")]

    done = subprocess.run(
        [
            "claude",
            "-p",
            f"Read this finding. Its root is this working directory.\n\n{finding}",
            "--append-system-prompt",
            system_prompt,
            "--model",
            model,
            "--output-format",
            "stream-json",
            "--verbose",
            "--allowedTools",
            "Read,Glob,Grep",
        ],
        cwd=fixture_dir / "repo",
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        return False, f"claude exited {done.returncode}: {done.stderr.strip()}"
    events: list[dict[str, Any]] = [json.loads(line) for line in done.stdout.splitlines() if line.strip()]
    result = next((e for e in events if e.get("type") == "result"), None)
    if result is None:
        return False, f"no result event in stream-json output: {done.stdout!r}"
    try:
        report = _extract_verdict(str(result.get("result", "")))
    except ValueError as exc:
        return False, str(exc)

    problem = _judge(report, expected)
    if problem is not None:
        return False, problem
    read_paths = [
        str(call.get("input", {}).get("file_path", ""))
        for call in _tool_calls(events)
        if call.get("name") == "Read"
    ]
    for path in must_read:
        if not any(p.endswith(path) for p in read_paths):
            return False, f"no Read call opened {path!r}; Read calls: {read_paths!r}"
    verdicts = [c["verdict"] for c in report["claims"]]
    return True, f"verdicts={verdicts!r} note={report.get('note')!r}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the reading-agent golden fixtures.")
    parser.add_argument("--model", default="sonnet", help="The model to run the agent on (default: sonnet).")
    args = parser.parse_args()
    system_prompt = _system_prompt()
    fixture_dirs = sorted(p for p in FIXTURES_DIR.iterdir() if p.is_dir())
    if not fixture_dirs:
        print(f"no fixtures found under {FIXTURES_DIR}", file=sys.stderr)
        return 2
    failures = 0
    for fixture_dir in fixture_dirs:
        ok, detail = _run_fixture(fixture_dir, system_prompt, args.model)
        print(f"[{'PASS' if ok else 'FAIL'}] {args.model} {fixture_dir.name}: {detail}")
        failures += not ok
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
