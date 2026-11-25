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

"""Golden-fixture harness for the reading-agent subagent (#259, #281).

Run by hand, like `scripts/run_judgment_agent_golden.py`: each run is a
live `claude -p` call, which costs a real API call and is not guaranteed
deterministic across model versions, so this is not collected by
`unittest discover`.

    python3 scripts/run_reading_agent_golden.py [--model sonnet|haiku|...]
        [--batch-size 2|3|5|10 | --stress | --only NAME ...] [--repeat N]
        [--output-dir DIR]

A fixture under `tests/fixtures/reading_agent_golden/` holds `repo/`, the
files its findings cite, and one or more findings, each a `finding.txt`,
the finding as the session hands it over, beside an `expected.json`; a
fixture with several names them `<name>.finding.txt` and
`<name>.expected.json`. `expected.json`'s `false_claims` lists a fragment
of each claim that has to come back `false`, and its optional
`not_checked` one of each that has to come back `not checked`. Every
other claim has to come back `true`, so a known-true finding lists none.
Its optional `kinds` maps a fragment to the kind the claim holding it has
to be reported as (ADR 0019), and every other claim has to be current. A
claim holding a listed fragment has to be reported. `outside_unit` lists fragments of sentences
beyond the unit, such as the next section's, which no claim may hold: a
unit read past its end is read wrong, whatever the verdicts say. In a
fixture with several findings, so are fragments of the others' `kinds`.
Its optional `reads` lists files that have to be read beside the unit and
subjects, such as one in a tree the finding carries. A fixture's `trees/` holds those trees,
each named by its commit, and `{root}` in a `finding.txt` is the root the
run copies them into.

Every run is one call, and fails unless the array that comes back holds
exactly one object per finding, keyed by its `file:line` and mode, each
with the verdicts and kinds it has to have and its unit, subjects and
`reads` in `read`, and unless the agent opened each of those with
`Read`: a verdict reached from `Grep` matches alone is the failure the
agent exists to prevent. Every problem in every finding is reported, each
of a type: `verdict`, `kind`, `unit`, `read`, `matching`, or `call` for a
call that returned no message to judge.

With no mode, each finding of every fixture is run alone. `--only`, which
may be repeated, runs alone only the findings of the fixture it names, or
the one finding, named as a run prints it, such as
`shared_subject_batch/02-faq.finding.txt`. `--batch-size`
runs the first that many findings of `shared_subject_batch` in one call,
a reading batch as the check-claims skill forms one: findings from one
root that share subjects. One thing differs: the third finding carries
trees, where the skill re-sends a finding with trees apart from the rest,
so that the same path at two trees meets in one call. `--stress` runs
every other fixture's findings in one call, each fixture's `repo/` copied
under its own prefix, `f01/` and on, in one root, and the paths each
finding names moved with it. Those fixtures are unrelated, which no
reading batch's findings are, so a stress run never sets the skill's
cap. `--repeat` runs the mode N times, and `--output-dir` saves each
run's final message, `Read` calls, token usage and problems.

Each call is isolated (`_claude_args`) and its root is a temporary
directory outside this repository.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from run_judgment_agent_golden import _tool_calls

REPO_ROOT = Path(__file__).resolve().parent.parent
SUBAGENT_PROMPT = REPO_ROOT / "claims" / "subagent" / "reading_agent.md"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures" / "reading_agent_golden"
# The fixture every realistic batch is drawn from, in its findings' order.
SHARED_SUBJECT_DIR = FIXTURES_DIR / "shared_subject_batch"
# The batch sizes the cap is measured at (#284).
SIZES = (2, 3, 5, 10)
# Where `claims claim-trees` copies a commit's tree, under the root.
TREES = ".claims/trees/"
# What a problem no one finding owns is reported against.
BATCH = "the whole call"
_UNIT_RE = re.compile(r"^\[advisory\] (\S+):(\d+) \(([^)]+)\)", re.M)
_SUBJECTS_RE = re.compile(r"^Subjects: (.*)$", re.M)
_TREE_RE = re.compile(r"^(written|before) (\w+) ", re.M)


@dataclass(frozen=True)
class Problem:
    """One way a run failed: the finding it is in, or `BATCH`, and its type,
    `verdict`, `kind`, `unit`, `read`, `matching` or `call`."""

    finding: str
    type: str
    detail: str


@dataclass(frozen=True, eq=False)
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
        return [self.path, *self.subjects, *self.expected.get("reads", [])]


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
    """`finding` with its unit's and subjects' paths, in its text and its fields, under `prefix`."""

    text = finding.text
    for path in dict.fromkeys([finding.path, *finding.subjects]):
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


def _unit(finding: Finding) -> str:
    """The text of `finding`'s unit: a `stale-claims` section, or else the line it is at."""

    lines = (finding.repo / finding.path).read_text(encoding="utf-8").splitlines()[finding.line - 1 :]
    end = 1
    if finding.mode == "stale-claims":
        end = next((i for i, line in enumerate(lines[1:], 1) if line.startswith("#")), len(lines))
    return " ".join(" ".join(lines[:end]).split())


