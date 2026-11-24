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
way, by hand: each finding under `tests/fixtures/reading_agent_golden/`
is one live `claude -p` call, which costs a real API call and is not
guaranteed deterministic across model versions, so this is not collected
by `unittest discover`.

    python3 scripts/run_reading_agent_golden.py [--model sonnet|haiku|...] [--batched]

A fixture holds `repo/`, the files its findings cite, and one or more
findings, each a `finding.txt`, the finding as the session hands it over,
beside an `expected.json`; a fixture with several names them
`<name>.finding.txt` and `<name>.expected.json`. `expected.json`'s
`false_claims` lists a fragment of each claim that has to come back
`false`, and its optional `not_checked` one of each that has to come back
`not checked`. Every other claim has to come back `true`, so a known-true
finding lists none. Its optional `kinds` maps a fragment to the kind the
claim holding it has to be reported as (ADR 0019).
`outside_unit` lists fragments of sentences beyond the unit, such as the
next section's, which no claim may hold: a unit read past its end is
read wrong, whatever the verdicts say. A
finding also fails unless the agent opened the unit's file and every
subject in `finding.txt`'s `Subjects:` line with `Read`: a verdict reached
from `Grep` matches alone is the failure the agent exists to prevent.

`--batched` hands every finding to one call instead, as one reading
batch (#274): each fixture's `repo/` is copied under its own prefix,
`f01/` and on, into one root, and the paths each finding names move with
it. The array that comes back has to hold exactly one object per finding,
keyed by its `file:line` and mode, each judged as it would be alone, and
each listing its own unit and subjects in `read`.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from run_judgment_agent_golden import _tool_calls

REPO_ROOT = Path(__file__).resolve().parent.parent
SUBAGENT_PROMPT = REPO_ROOT / "claims" / "subagent" / "reading_agent.md"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "reading_agent_golden"
_UNIT_RE = re.compile(r"^\[advisory\] (\S+):(\d+) \(([^)]+)\)", re.M)
_SUBJECTS_RE = re.compile(r"^Subjects: (.*)$", re.M)


@dataclass(frozen=True)
class Finding:
    """One finding as a fixture holds it, and where its root is."""

    name: str
    text: str
    expected: dict[str, Any]
    repo: Path
    path: str
    line: int
    mode: str
    subjects: list[str]

    @property
    def must_read(self) -> list[str]:
        return [self.path, *self.subjects]


def _findings(fixture_dir: Path) -> list[Finding]:
    found: list[Finding] = []
    for finding_file in sorted(fixture_dir.glob("*finding.txt")):
        text = finding_file.read_text(encoding="utf-8").strip()
        expected_file = fixture_dir / finding_file.name.replace("finding.txt", "expected.json")
        unit = _UNIT_RE.search(text)
        subjects = _SUBJECTS_RE.search(text)
        assert unit and subjects, f"{fixture_dir.name}/{finding_file.name} has no finding or Subjects: line"
        found.append(
            Finding(
                name=f"{fixture_dir.name}/{finding_file.name}",
                text=text,
                expected=json.loads(expected_file.read_text(encoding="utf-8")),
                repo=fixture_dir / "repo",
                path=unit.group(1),
                line=int(unit.group(2)),
                mode=unit.group(3),
                subjects=subjects.group(1).split(", "),
            )
        )
    return found


def _prefixed(finding: Finding, prefix: str) -> Finding:
    """`finding` with every path it names, in its text and its fields, under `prefix`."""

    text = finding.text
    for path in dict.fromkeys(finding.must_read):
        text = re.sub(rf"(?<![\w./-]){re.escape(path)}(?![\w/-])", f"{prefix}/{path}", text)
    return replace(
        finding,
        text=text,
        path=f"{prefix}/{finding.path}",
        subjects=[f"{prefix}/{s}" for s in finding.subjects],
    )


def _fixture_dirs() -> list[Path]:
    return sorted(p for p in FIXTURES_DIR.iterdir() if p.is_dir())


def _extract_array(text: str) -> Any:
    """The JSON array the agent's final message holds, or `None` when the
    first JSON value in it is not an array: a bare object's own `"claims": [`
    is not an array of reports."""

    starts = [i for i in (text.find("["), text.find("{")) if i != -1]
    if not starts or text[min(starts)] != "[":
        return None
    try:
        return json.JSONDecoder().raw_decode(text[min(starts) :])[0]
    except ValueError:
        return None


def _batch_root(root: Path, fixture_dirs: list[Path]) -> list[Finding]:
    """Copy each fixture's `repo/` under its own prefix in `root`, and return every finding, moved with it."""

    batch: list[Finding] = []
    for index, fixture_dir in enumerate(fixture_dirs, 1):
        prefix = f"f{index:02d}"
        shutil.copytree(fixture_dir / "repo", root / prefix)
        batch.extend(_prefixed(f, prefix) for f in _findings(fixture_dir))
    return batch


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


def _named_finding(report: dict[str, Any], batch: list[Finding]) -> Finding | None:
    """The finding in `batch` whose `file:line` and mode `report`'s `finding` field names, or `None`."""

    named = str(report.get("finding", ""))
    for finding in batch:
        if re.search(rf"(?<![\w./-]){re.escape(f'{finding.path}:{finding.line}')}(?!\d)", named) and finding.mode in named:
            return finding
    return None


def _judge_batch(reports: Any, batch: list[Finding]) -> str | None:
    """Why `reports`, the array a batched call returned, doesn't hold exactly
    one object per finding in `batch`, each passing `_judge` and listing its
    own unit and subjects in `read`, or `None`."""

    if not isinstance(reports, list):
        return f"not a JSON array: {reports!r}"
    matched: dict[tuple[str, int, str], dict[str, Any]] = {}
    for report in reports:
        finding = _named_finding(report, batch) if isinstance(report, dict) else None
        if finding is None:
            return f"an object for no finding in the batch: {report!r}"
        key = (finding.path, finding.line, finding.mode)
        if key in matched:
            return f"two objects for {finding.path}:{finding.line}: {report!r}"
        matched[key] = report
    for finding in batch:
        report = matched.get((finding.path, finding.line, finding.mode))
        if report is None:
            return f"no object for {finding.path}:{finding.line} ({finding.mode})"
        problem = _judge(report, finding.expected)
        if problem is not None:
            return f"{finding.path}:{finding.line}: {problem}"
        read = [str(r) for r in report.get("read", [])]
        for path in finding.must_read:
            if not any(path in r for r in read):
                return f"{finding.path}:{finding.line}: {path!r} not in read: {read!r}"
    return None


def _call(prompt: str, system_prompt: str, model: str, cwd: Path) -> tuple[str | None, str, list[str]]:
    """Run the agent once in `cwd`: its final message, or `None` and why not, and the paths it opened with `Read`."""

    done = subprocess.run(
        [
            "claude",
            "-p",
            prompt,
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
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if done.returncode != 0:
        return None, f"claude exited {done.returncode}: {done.stderr.strip()}", []
    events: list[dict[str, Any]] = [json.loads(line) for line in done.stdout.splitlines() if line.strip()]
    result = next((e for e in events if e.get("type") == "result"), None)
    if result is None:
        return None, f"no result event in stream-json output: {done.stdout!r}", []
    read_paths = [
        str(call.get("input", {}).get("file_path", ""))
        for call in _tool_calls(events)
        if call.get("name") == "Read"
    ]
    return str(result.get("result", "")), "", read_paths


def _unread(must_read: list[str], read_paths: list[str]) -> str | None:
    for path in must_read:
        if not any(p.endswith(path) for p in read_paths):
            return f"no Read call opened {path!r}; Read calls: {read_paths!r}"
    return None


def _run_one(finding: Finding, system_prompt: str, model: str) -> tuple[bool, str]:
    prompt = f"Read this finding. Its root is this working directory.\n\n{finding.text}"
    text, why, read_paths = _call(prompt, system_prompt, model, finding.repo)
    if text is None:
        return False, why
    reports = _extract_array(text)
    if not isinstance(reports, list) or len(reports) != 1:
        return False, f"not a JSON array of one object: {text!r}"
    report = reports[0]
    problem = _judge(report, finding.expected) or _unread(finding.must_read, read_paths)
    if problem is not None:
        return False, problem
    verdicts = [c["verdict"] for c in report["claims"]]
    return True, f"verdicts={verdicts!r} note={report.get('note')!r}"


def _run_batch(fixture_dirs: list[Path], system_prompt: str, model: str) -> tuple[bool, str]:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        batch = _batch_root(root, fixture_dirs)
        findings = "\n\n".join(f.text for f in batch)
        prompt = f"Read these {len(batch)} findings. Their root is this working directory.\n\n{findings}"
        text, why, read_paths = _call(prompt, system_prompt, model, root)
    if text is None:
        return False, why
    reports = _extract_array(text)
    if reports is None:
        return False, f"no JSON array in subagent output: {text!r}"
    problem = _judge_batch(reports, batch) or _unread([p for f in batch for p in f.must_read], read_paths)
    if problem is not None:
        return False, problem
    return True, f"{len(batch)} findings, one object each"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the reading-agent golden fixtures.")
    parser.add_argument("--model", default="sonnet", help="The model to run the agent on (default: sonnet).")
    parser.add_argument("--batched", action="store_true", help="Hand every finding to one call, as one reading batch.")
    args = parser.parse_args()
    system_prompt = _system_prompt()
    fixture_dirs = _fixture_dirs()
    if not fixture_dirs:
        print(f"no fixtures found under {FIXTURES_DIR}", file=sys.stderr)
        return 2
    if args.batched:
        ok, detail = _run_batch(fixture_dirs, system_prompt, args.model)
        print(f"[{'PASS' if ok else 'FAIL'}] {args.model} batched: {detail}")
        return 0 if ok else 1
    failures = 0
    for finding in (f for d in fixture_dirs for f in _findings(d)):
        ok, detail = _run_one(finding, system_prompt, args.model)
        print(f"[{'PASS' if ok else 'FAIL'}] {args.model} {finding.name}: {detail}")
        failures += not ok
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
