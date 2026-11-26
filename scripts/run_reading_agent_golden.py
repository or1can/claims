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

"""Golden-fixture harness for the reading-agent subagent (#259, #281, #287, #293, #296).

Run by hand, like `scripts/run_judgment_agent_golden.py`: each run is a
live `claude -p` call, which costs a real API call and is not guaranteed
deterministic across model versions, so this is not collected by
`unittest discover`.

    python3 scripts/run_reading_agent_golden.py [--model sonnet|haiku|...]
        [--batch-size 2|3|5|10 [--root large|small] | --stress |
        --only NAME ... | --saved DIR ...] [--repeat N] [--output-dir DIR]
        [--alone DIR ...]

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
claim holding a listed fragment has to be reported. `outside_unit` lists
fragments of sentences beyond the unit, such as the next section's, which
no claim may hold. Nor may one hold a fragment
of another finding's `kinds`, in a fixture with several. Its optional
`settled_by` gives the lines that settle a claim, and `absent` the claims
that something is unused: nothing is judged by either, and the tests hold
the fixture to them. Its optional `reads` lists files that have to be read beside the unit and
subjects, such as one in a tree the finding carries. A fixture's `trees/` holds those trees,
each named by its commit, and `{root}` in a `finding.txt` is the root the
run copies them into.

Every run is one call, and the array that comes back has to be one that
holds exactly one object per finding, keyed by its `file:line` and mode,
each with the verdicts and kinds it has to have and its unit, subjects
and `reads` in `read`. The agent has to have opened every line of each of
those with `Read`.
Every problem in every finding is reported, each of a type and a class,
which ADR 0021's Status settles. One rejecting problem rejects a batch
size, a compared one is weighed against its rate alone, and a counted one
is only recorded:

- `verdict`: a claim not reported, or reported with another verdict, or
  with no evidence. Rejecting, but counted for a true claim returned
  `false`.
- `kind`: rejecting for a claim not reported, and for a current or
  intended one called past or superseded. Any other is counted.
- `read`: a unit, subject or `reads` file not opened, only partly read,
  or not in the object's own `read`. Rejecting.
- `unit-other`: a claim of another finding in the call, or of another
  page. Rejecting.
- `unit-own-page`: a sentence of the finding's own page outside its unit.
  Counted. In a stress run, so is another finding's claim on that page.
- `unopened`: a `true` verdict none of whose cited files was opened, or
  citing lines of an opened one that no `Read` returned. Compared.
- `unresolved`: a `true` verdict whose evidence names no file in the
  root, or lines of one that isn't there, so it can't be judged
  `unopened` or not. Compared, and reported
  apart: it weighs against a batch, and not for the rate alone.
- `matching`: a finding with no object or two, or an object for none.
  Counted.
- `call`: the call returned no message to judge. Rejecting, unless a
  person reads it as from outside the agent, such as a usage limit, and
  discards the run.

A run is labelled by its worst class, and the command exits 1 when any
run has a rejecting problem.

With no mode, each finding of every fixture is run alone. `--only`, which
may be repeated, runs alone only the findings of the fixture it names, or
the one finding, named as a run prints it, such as
`shared_subject_batch/02-faq.finding.txt`. `--batch-size`
runs the first that many findings of one root in one call, a reading
batch as the check-claims skill forms one: findings from one root that
share subjects. The root is `shared_subject_large`, whose subjects are
hundreds of lines, or with `--root small` `shared_subject_batch`, which
no cap may rest on alone. One thing differs in the small root: its third
finding carries trees, where the skill re-sends a finding with trees
apart from the rest, so that the same path at two trees meets in one
call. `--stress` runs
every other fixture's findings in one call, each fixture's `repo/` copied
under its own prefix, `f01/` and on, in one root, and the paths each
finding names moved with it. Those fixtures are unrelated, which no
reading batch's findings are, so a stress run never sets the skill's
cap. `--repeat` runs the mode N times, and `--output-dir` saves each
run's final message, `Read` calls, token usage, problems, effort and how
many claims each finding listed. With them it saves what the call's own
output names: the ID of each model that answered, which the alias
`--model` gives may resolve to at one time and not at another, and the
Claude Code version. A call that failed may name neither. Beside them
it saves the digest of the system prompt the call ran with, the contract,
which every run has.

The summary counts the failed runs by class. With `--alone`, the saved
runs of the same findings alone, it says whether the runs pass the bar,
or each way they fall short of it (`_short_of_the_bar`). Runs, batched and
alone together, that differ in model alias, effort, contract digest,
model ID or Claude Code version don't pass, and the summary names each
that differs. A
failed call is compared only on what it names, and runs none of which
names a model ID, or none a version, don't pass.
`--saved` makes no call, and summarises runs saved earlier. It and
`--alone` refuse a run saved without its model ID, version or contract
digest.

Each call is isolated (`_claude_args`) and its root is a temporary
directory outside this repository.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
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
# The fixtures a realistic batch is drawn from, in its findings' order.
ROOTS = {
    "large": FIXTURES_DIR / "shared_subject_large",
    "small": FIXTURES_DIR / "shared_subject_batch",
}
# The effort every call runs at, whatever its user's is.
EFFORT = "medium"
# What made a call, as its output names it, and the field of a saved run holding it.
IDENTITY = {"model ID": "model_id", "Claude Code version": "claude_code_version"}
# The field of a saved run holding the digest of the system prompt it ran with.
CONTRACT = "contract"
# The fewest runs of a size, and readings alone, its bar is judged on, and
# the margin on the compared problem's rate when its alone rate is below it.
MIN_RUNS = 60
MIN_MARGIN = 0.05
RESAMPLES = 5000
# The batch sizes the cap is measured at (#284).
SIZES = (2, 3, 5, 10)
# Where `claims claim-trees` copies a commit's tree, under the root.
TREES = ".claims/trees/"
# What a problem weighs: whether one rejects a batch size, is compared with
# its rate alone, or is only recorded.
REJECTING = "rejecting"
COMPARED = "compared"
COUNTED = "counted"
# What a problem no one finding owns is reported against.
BATCH = "the whole call"
_UNIT_RE = re.compile(r"^\[advisory\] (\S+):(\d+) \(([^)]+)\)", re.M)
_SUBJECTS_RE = re.compile(r"^Subjects: (.*)$", re.M)
_SPAN = r"L?\d+(?:\s*[-–]\s*L?\d+)?"
# What comes between two spans of one file's lines: "9-13 (put), 20 and 31".
_NEXT = r"(?:\s*\([^()]*\))?(?:\s*[,;]\s*(?:and\s+|plus\s+)?|\s+and\s+|\s+plus\s+)"
_SPANS = rf"{_SPAN}(?:{_NEXT}{_SPAN})*"
# A file a claim's evidence cites, and the lines of it, if it gives any.
_CITED_RE = re.compile(
    rf"(?:\blines?\s+(?P<before>{_SPANS})\s+(?:of|in)\s+`?)?"
    rf"(?<![\w./-])(?P<path>[\w./-]*[\w-]\.[A-Za-z]\w*)`?"
    rf"(?:(?P<mark>[:#]|[\s,(]*\blines?\s+)(?P<after>{_SPANS}))?"
)
_TREE_RE = re.compile(r"^(written|before) (\w+) ", re.M)


@dataclass(frozen=True)
class Problem:
    """One way a run went wrong: the finding it is in, or `BATCH`, its type,
    which the module docstring lists, and its class, `REJECTING` unless a
    list in ADR 0021's Status puts it elsewhere."""

    finding: str
    type: str
    detail: str
    problem_class: str = REJECTING


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
        expected = json.loads(expected_file.read_text(encoding="utf-8"))
        page = _one_line((fixture_dir / "repo" / unit.group(1)).read_text(encoding="utf-8"))
        expected["elsewhere"] = [x for x in expected["outside_unit"] if x not in page]
        found.append(
            Finding(
                name=f"{fixture_dir.name}/{finding_file.name}",
                text=text,
                expected=expected,
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


def _one_line(text: str) -> str:
    return " ".join(text.split())


def _unit_lines(finding: Finding) -> list[str]:
    """The lines of `finding`'s unit, less blank ones at its end: a
    `stale-claims` section, or else the line it is at."""

    lines = (finding.repo / finding.path).read_text(encoding="utf-8").splitlines()[finding.line - 1 :]
    end = 1
    if finding.mode == "stale-claims":
        end = next((i for i, line in enumerate(lines[1:], 1) if line.startswith("#")), len(lines))
    while end > 1 and not lines[end - 1].strip():
        end -= 1
    return lines[:end]


def _unit(finding: Finding) -> str:
    return _one_line(" ".join(_unit_lines(finding)))


def _copied(fixture_dir: Path, root: Path) -> list[Finding]:
    """Copy `fixture_dir`'s `repo/` to `root`, and its `trees/` to where
    `claim-trees` puts a commit's copy, and return its findings, rooted
    there. A fragment another finding's `kinds` lists is outside a finding's
    unit unless it is in it: `outside_unit` when it is on the finding's own
    page, and `elsewhere` when it isn't."""

    shutil.copytree(fixture_dir / "repo", root, dirs_exist_ok=True)
    if (fixture_dir / "trees").is_dir():
        shutil.copytree(fixture_dir / "trees", root / TREES)
        (root / TREES).parent.joinpath(".gitignore").write_text("*\n", encoding="utf-8")
    found = [replace(f, text=f.text.replace("{root}", str(root)), repo=root) for f in _findings(fixture_dir)]
    for f in found:
        page = _one_line((root / f.path).read_text(encoding="utf-8"))
        for fragment in _claims_outside(f, found):
            f.expected["outside_unit" if fragment in page else "elsewhere"].append(fragment)
    return found


def _claims_outside(finding: Finding, findings: list[Finding]) -> list[str]:
    """Each fragment another of `findings` lists in `kinds` that isn't in `finding`'s unit."""

    fragments = dict.fromkeys(x for f in findings if f is not finding for x in f.expected.get("kinds", {}))
    return [x for x in fragments if x not in _unit(finding)]


def _realistic_batch(root: Path, size: int, fixture_dir: Path) -> list[Finding]:
    """The first `size` findings of `fixture_dir`, copied to
    `root`. The others' claims are `elsewhere` for each, though one page
    hold both."""

    batch = _copied(fixture_dir, root)[:size]
    for f in batch:
        f.expected["elsewhere"].extend(_claims_outside(f, batch))
    return batch


def _stress_batch(root: Path) -> list[Finding]:
    """Every other fixture's findings, each fixture under its own prefix in `root`."""

    batch: list[Finding] = []
    for index, fixture_dir in enumerate((d for d in _fixture_dirs() if d not in ROOTS.values()), 1):
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

    def problem(type_: str, detail: str, problem_class: str = REJECTING) -> None:
        problems.append(Problem(finding.name, type_, detail, problem_class))

    expected = finding.expected
    false_claims: list[str] = expected["false_claims"]
    not_checked: list[str] = expected.get("not_checked", [])
    outside_unit: list[str] = expected["outside_unit"]
    elsewhere: list[str] = expected.get("elsewhere", [])
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
        claim = {**item, "claim": _one_line(str(item.get("claim", "")))}
        if any(fragment in claim["claim"] for fragment in elsewhere):
            problem("unit-other", f"another finding's claim, or another page's: {claim!r}")
            continue
        if any(fragment in claim["claim"] for fragment in outside_unit):
            problem("unit-own-page", f"claim from outside the unit: {claim!r}", COUNTED)
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
                detail = f"expected {' and '.join(sorted(values))}: {claim!r}"
                problem(field, detail, _mismatch_class(field, values, str(claim.get(field))))
    return problems


def _mismatch_class(field: str, expected: set[str], reported: str) -> str:
    """The class of a verdict or kind that isn't the one expected: counted
    for a true claim returned `false`, and for a kind that doesn't send a
    current or intended claim's reading to an old tree."""

    if field == "verdict":
        return COUNTED if expected == {"true"} and reported == "false" else REJECTING
    to_old_tree = expected & {"current", "intended"} and reported in {"past", "superseded"}
    return REJECTING if to_old_tree else COUNTED


def _named_finding(report: dict[str, Any], batch: list[Finding]) -> Finding | None:
    """The finding in `batch` whose `file:line` and mode `report`'s `finding` field names, or `None`."""

    named = str(report.get("finding", ""))
    for finding in batch:
        if re.search(rf"(?<![\w./-]){re.escape(f'{finding.path}:{finding.line}')}(?!\d)", named) and finding.mode in named:
            return finding
    return None


def _matched(reports: Any, batch: list[Finding]) -> tuple[dict[Finding, dict[str, Any]], list[Problem]]:
    """The object in `reports`, the final message's array, for each finding
    in `batch`, and every way they fall short of exactly one for each."""

    if not isinstance(reports, list):
        return {}, [Problem(BATCH, "matching", f"not a JSON array: {reports!r}", COUNTED)]
    problems: list[Problem] = []
    matched: dict[Finding, dict[str, Any]] = {}
    for report in reports:
        finding = _named_finding(report, batch) if isinstance(report, dict) else None
        if finding is None:
            problems.append(Problem(BATCH, "matching", f"an object for no finding in the batch: {report!r}", COUNTED))
        elif finding in matched:
            problems.append(Problem(finding.name, "matching", f"a second object for it: {report!r}", COUNTED))
        else:
            matched[finding] = report
    problems += [Problem(f.name, "matching", "no object for it", COUNTED) for f in batch if f not in matched]
    return matched, problems


def _judge_batch(reports: Any, batch: list[Finding]) -> list[Problem]:
    """Every way `reports` falls short of one object per finding in `batch`, each passing `_judge`."""

    matched, problems = _matched(reports, batch)
    return problems + [p for finding, report in matched.items() for p in _judge(report, finding)]


def _claude_args(prompt: str, system_prompt: str, model: str) -> list[str]:
    """The call, isolated: the contract is the whole system prompt, the three
    tools are the only ones, and no hook, skill, plugin, MCP server or
    `CLAUDE.md` is loaded, so what its user has installed doesn't change a
    run, nor the effort they work at. Claude Code still attaches its own environment block."""

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
        "--effort",
        EFFORT,
        "--output-format",
        "stream-json",
        "--verbose",
    ]


@dataclass(frozen=True)
class Reply:
    """What one call returned: its final message, the input of each `Read`
    call, with the first and last of the `lines` it opened unless it opened
    none, and its token usage, or, in `error`, why there is no message. With
    it, what its own output names: the Claude Code version, and the ID of
    the model that answered, or of each in turn. A call that failed may name
    neither."""

    message: str
    reads: list[dict[str, Any]]
    usage: dict[str, Any]
    error: str = ""
    model_id: str = ""
    claude_code_version: str = ""


def _lines_opened(events: list[dict[str, Any]]) -> dict[str, list[int]]:
    """The first and last line each `Read` call in `events` returned, by the
    call's id. What came back, not what was asked for: a call may ask for
    lines past the file's end, be cut short, or fail."""

    lines: dict[str, list[int]] = {}
    for event in events:
        result = event.get("tool_use_result")
        file = result.get("file") if isinstance(result, dict) else None
        if not isinstance(file, dict) or not file.get("numLines"):
            continue
        for block in event.get("message", {}).get("content", []):
            if block.get("type") == "tool_result":
                lines[block["tool_use_id"]] = [file["startLine"], file["startLine"] + file["numLines"] - 1]
    return lines


def _call(prompt: str, system_prompt: str, model: str, root: Path) -> Reply:
    done = subprocess.run(
        _claude_args(prompt, system_prompt, model),
        cwd=root,
        # Claude Code lets this variable override `--effort`.
        env={**os.environ, "CLAUDE_CODE_EFFORT_LEVEL": EFFORT},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    try:
        events: list[dict[str, Any]] = [json.loads(line) for line in done.stdout.splitlines() if line.strip()]
    except ValueError:
        return Reply("", [], {}, f"output is not stream-json: {done.stdout!r}")
    lines = _lines_opened(events)
    reads = [
        {**call.get("input", {}), **({"lines": lines[call["id"]]} if call.get("id") in lines else {})}
        for call in _tool_calls(events)
        if call.get("name") == "Read"
    ]
    result = next((e for e in events if e.get("type") == "result"), {})
    answered = [e.get("message", {}).get("model", "") for e in events if e.get("type") == "assistant"]
    reply = Reply(
        str(result.get("result", "")),
        reads,
        result.get("usage", {}),
        # Claude Code gives `<synthetic>` as the model of an error it words itself.
        model_id=", ".join(dict.fromkeys(m for m in answered if m not in {"", "<synthetic>"})),
        claude_code_version=next((e["claude_code_version"] for e in events if "claude_code_version" in e), ""),
    )
    if done.returncode != 0:
        return replace(reply, error=f"claude exited {done.returncode}: {done.stderr.strip() or reply.message}")
    if not result or result.get("is_error"):
        return replace(reply, error=f"no successful result event: {done.stdout!r}")
    return reply


def _opened(reads: list[dict[str, Any]], root: Path) -> dict[str, set[int]]:
    """The lines of each file `reads` opened, by its path relative to `root`."""

    opened: dict[str, set[int]] = {}
    for read in reads:
        if "lines" in read:
            first, last = read["lines"]
            opened.setdefault(_relative(str(read["file_path"]), root), set()).update(range(first, last + 1))
    return opened


def _unread(batch: list[Finding], opened: dict[str, set[int]]) -> list[Problem]:
    """Each unit, and each other file a finding in `batch` needs read, that
    no `Read` call opened, or that they opened only part of."""

    problems: list[Problem] = []
    for finding in batch:
        unit = range(finding.line, finding.line + len(_unit_lines(finding)))
        needed = [(finding.path, unit)]
        for path in finding.must_read[1:]:
            lines = (finding.repo / path).read_text(encoding="utf-8").splitlines()
            needed.append((path, range(1, len(lines) + 1)))
        for path, lines in needed:
            unread = sorted(set(lines) - opened.get(path, set()))
            if path not in opened:
                problems.append(Problem(finding.name, "read", f"no Read call opened {path!r}; opened: {sorted(opened)!r}"))
            elif unread:
                problems.append(Problem(finding.name, "read", f"{path!r} only partly read; unread lines: {unread!r}"))
    return problems


def _cited(evidence: str, tree: str, finding: Finding) -> tuple[list[tuple[list[str], set[int]]], list[str]]:
    """Each file `evidence` cites, with the lines of it, if it gives any, and
    each path it cites lines of that is no file. A file is every path it may
    be at: in each tree of `finding`'s that `tree` names, in the root when
    it names that or no tree, or else in the root, for a file the trees
    don't hold."""

    named = [c for role, c in _TREE_RE.findall(finding.text) if re.search(rf"\b{role}\b|{c[:7]}", tree)]
    places = [f"{TREES}{commit}/" for commit in named]
    if "root" in tree or not named:
        places.append("")
    cited: list[tuple[list[str], set[int]]] = []
    missing: list[str] = []
    for match in _CITED_RE.finditer(evidence):
        path = _relative(match["path"], finding.repo)
        paths = [p + path for p in places if (finding.repo / p / path).is_file()]
        if not paths and (finding.repo / path).is_file():
            paths = [path]
        if not paths or path.startswith(("/", "..")):
            if match["mark"] in {":", "#"}:
                missing.append(path)
            continue
        lines: set[int] = set()
        for span in re.findall(_SPAN, re.sub(r"\([^()]*\)", "", f"{match['before'] or ''} {match['after'] or ''}")):
            numbers = [int(n) for n in re.findall(r"\d+", span)]
            lines.update(range(numbers[0], numbers[-1] + 1))
        cited.append((paths, lines))
    return cited, missing


def _unopened(report: dict[str, Any], finding: Finding, opened: dict[str, set[int]]) -> list[Problem]:
    """Each claim of `report`'s returned `true` on evidence no `Read` opened:
    none of the files it cites, or lines it cites of one that was. Evidence
    naming no file there is, or lines of one that isn't, can't be judged so,
    and is a type of its own."""

    reported = report.get("claims")
    problems: list[Problem] = []
    for claim in reported if isinstance(reported, list) else []:
        if not isinstance(claim, dict) or claim.get("verdict") != "true" or not claim.get("evidence"):
            continue
        cited, missing = _cited(str(claim["evidence"]), str(claim.get("tree", "")), finding)
        read = [(set[int]().union(*(opened[p] for p in paths if p in opened)), lines) for paths, lines in cited]
        read = [(have, lines) for have, lines in read if have]
        if missing or not cited:
            problems.append(Problem(finding.name, "unresolved", f"evidence names no file: {claim!r}", COMPARED))
        if cited and not read:
            problems.append(Problem(finding.name, "unopened", f"no cited file was opened: {claim!r}", COMPARED))
        elif any(lines - have for have, lines in read):
            problems.append(Problem(finding.name, "unopened", f"cites lines that weren't opened: {claim!r}", COMPARED))
    return problems


def _run(batch: list[Finding], system_prompt: str, model: str) -> dict[str, Any]:
    """Hand `batch` to one call, judge what comes back, and return the run as it is saved."""

    these = "this finding. Its root" if len(batch) == 1 else f"these {len(batch)} findings. Their root"
    findings = "\n\n".join(f.text for f in batch)
    reply = _call(f"Read {these} is this working directory.\n\n{findings}", system_prompt, model, batch[0].repo)
    problems = [Problem(BATCH, "call", reply.error)]
    matched: dict[Finding, dict[str, Any]] = {}
    if not reply.error:
        reports = _extract_array(reply.message)
        reports = reply.message if reports is None else reports
        opened = _opened(reply.reads, batch[0].repo)
        matched, _ = _matched(reports, batch)
        problems = _judge_batch(reports, batch) + _unread(batch, opened)
        for finding, report in matched.items():
            problems += _unopened(report, finding, opened)
    if len(batch) == 1:
        problems = [replace(p, finding=batch[0].name) for p in problems]
    listed = {f.name: report.get("claims") for f, report in matched.items()}
    return {
        "model": model,
        "effort": EFFORT,
        CONTRACT: hashlib.sha256(system_prompt.encode("utf-8")).hexdigest(),
        "findings": [f.name for f in batch],
        "problems": [asdict(p) for p in problems],
        "claims": {name: len(claims) if isinstance(claims, list) else 0 for name, claims in listed.items()},
        **asdict(reply),
    }


def _bound(batched: list[tuple[int, int]], alone: list[tuple[int, int]]) -> float:
    """The one-sided 95% upper bound on the batched rate less the alone
    rate. Each call is its readings with the compared problem, and its
    readings. Calls are resampled whole, since one call's readings aren't
    independent. Resampling a few rare readings bounds them too low, and
    none at all at 0, so the bound is never below the one for none: there
    the batched rate is the highest with a 5% chance of none in that many
    calls."""

    draw = random.Random(0)

    def rate(calls: list[tuple[int, int]]) -> float:
        return sum(flagged for flagged, _ in calls) / sum(readings for _, readings in calls)

    unseen = 1 - 0.05 ** (1 / len(batched))
    resampled: list[float] = []
    if_none: list[float] = []
    for _ in range(RESAMPLES):
        alone_rate = rate(draw.choices(alone, k=len(alone)))
        resampled.append(rate(draw.choices(batched, k=len(batched))) - alone_rate)
        if_none.append(unseen - alone_rate)
    return max(sorted(differences)[math.ceil(0.95 * RESAMPLES) - 1] for differences in (resampled, if_none))


def _calls(runs: list[dict[str, Any]], types: set[str]) -> list[tuple[int, int]]:
    """For each of `runs`, its readings with a problem of `types`, and its readings."""

    return [
        (len({p["finding"] for p in run["problems"] if p["type"] in types} & run["claims"].keys()), len(run["claims"]))
        for run in runs
        if run["claims"]
    ]


def _compared(runs: list[dict[str, Any]], alone: list[dict[str, Any]]) -> tuple[float, float, float, float]:
    """The compared problem's rate in `runs` and in `alone`, the bound on the
    difference, and the margin it has to be within. Evidence naming no file
    weighs against the batch, and not for the rate alone."""

    batched_calls = _calls(runs, {"unopened", "unresolved"})
    alone_calls = _calls(alone, {"unopened"})
    batched_rate, alone_rate = (sum(f for f, _ in c) / sum(n for _, n in c) for c in (batched_calls, alone_calls))
    return batched_rate, alone_rate, _bound(batched_calls, alone_calls), max(alone_rate, MIN_MARGIN)


def _same_findings(runs: list[dict[str, Any]], alone: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The runs in `alone` of one finding, when that finding is in `runs`."""

    names = {name for run in runs for name in run["findings"]}
    return [run for run in alone if len(run["findings"]) == 1 and run["findings"][0] in names]


def _failed(runs: list[dict[str, Any]], problem_class: str) -> int:
    """How many of `runs` have a problem of `problem_class`."""

    return sum(any(p["problem_class"] == problem_class for p in run["problems"]) for run in runs)


def _short_of_the_bar(runs: list[dict[str, Any]], alone: list[dict[str, Any]]) -> list[str]:
    """Each way `runs`, of one size, fall short of ADR 0021's bar against `alone`."""

    alone = _same_findings(runs, alone)
    values: dict[str, set[Any]] = {"findings": {tuple(r["findings"]) for r in runs}}
    for name, field in (("model alias", "model"), ("effort", "effort"), ("contract digest", CONTRACT), *IDENTITY.items()):
        # A call that failed may name neither its model ID nor its version.
        values[name] = {r[field] for r in runs + alone if r[field] or all(p["type"] != "call" for p in r["problems"])}
    if differing := [name for name, found in values.items() if len(found) > 1]:
        return [f"the runs differ in their {' and '.join(differing)}"]
    short = [f"the runs don't say their {name}" for name, found in values.items() if found == {""}]
    findings: list[str] = runs[0]["findings"]
    if len(findings) not in SIZES or not all(name.startswith(f"{ROOTS['large'].name}/") for name in findings):
        short.append("they aren't a reading batch of the large root, which a cap has to rest on")
    judged = [run for run in runs if len(run["claims"]) == len(findings)]
    if len(judged) < MIN_RUNS:
        short.append(f"{len(judged)} runs with an object for every finding, of the {MIN_RUNS} needed")
    if rejected := _failed(runs, REJECTING):
        short.append(f"{rejected} of {len(runs)} runs with a rejecting problem")
    readings = Counter(name for run in alone for name in run["claims"])
    if len({readings[name] for name in findings}) > 1:
        short.append("the findings were not each read alone as often")
    if readings.total() < MIN_RUNS:
        short.append(f"{readings.total()} readings alone, of the {MIN_RUNS} needed")
    if readings and any(run["claims"] for run in runs):
        *_, bound, margin = _compared(runs, alone)
        if bound > margin:
            short.append(f"the bound {bound:.3f} on the compared problem's difference is over its margin {margin:.3f}")
    return short


def _summary(runs: list[dict[str, Any]], alone: list[dict[str, Any]]) -> list[str]:
    """What `runs` came to, and, given runs `alone` to compare them with, whether they pass the bar."""

    failed = ", ".join(f"{_failed(runs, class_)} {class_}" for class_ in (REJECTING, COMPARED, COUNTED))
    lines = [f"failed runs of {len(runs)}: {failed}"]
    failures = Counter(
        failure for run in runs for failure in {(p["finding"], p["type"], p["problem_class"]) for p in run["problems"]}
    )
    lines += [f"    {n} x {finding}: {type_} ({class_})" for (finding, type_, class_), n in sorted(failures.items())]
    unresolved = sum(flagged for flagged, _ in _calls(runs, {"unresolved"}))
    if unresolved:
        lines.append(f"evidence naming no file: {unresolved} reading{'s' if unresolved > 1 else ''}")
    alone = _same_findings(runs, alone)
    lines.append(f"claims listed per finding: {_claims_listed(runs)}" + (f", alone {_claims_listed(alone)}" if alone else ""))
    if alone and _calls(runs, set()) and _calls(alone, set()):
        batched_rate, alone_rate, bound, margin = _compared(runs, alone)
        lines.append(
            f"compared problem: batched {batched_rate:.3f}, alone {alone_rate:.3f}, "
            f"upper bound on the difference {bound:.3f}, margin {margin:.3f}"
        )
    if alone:
        short = _short_of_the_bar(runs, alone)
        lines += [f"doesn't pass the bar: {reason}" for reason in short] or ["passes the bar"]
    return lines


def _claims_listed(runs: list[dict[str, Any]]) -> str:
    listed = [n for run in runs for n in run["claims"].values()]
    return f"{sum(listed) / len(listed):.2f}" if listed else "none"


def _saved(directories: list[Path], parser: argparse.ArgumentParser) -> list[dict[str, Any]]:
    """The runs saved in `directories`."""

    runs: list[dict[str, Any]] = []
    for directory in directories:
        files = sorted(directory.glob("*.json"))
        if not files:
            parser.error(f"{directory} holds no saved run")
        for file in files:
            run = json.loads(file.read_text(encoding="utf-8"))
            if not {"claims", CONTRACT, *IDENTITY.values()} <= run.keys():
                parser.error(f"{file} was saved by an earlier harness, whose runs aren't judged by this bar")
            runs.append(run)
    return runs


def _modes(args: argparse.Namespace) -> list[tuple[str, Callable[[Path], list[Finding]]]]:
    """Each call the mode `args` names makes: its label, and what builds its batch in a root."""

    if args.stress:
        return [("stress", _stress_batch)]
    if args.batch_size:
        return [
            (
                f"{args.root}-batch-{args.batch_size}",
                lambda root: _realistic_batch(root, args.batch_size, ROOTS[args.root]),
            )
        ]
    return [
        (f"alone {f.name}", lambda root, d=d, i=i: [_copied(d, root)[i]])
        for d in _fixture_dirs()
        for i, f in enumerate(_findings(d))
        if not args.only or {d.name, f.name} & set(args.only)
    ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the reading-agent golden fixtures.")
    parser.add_argument("--model", default="sonnet", help="The model to run the agent on (default: sonnet).")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--batch-size", type=int, choices=SIZES, help="Hand one call a reading batch of this many findings."
    )
    parser.add_argument(
        "--root", choices=sorted(ROOTS), default="large", help="The root --batch-size draws from (default: large)."
    )
    mode.add_argument("--stress", action="store_true", help="Hand one call the unrelated fixtures' findings.")
    mode.add_argument(
        "--only",
        action="append",
        metavar="NAME",
        help="Run alone only this fixture's findings, or only this finding. May be repeated.",
    )
    mode.add_argument(
        "--saved",
        action="append",
        type=Path,
        metavar="DIR",
        help="Make no call, and summarise the runs an --output-dir saved. May be repeated.",
    )
    parser.add_argument(
        "--alone",
        action="append",
        type=Path,
        default=[],
        metavar="DIR",
        help="Judge the runs of a size against the runs alone saved here. May be repeated.",
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
    alone = _saved(args.alone, parser)
    if args.saved:
        runs = _saved(args.saved, parser)
        print("\n".join(_summary(runs, alone)))
        return _exit_code(runs)
    if args.output_dir is not None:
        if args.output_dir.exists() and (not args.output_dir.is_dir() or any(args.output_dir.iterdir())):
            parser.error(f"--output-dir {args.output_dir} is not a new or empty directory")
        args.output_dir.mkdir(parents=True, exist_ok=True)
    if not _fixture_dirs():
        print(f"no fixtures found under {FIXTURES_DIR}", file=sys.stderr)
        return 2
    system_prompt = _system_prompt()
    runs: list[dict[str, Any]] = []
    for repeat in range(1, args.repeat + 1):
        for label, build in _modes(args):
            with tempfile.TemporaryDirectory() as tmp:
                run = _run(build(Path(tmp).resolve()), system_prompt, args.model)
            runs.append(run)
            classes = {p["problem_class"] for p in run["problems"]}
            worst = next((c for c in (REJECTING, COMPARED, COUNTED) if c in classes), "pass")
            print(f"[{worst.upper()}] {args.model} {label} {repeat}/{args.repeat}", flush=True)
            for p in run["problems"]:
                print(f"    {p['finding']}: {p['type']}: {p['detail']}", flush=True)
            if args.output_dir is not None:
                name = f"{re.sub(r'[ /]+', '-', label)}-{repeat:02d}.json"
                (args.output_dir / name).write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    print("\n".join(_summary(runs, alone)))
    return _exit_code(runs)


def _exit_code(runs: list[dict[str, Any]]) -> int:
    """1 when any run has a rejecting problem, else 0."""

    return int(_failed(runs, REJECTING) > 0)


if __name__ == "__main__":
    raise SystemExit(main())