def _copied(fixture_dir: Path, root: Path) -> list[Finding]:
    """Copy `fixture_dir`'s `repo/` to `root`, and its `trees/` to where
    `claim-trees` puts a commit's copy, and return its findings, rooted
    there. Every fragment another finding's `kinds` lists that isn't in a
    finding's own unit is outside it."""

    shutil.copytree(fixture_dir / "repo", root, dirs_exist_ok=True)
    if (fixture_dir / "trees").is_dir():
        shutil.copytree(fixture_dir / "trees", root / TREES)
        (root / TREES).parent.joinpath(".gitignore").write_text("*\n", encoding="utf-8")
    found = [replace(f, text=f.text.replace("{root}", str(root)), repo=root) for f in _findings(fixture_dir)]
    fragments = dict.fromkeys(fragment for f in found for fragment in f.expected.get("kinds", {}))
    return [
        replace(
            f,
            expected={
                **f.expected,
                "outside_unit": [*f.expected["outside_unit"], *(x for x in fragments if x not in _unit(f))],
            },
        )
        for f in found
    ]


def _realistic_batch(root: Path, size: int) -> list[Finding]:
    """The first `size` findings of the shared-subject fixture, copied to `root`."""

    return _copied(SHARED_SUBJECT_DIR, root)[:size]


def _stress_batch(root: Path) -> list[Finding]:
    """Every other fixture's findings, each fixture under its own prefix in `root`."""

    batch: list[Finding] = []
    for index, fixture_dir in enumerate((d for d in _fixture_dirs() if d != SHARED_SUBJECT_DIR), 1):
        prefix = f"f{index:02d}"
        shutil.copytree(fixture_dir / "repo", root / prefix)
        batch.extend(replace(_prefixed(f, prefix), repo=root) for f in _findings(fixture_dir))
    return batch


def _system_prompt() -> str:
    # The body below the frontmatter, as `run_judgment_agent_golden.py` does.
    _, _, body = SUBAGENT_PROMPT.read_text(encoding="utf-8").partition("---\n")
    _, _, body = body.partition("---\n")
    return body.strip()


def _relative(path: str, root: Path) -> str:
    """`path`, as a `Read` call or a report gives it, relative to `root` when it is inside it."""

    return os.path.relpath(path, root) if path.startswith(f"{root}/") else os.path.normpath(path)


def _listed(path: str, read: list[str], finding: Finding) -> bool:
    """Whether a report's `read` names `path`: a file of the root by its
    path, in an entry that isn't a tree's alone; a file in a tree by its
    path, or by its relative path beside its tree's commit or role."""

    entries = [entry.replace(f"{finding.repo}/", "") for entry in read]
    named = re.compile(rf"(?<![\w./-])(?:\./)?{re.escape(path)}(?![\w/-])")
    trees = [(commit, re.compile(rf"\b{role}\b|{commit[:7]}")) for role, commit in _TREE_RE.findall(finding.text)]
    if path.startswith(TREES):
        commit, _, inner = path.removeprefix(TREES).partition("/")
        marks = [mark for c, mark in trees if c == commit] or [re.compile(commit[:7])]
        return any(named.search(e) or (inner in e and any(m.search(e) for m in marks)) for e in entries)
    return any(named.search(e) and ("root" in e or not any(m.search(e) for _, m in trees)) for e in entries)


def _judge(report: dict[str, Any], finding: Finding) -> list[Problem]:
    """Every way `report` differs from what `finding` expects: a verdict, a
    kind, a claim from outside the unit, or a path missing from `read`."""

    problems: list[Problem] = []

    def problem(type_: str, detail: str) -> None:
        problems.append(Problem(finding.name, type_, detail))

    expected = finding.expected
    false_claims: list[str] = expected["false_claims"]
    not_checked: list[str] = expected.get("not_checked", [])
    outside_unit: list[str] = expected["outside_unit"]
    listed_read = report.get("read")
    read = [str(r) for r in listed_read] if isinstance(listed_read, list) else []
    for path in finding.must_read:
        if not _listed(path, read, finding):
            problem("read", f"{path!r} not in read: {read!r}")
    reported = report.get("claims")
    if not isinstance(reported, list) or not reported:
        problem("verdict", f"no claims listed: {report!r}")
        return problems
    claims: list[dict[str, Any]] = []
    for item in reported:
        if not isinstance(item, dict):
            problem("verdict", f"not a claim: {item!r}")
            continue
        claim = {**item, "claim": " ".join(str(item.get("claim", "")).split())}
        if any(fragment in claim["claim"] for fragment in outside_unit):
            problem("unit", f"claim from outside the unit: {claim!r}")
            continue
        claims.append(claim)
        if not claim.get("evidence"):
            problem("verdict", f"no evidence cited: {claim!r}")
    verdicts = {**dict.fromkeys(false_claims, "false"), **dict.fromkeys(not_checked, "not checked")}
    for field, needed, default in (("verdict", verdicts, "true"), ("kind", expected.get("kinds", {}), "current")):
        for fragment, value in needed.items():
            if not any(fragment in claim["claim"] for claim in claims):
                problem(field, f"no claim holding {fragment!r}, which has to be {value}: {claims!r}")
        for claim in claims:
            values = {value for fragment, value in needed.items() if fragment in claim["claim"]} or {default}
            if {str(claim.get(field))} != values:
                problem(field, f"expected {' and '.join(sorted(values))}: {claim!r}")
    return problems


def _named_finding(report: dict[str, Any], batch: list[Finding]) -> Finding | None:
    """The finding in `batch` whose `file:line` and mode `report`'s `finding` field names, or `None`."""

    named = str(report.get("finding", ""))
    for finding in batch:
        if re.search(rf"(?<![\w./-]){re.escape(f'{finding.path}:{finding.line}')}(?!\d)", named) and finding.mode in named:
            return finding
    return None


def _judge_batch(reports: Any, batch: list[Finding]) -> list[Problem]:
    """Every way `reports`, the final message's array, falls short of one
    object per finding in `batch`, each passing `_judge`."""

    if not isinstance(reports, list):
        return [Problem(BATCH, "matching", f"not a JSON array: {reports!r}")]
    problems: list[Problem] = []
    matched: dict[Finding, dict[str, Any]] = {}
    for report in reports:
        finding = _named_finding(report, batch) if isinstance(report, dict) else None
        if finding is None:
            problems.append(Problem(BATCH, "matching", f"an object for no finding in the batch: {report!r}"))
        elif finding in matched:
            problems.append(Problem(finding.name, "matching", f"a second object for it: {report!r}"))
        else:
            matched[finding] = report
    for finding in batch:
        if finding in matched:
            problems += _judge(matched[finding], finding)
        else:
            problems.append(Problem(finding.name, "matching", "no object for it"))
    return problems


def _claude_args(prompt: str, system_prompt: str, model: str) -> list[str]:
    """The call, isolated: the contract is the whole system prompt, the three
    tools are the only ones, and no hook, skill, plugin, MCP server or
    `CLAUDE.md` is loaded, so what its user has installed doesn't change a
    run. Claude Code still attaches its own environment block."""

    return [
        "claude",
        "-p",
        prompt,
        "--safe-mode",
        "--strict-mcp-config",
        "--system-prompt",
        system_prompt,
        "--tools",
        "Read,Glob,Grep",
        "--model",
        model,
        "--output-format",
        "stream-json",
        "--verbose",
    ]


@dataclass(frozen=True)
class Reply:
    """What one call returned: its final message, the input of each `Read`
    call and its token usage, or, in `error`, why there is no message."""

    message: str
    reads: list[dict[str, Any]]
    usage: dict[str, Any]
    error: str = ""


def _call(prompt: str, system_prompt: str, model: str, root: Path) -> Reply:
    done = subprocess.run(_claude_args(prompt, system_prompt, model), cwd=root, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    try:
        events: list[dict[str, Any]] = [json.loads(line) for line in done.stdout.splitlines() if line.strip()]
    except ValueError:
        return Reply("", [], {}, f"output is not stream-json: {done.stdout!r}")
    reads = [call.get("input", {}) for call in _tool_calls(events) if call.get("name") == "Read"]
    result = next((e for e in events if e.get("type") == "result"), {})
    reply = Reply(str(result.get("result", "")), reads, result.get("usage", {}))
    if done.returncode != 0:
        return replace(reply, error=f"claude exited {done.returncode}: {done.stderr.strip() or reply.message}")
    if not result or result.get("is_error"):
        return replace(reply, error=f"no successful result event: {done.stdout!r}")
    return reply


def _unread(batch: list[Finding], read_paths: list[str]) -> list[Problem]:
    """Each path a finding in `batch` needs read that no `Read` call opened."""

    return [
        Problem(finding.name, "read", f"no Read call opened {path!r}; Read calls: {read_paths!r}")
        for finding in batch
        for path in finding.must_read
        if path not in {_relative(p, finding.repo) for p in read_paths}
    ]


def _run(batch: list[Finding], system_prompt: str, model: str) -> tuple[Reply, list[Problem]]:
    """Hand `batch` to one call, and judge what comes back."""

    these = "this finding. Its root" if len(batch) == 1 else f"these {len(batch)} findings. Their root"
    findings = "\n\n".join(f.text for f in batch)
    reply = _call(f"Read {these} is this working directory.\n\n{findings}", system_prompt, model, batch[0].repo)
    if reply.error:
        return reply, [Problem(BATCH, "call", reply.error)]
    reports = _extract_array(reply.message)
    problems = _judge_batch(reply.message if reports is None else reports, batch)
    return reply, problems + _unread(batch, [str(r.get("file_path", "")) for r in reply.reads])


def _modes(args: argparse.Namespace) -> list[tuple[str, Callable[[Path], list[Finding]]]]:
    """Each call the mode `args` names makes: its label, and what builds its batch in a root."""

    if args.stress:
        return [("stress", _stress_batch)]
    if args.batch_size:
        return [(f"batch-{args.batch_size}", lambda root: _realistic_batch(root, args.batch_size))]
    return [
        (f"alone {f.name}", lambda root, d=d, i=i: [_copied(d, root)[i]])
        for d in _fixture_dirs()
        for i, f in enumerate(_findings(d))
        if not args.only or {d.name, f.name} & set(args.only)
    ]


def _save(path: Path, model: str, batch: list[Finding], reply: Reply, problems: list[Problem]) -> None:
    run = {
        "model": model,
        "findings": [f.name for f in batch],
        "problems": [asdict(p) for p in problems],
        **asdict(reply),
    }
    path.write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the reading-agent golden fixtures.")
    parser.add_argument("--model", default="sonnet", help="The model to run the agent on (default: sonnet).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--batch-size", type=int, choices=SIZES, help="Hand one call a reading batch of this many findings."
    )
    mode.add_argument("--stress", action="store_true", help="Hand one call the unrelated fixtures' findings.")
    mode.add_argument(
        "--only",
        action="append",
        metavar="NAME",
        help="Run alone only this fixture's findings, or only this finding. May be repeated.",
    )
    parser.add_argument("--repeat", type=int, default=1, help="How many times to run the mode (default: 1).")
    parser.add_argument("--output-dir", type=Path, help="A new or empty directory to save each run to.")
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat has to be at least 1")
    names = {name for d in _fixture_dirs() for f in _findings(d) for name in (d.name, f.name)}
    for name in args.only or []:
        if name not in names:
            parser.error(f"--only {name} is no fixture or finding")
    if args.output_dir is not None:
        if args.output_dir.exists() and (not args.output_dir.is_dir() or any(args.output_dir.iterdir())):
            parser.error(f"--output-dir {args.output_dir} is not a new or empty directory")
        args.output_dir.mkdir(parents=True, exist_ok=True)
    if not _fixture_dirs():
        print(f"no fixtures found under {FIXTURES_DIR}", file=sys.stderr)
        return 2
    system_prompt = _system_prompt()
    failed = 0
    total = 0
    failures: Counter[tuple[str, str]] = Counter()
    for repeat in range(1, args.repeat + 1):
        for label, build in _modes(args):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve()
                batch = build(root)
                reply, problems = _run(batch, system_prompt, args.model)
            if len(batch) == 1:
                problems = [replace(p, finding=batch[0].name) for p in problems]
            total += 1
            failed += bool(problems)
            failures.update({(p.finding, p.type) for p in problems})
            print(f"[{'FAIL' if problems else 'PASS'}] {args.model} {label} {repeat}/{args.repeat}", flush=True)
            for problem in problems:
                print(f"    {problem.finding}: {problem.type}: {problem.detail}", flush=True)
            if args.output_dir is not None:
                name = f"{re.sub(r'[ /]+', '-', label)}-{repeat:02d}.json"
                _save(args.output_dir / name, args.model, batch, reply, problems)
    print(f"failed runs: {failed} of {total}")
    for (finding, type_), runs in sorted(failures.items()):
        print(f"    {runs} x {finding}: {type_}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
