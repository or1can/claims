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

"""Golden-fixture harness for the reading-agent subagent (#259, #281, #287, #293, #296, #304, #308).

Run by hand, like `scripts/run_judgment_agent_golden.py`: each run is a
live `claude -p` call, which costs a real API call and is not guaranteed
deterministic across model versions, so this is not collected by
`unittest discover`.

    python3 scripts/run_reading_agent_golden.py [--model sonnet|haiku|...]
        [--batch 5a|5b|10 | --batch-size 2|3|5|10 [--root large|small] | --stress |
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
which ADR 0022 settles by whether the session's own check of the
reading would catch it before a mark. A problem not caught is rejecting,
and weighs on the bar's bound; a caught one costs a re-send of its
finding, and weighs on the bar's cost; a counted one is only recorded:

- `verdict`: a claim not reported, or reported with another verdict.
  Rejecting, but counted for a true claim returned `false`.
- `kind`: rejecting for a claim not reported, and for a current or
  intended one called past or superseded. Any other is counted.
- `read`: a unit, subject or `reads` file listed in `read` in full that
  no `Read` call opened, or opened only in part, or a `reads` file not in
  `read`. Rejecting. A unit or subject missing from `read`, or listed
  with only part of it, is caught.
- `unit-other`: a claim of another finding in the call, or of another
  page. Rejecting.
- `unit-own-page`: a sentence of the finding's own page outside its unit.
  Counted. In a stress run, so is another finding's claim on that page.
- `unopened`: a `true` verdict none of whose cited files was opened, or
  citing lines of an opened one that no `Read` returned, where `read`
  gives what it cites. Rejecting.
- `call`: the call returned no message to judge. Rejecting, unless a
  person reads it as from outside the agent, such as a usage limit, and
  discards the run.
- `matching`, `read`, `cited`, `no-file` and `no-claims`: whatever
  `claims.reading.check_reading`, the session's own check, flags. Each is
  caught. So are a claim with no evidence, as `no-file`, and a claim
  `not checked` that the fixture doesn't expect so, as `not-checked`.
- `format`: a final message holding the array, and more: a Markdown
  fence around it, or prose before or after it. The array is still read
  from it. Counted.

A run is labelled by its worst class.

With no mode, each finding of every fixture is run alone. `--only`, which
may be repeated, runs alone only the findings of the fixture it names, or
the one finding, named as a run prints it, such as
`shared_subject_batch/02-faq.finding.txt`. `--batch` runs one of
`BATCHES` in one call, the named reading batches of `shared_subject_large`,
whose subjects are hundreds of lines, which a cap rests on: `5a` and `5b`,
which together hold all ten of its findings, and `10`, which is all ten.
Each is a reading batch as the check-claims skill forms one: findings from
one root joined by shared subjects. `--batch-size` runs the first that
many findings of one root in one call, the large root, or with `--root
small` `shared_subject_batch`, and no cap rests on either. One thing
differs in the small root: its third finding carries trees, where the
skill re-sends a finding with trees apart from the rest, so that the same
path at two trees meets in one call. `--stress` runs
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
which every run has, and the root it ran in.

The summary counts the failed runs by class, and gives, per finding read,
the rate of problems not caught and its bound (`_bound`). With
`--alone`, the saved runs of the same findings alone, it gives that rate
and bound alone too, and the tokens per finding a batch spends, its
re-sends priced at each finding's tokens alone, beside the tokens per
finding alone (`_cost`), and says whether the runs pass ADR 0022's bar, or each way they fall
short of it (`_short_of_the_bar`). A run alone
that returned no report is no reading, and each finding has to be read
alone as often as the one read most, the count: one short of it is to be
run alone again, and one run alone more than twice the count leaves the
size not accepted (`_short_of_the_count`). Runs, batched and
alone together, that differ in model alias, effort, contract digest,
model ID or Claude Code version don't pass, and the summary names each
that differs. A
failed call is compared only on what it names, and runs none of which
names a model ID, or none a version, don't pass.
`--saved` makes no call, and summarises runs saved earlier, each graded
again from its final message and `Read` calls by this harness, not by
the problems it was saved with, in the batch rebuilt from the run's own
findings (`_regraded`). It and
`--alone` refuse a run saved without its model ID, version or contract
digest. The command exits 1 when the runs don't pass the bar, or, given
no `--alone`, when any run has a problem not caught.

Each call is isolated (`_claude_args`) and its root is a temporary
directory outside this repository.

A finding line, the object naming it, a `read` entry and a claim's
evidence are parsed by `claims.reading`, and what is caught is what
`claims.reading.check_reading` flags: the code `claims.cli check-reading`
runs in a session (#299).
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
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
# Run as a script, the repo root is not on `sys.path` yet.
sys.path.insert(0, str(REPO_ROOT))

from claims.reading import FINDING_RE, TREE_RE, TREES, Sent, check_reading, cited, listing, matched, relative  # noqa: E402
from claims.reading import extract_array as _extract_array  # noqa: E402
from run_judgment_agent_golden import _tool_calls  # noqa: E402

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
# The batched calls of a size, and the readings alone of each of the large
# root's findings, which serve every size, that its bar is judged on, both
# fixed before any run (ADR 0022 and its amendment).
BATCHED_RUNS = 200
ALONE_COUNT = 60
# The most a one-sided 95% upper bound on the rate of problems not caught,
# per finding read, may be.
LIMIT = 0.01
RESAMPLES = 5000
# The fields of a call's usage that its tokens are the sum of.
TOKENS = ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens")
# The batch sizes the cap is measured at (#284).
SIZES = (2, 3, 5, 10)


def _large(*stems: str) -> tuple[str, ...]:
    return tuple(f"{ROOTS['large'].name}/{stem}.finding.txt" for stem in stems)


# The reading batches of the large root a size's cap rests on, by name
# (ADR 0022's amendment): each joined by shared subjects, as the
# check-claims skill's step 2 joins one, and a size's batches together
# holding each of the root's findings once. Each is run as often as the
# others of its size, `BATCHED_RUNS` between them.
BATCHES = {
    "5a": _large("01-holds", "02-support", "04-audit", "05-privacy", "06-hold-length"),
    "5b": _large("03-planning", "07-stock-totalising", "08-stock-temporal", "09-cases", "10-planner-totalising"),
    "10": _large(
        "01-holds",
        "02-support",
        "03-planning",
        "04-audit",
        "05-privacy",
        "06-hold-length",
        "07-stock-totalising",
        "08-stock-temporal",
        "09-cases",
        "10-planner-totalising",
    ),
}
# What a problem weighs: whether the session's own check would not catch
# it, and it rejects a batch size; would catch it, and it costs a re-send;
# or it is only recorded.
REJECTING = "rejecting"
CAUGHT = "caught"
COUNTED = "counted"
# What a problem no one finding owns is reported against.
BATCH = "the whole call"
_SUBJECTS_RE = re.compile(r"^Subjects: (.*)$", re.M)


@dataclass(frozen=True)
class Problem:
    """One way a run went wrong: the finding it is in, or `BATCH`, its type,
    which the module docstring lists, and its class, `REJECTING` unless a
    list in ADR 0022's Decision puts it elsewhere."""

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
        unit = FINDING_RE.search(text)
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
    """The first `size` findings of `fixture_dir`, copied to `root`, as `_named_batch` builds them."""

    return _named_batch(root, [f.name for f in _findings(fixture_dir)][:size], fixture_dir)


def _named_batch(root: Path, names: Sequence[str], fixture_dir: Path) -> list[Finding]:
    """The findings of `fixture_dir` named `names`, in that order, copied
    to `root`. The others' claims are `elsewhere` for each, though one page
    hold both."""

    found = {f.name: f for f in _copied(fixture_dir, root)}
    batch = [found[name] for name in names]
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


def _trees(finding: Finding) -> list[tuple[str, str]]:
    """The trees `finding` carries, each `(role, commit)`, as its text gives them."""

    return TREE_RE.findall(finding.text)


def _listed(path: str, read: list[str], finding: Finding) -> bool:
    """Whether a report's `read` names `path`, as `claims.reading.listing` reads it."""

    return bool(listing(path, read, finding.repo, _trees(finding)))


def _read_of(report: dict[str, Any]) -> list[str]:
    listed_read = report.get("read")
    return [str(r) for r in listed_read] if isinstance(listed_read, list) else []


def _sent(finding: Finding) -> Sent:
    """`finding` as the session sends it, for `claims.reading.check_reading`."""

    return Sent(finding.path, finding.line, finding.mode, tuple(finding.subjects), finding.repo, tuple(_trees(finding)))


def _judge(report: dict[str, Any], finding: Finding) -> list[Problem]:
    """Every way `report` differs from what `finding` expects that the
    session's own check doesn't flag: a verdict, a kind, a claim from
    outside the unit, or a `reads` file missing from `read`. Beside them,
    as caught, a claim `not checked` the fixture doesn't expect, and one
    with no evidence."""

    problems: list[Problem] = []

    def problem(type_: str, detail: str, problem_class: str = REJECTING) -> None:
        problems.append(Problem(finding.name, type_, detail, problem_class))

    expected = finding.expected
    false_claims: list[str] = expected["false_claims"]
    not_checked: list[str] = expected.get("not_checked", [])
    outside_unit: list[str] = expected["outside_unit"]
    elsewhere: list[str] = expected.get("elsewhere", [])
    read = _read_of(report)
    # The unit and the subjects are held to `read` by `check_reading`.
    for path in expected.get("reads", []):
        if not _listed(path, read, finding):
            problem("read", f"{path!r} not in read: {read!r}")
    reported = report.get("claims")
    if not isinstance(reported, list) or not reported:
        # `check_reading` flags a report listing no claims.
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
            problem("no-file", f"no evidence cited: {claim!r}", CAUGHT)
    verdicts = {**dict.fromkeys(false_claims, "false"), **dict.fromkeys(not_checked, "not checked")}
    for field, needed, default in (("verdict", verdicts, "true"), ("kind", expected.get("kinds", {}), "current")):
        for fragment, value in needed.items():
            if not any(fragment in claim["claim"] for claim in claims):
                problem(field, f"no claim holding {fragment!r}, which has to be {value}: {claims!r}")
        for claim in claims:
            values = {value for fragment, value in needed.items() if fragment in claim["claim"]} or {default}
            reported_value = str(claim.get(field))
            if {reported_value} != values:
                detail = f"expected {' and '.join(sorted(values))}: {claim!r}"
                if field == "verdict" and reported_value == "not checked":
                    problem("not-checked", detail, CAUGHT)
                else:
                    problem(field, detail, _mismatch_class(field, values, reported_value))
    return problems


def _mismatch_class(field: str, expected: set[str], reported: str) -> str:
    """The class of a verdict or kind that isn't the one expected: counted
    for a true claim returned `false`, and for a kind that doesn't send a
    current or intended claim's reading to an old tree."""

    if field == "verdict":
        return COUNTED if expected == {"true"} and reported == "false" else REJECTING
    to_old_tree = expected & {"current", "intended"} and reported in {"past", "superseded"}
    return REJECTING if to_old_tree else COUNTED


def _objects(reports: Any, batch: list[Finding]) -> dict[Finding, dict[str, Any]]:
    """The one object in `reports`, the final message's array, for each
    finding in `batch` that has exactly one, as `claims.reading.matched`
    pairs them. A finding with none or two is re-sent, and not judged."""

    found, _ = matched(reports, [_sent(f) for f in batch])
    return {f: objects[0] for f, objects in zip(batch, found.values(), strict=True) if len(objects) == 1}


def _judge_batch(reports: Any, batch: list[Finding]) -> list[Problem]:
    """Every item `claims.reading.check_reading` flags in `reports`, each
    caught, but a `not checked` claim, which `_judge` holds to the fixture;
    then every problem `_judge` finds in each finding's one object."""

    names = {_sent(f).name: f.name for f in batch}
    problems = [
        Problem(names.get(flag.finding, BATCH), flag.type, flag.detail, CAUGHT)
        for flag in check_reading(reports, [_sent(f) for f in batch])
        if flag.type != "not-checked"
    ]
    return problems + [p for finding, report in _objects(reports, batch).items() for p in _judge(report, finding)]


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
            opened.setdefault(relative(str(read["file_path"]), root), set()).update(range(first, last + 1))
    return opened


def _unread(batch: list[Finding], opened: dict[str, set[int]], reports: Any) -> list[Problem]:
    """Each unit, and each other file a finding in `batch` needs read, that
    its one object in `reports` lists as read in full, but that no `Read`
    call opened, or that they opened only part of. One its object doesn't
    list so, `check_reading` flags, or `_judge` does for a `reads` file."""

    objects = _objects(reports, batch)
    flagged = {(flag.finding, flag.path) for flag in check_reading(reports, [_sent(f) for f in batch]) if flag.type == "read"}
    problems: list[Problem] = []
    for finding in (f for f in batch if f in objects):
        unit = range(finding.line, finding.line + len(_unit_lines(finding)))
        needed = [(finding.path, unit)]
        for path in finding.must_read[1:]:
            lines = (finding.repo / path).read_text(encoding="utf-8").splitlines()
            needed.append((path, range(1, len(lines) + 1)))
        read = _read_of(objects[finding])
        for path, lines in needed:
            if (_sent(finding).name, path) in flagged or not _listed(path, read, finding):
                continue
            unread = sorted(set(lines) - opened.get(path, set()))
            if path not in opened:
                problems.append(Problem(finding.name, "read", f"no Read call opened {path!r}; opened: {sorted(opened)!r}"))
            elif unread:
                problems.append(Problem(finding.name, "read", f"{path!r} only partly read; unread lines: {unread!r}"))
    return problems


def _cited(evidence: str, tree: str, finding: Finding) -> tuple[list[tuple[list[str], set[int]]], list[str]]:
    """What `evidence` cites, at `finding`'s trees, as `claims.reading.cited` reads it."""

    return cited(evidence, tree, finding.repo, _trees(finding))


def _caught_citing(report: dict[str, Any], claim: dict[str, Any], finding: Finding) -> bool:
    """Whether `check_reading` flags `claim` of `report` for citing a file,
    or lines of one, that `report`'s `read` doesn't give."""

    sent = _sent(finding)
    alone = {"finding": f"{sent.path}:{sent.line} ({sent.mode})", "read": report.get("read"), "claims": [claim]}
    return any(flag.type == "cited" for flag in check_reading([alone], [sent]))


def _unopened(report: dict[str, Any], finding: Finding, opened: dict[str, set[int]]) -> list[Problem]:
    """Each claim of `report`'s returned `true` on evidence no `Read` opened,
    none of the files it cites, or lines it cites of one that was, where
    `report`'s `read` gives what it cites, so `check_reading` doesn't flag
    it. Evidence naming no file `check_reading` flags itself."""

    reported = report.get("claims")
    problems: list[Problem] = []
    for claim in reported if isinstance(reported, list) else []:
        if not isinstance(claim, dict) or claim.get("verdict") != "true" or not claim.get("evidence"):
            continue
        if _caught_citing(report, claim, finding):
            continue
        cited, _ = _cited(str(claim["evidence"]), str(claim.get("tree", "")), finding)
        read = [(set[int]().union(*(opened[p] for p in paths if p in opened)), lines) for paths, lines in cited]
        read = [(have, lines) for have, lines in read if have]
        if cited and not read:
            problems.append(Problem(finding.name, "unopened", f"no cited file was opened: {claim!r}"))
        elif any(lines - have for have, lines in read):
            problems.append(Problem(finding.name, "unopened", f"cites lines that weren't opened: {claim!r}"))
    return problems


def _graded(batch: list[Finding], reply: Reply) -> dict[str, Any]:
    """What `reply` to `batch` came to: every problem in it, the claims
    each finding with one object listed, and the reply itself."""

    root = batch[0].repo
    problems = [Problem(BATCH, "call", reply.error)]
    objects: dict[Finding, dict[str, Any]] = {}
    if not reply.error:
        reports, bare = _extract_array(reply.message)
        reports = reply.message if reports is None else reports
        opened = _opened(reply.reads, root)
        objects = _objects(reports, batch)
        problems = _judge_batch(reports, batch) + _unread(batch, opened, reports)
        if isinstance(reports, list) and not bare:
            problems.append(Problem(BATCH, "format", "the final message holds the array, and more", COUNTED))
        for finding, report in objects.items():
            problems += _unopened(report, finding, opened)
    if len(batch) == 1:
        problems = [replace(p, finding=batch[0].name) for p in problems]
    listed = {f.name: report.get("claims") for f, report in objects.items()}
    return {
        "root": str(root),
        "findings": [f.name for f in batch],
        "problems": [asdict(p) for p in problems],
        "claims": {name: len(claims) if isinstance(claims, list) else 0 for name, claims in listed.items()},
        **asdict(reply),
    }


def _run(batch: list[Finding], system_prompt: str, model: str) -> dict[str, Any]:
    """Hand `batch` to one call, judge what comes back, and return the run as it is saved."""

    these = "this finding. Its root" if len(batch) == 1 else f"these {len(batch)} findings. Their root"
    findings = "\n\n".join(f.text for f in batch)
    reply = _call(f"Read {these} is this working directory.\n\n{findings}", system_prompt, model, batch[0].repo)
    return {
        "model": model,
        "effort": EFFORT,
        CONTRACT: hashlib.sha256(system_prompt.encode("utf-8")).hexdigest(),
        **_graded(batch, reply),
    }


def _rebuilt(names: list[str], root: Path) -> list[Finding]:
    """The batch a run of the findings `names` was built as, in `root`:
    one finding alone, a named batch, the first of a root's, or the stress
    pack."""

    dirs = {d.name: d for d in _fixture_dirs()}
    fixtures = {name.partition("/")[0] for name in names}
    if len(names) == 1:
        return [f for f in _copied(dirs[names[0].partition("/")[0]], root) if f.name == names[0]]
    if tuple(names) in BATCHES.values():
        return _named_batch(root, names, ROOTS["large"])
    if len(fixtures) == 1 and dirs[next(iter(fixtures))] in ROOTS.values():
        return _realistic_batch(root, len(names), dirs[next(iter(fixtures))])
    return _stress_batch(root)


def _old_root(run: dict[str, Any], batch: list[Finding]) -> str:
    """The root `run` was made in: as saved, or, for a run saved before
    the root was, the part of a `Read` call's path before a file the batch
    needs read."""

    if run.get("root"):
        return str(run["root"])
    for read in run["reads"]:
        file_path = str(read.get("file_path", ""))
        for path in (p for f in batch for p in f.must_read):
            if file_path.endswith(f"/{path}"):
                return file_path.removesuffix(f"/{path}")
    return ""


def _regraded(run: dict[str, Any]) -> dict[str, Any] | None:
    """`run`, saved earlier, graded again from its final message and `Read`
    calls, in a new root: its problems and claims as this harness finds
    them. `None` when its findings are no batch this harness builds."""

    known = {f.name for d in _fixture_dirs() for f in _findings(d)}
    if not run["findings"] or not set(run["findings"]) <= known:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        batch = _rebuilt(list(run["findings"]), root)
        if [f.name for f in batch] != run["findings"]:
            return None
        old = _old_root(run, batch)

        def moved(text: str) -> str:
            return text.replace(old, str(root)) if old else text

        reply = Reply(
            moved(str(run["message"])),
            [{**r, **({"file_path": moved(str(r["file_path"]))} if "file_path" in r else {})} for r in run["reads"]],
            run.get("usage", {}),
            str(run.get("error", "")),
        )
        graded = _graded(batch, reply)
    return {**run, "problems": graded["problems"], "claims": graded["claims"]}


def _bound(calls: list[tuple[int, int]]) -> float:
    """The one-sided 95% upper bound on the rate of readings with a problem
    not caught. Each call is its readings with one, and its readings.
    Calls are resampled whole, since one call's readings aren't
    independent. Resampling a few rare readings bounds them too low, and
    none at all at 0, so the bound is never below the one for none: the
    rate per reading with a 5% chance of none in that many readings."""

    none = 1 - 0.05 ** (1 / sum(readings for _, readings in calls))
    if not any(flagged for flagged, _ in calls):
        return none
    draw = random.Random(0)
    rates = sorted(
        sum(flagged for flagged, _ in drawn) / sum(readings for _, readings in drawn)
        for drawn in (draw.choices(calls, k=len(calls)) for _ in range(RESAMPLES))
    )
    return max(rates[math.ceil(0.95 * RESAMPLES) - 1], none)


def _calls(runs: list[dict[str, Any]]) -> list[tuple[int, int]]:
    """For each of `runs` with a reading, its readings with a problem not
    caught, and its readings. A failed call is each of its findings read
    with one."""

    calls: list[tuple[int, int]] = []
    for run in runs:
        if any(p["type"] == "call" for p in run["problems"]):
            calls.append((len(run["findings"]), len(run["findings"])))
        elif run["claims"]:
            flagged = {p["finding"] for p in run["problems"] if p["problem_class"] == REJECTING}
            calls.append((len(flagged & run["claims"].keys()), len(run["claims"])))
    return calls


def _rate(calls: list[tuple[int, int]]) -> float:
    return sum(flagged for flagged, _ in calls) / sum(readings for _, readings in calls)


def _tokens(run: dict[str, Any]) -> int:
    """The tokens `run`'s call spent: input, cache and output."""

    usage = run.get("usage", {})
    return sum(int(usage.get(field) or 0) for field in TOKENS)


def _cost(runs: list[dict[str, Any]], alone: list[dict[str, Any]]) -> tuple[float, float, int] | None:
    """The mean tokens per finding of `runs`, with a re-send for each
    finding a run has a caught problem in, priced at that finding's mean
    tokens alone; the mean per finding of `alone`'s readings; and how many
    re-sends.
    `None` when a finding of `runs` has no run alone to price it."""

    names = dict.fromkeys(name for run in runs for name in run["findings"])
    # A run alone with no report is no reading, so it prices nothing.
    spent = {name: [_tokens(r) for r in alone if r["findings"] == [name] and r["claims"]] for name in names}
    if not names or not all(spent.values()):
        return None
    mean = {name: sum(tokens) / len(tokens) for name, tokens in spent.items()}
    resends = [
        name
        for run in runs
        for name in {p["finding"] for p in run["problems"] if p["problem_class"] == CAUGHT}
        if name in mean
    ]
    batched = (sum(_tokens(r) for r in runs) + sum(mean[name] for name in resends)) / sum(len(r["findings"]) for r in runs)
    return batched, sum(mean.values()) / len(mean), len(resends)


def _same_findings(runs: list[dict[str, Any]], alone: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The runs in `alone` of one finding, when that finding is in `runs`."""

    names = {name for run in runs for name in run["findings"]}
    return [run for run in alone if len(run["findings"]) == 1 and run["findings"][0] in names]


def _failed(runs: list[dict[str, Any]], problem_class: str) -> int:
    """How many of `runs` have a problem of `problem_class`."""

    return sum(any(p["problem_class"] == problem_class for p in run["problems"]) for run in runs)


def _short_of_the_count(findings: list[str], alone: list[dict[str, Any]]) -> list[str]:
    """Each of `findings` not read alone as often as the others, by `alone`.
    A run alone with no report is no reading. The count is the most readings
    any finding has, and a finding short of it is run alone again, up to
    twice the count; one run more often than that leaves the size not
    accepted."""

    readings = Counter(name for run in alone for name in run["claims"])
    runs = Counter(run["findings"][0] for run in alone)
    count = max(readings[name] for name in findings)
    short: list[str] = []
    for name in findings:
        if count and runs[name] > 2 * count:
            short.append(f"{name} was run alone {runs[name]} times, over twice the count of {count}, so the size isn't accepted")
        elif readings[name] < count:
            short.append(f"{name} has {readings[name]} readings alone, short of the count of {count}: run it alone again")
    return short


def _short_of_the_bar(runs: list[dict[str, Any]], alone: list[dict[str, Any]]) -> list[str]:
    """Each way `runs`, of one size, fall short of ADR 0022's bar against `alone`."""

    alone = _same_findings(runs, alone)
    values: dict[str, set[Any]] = {}
    for name, field in (("model alias", "model"), ("effort", "effort"), ("contract digest", CONTRACT), *IDENTITY.items()):
        # A call that failed may name neither its model ID nor its version.
        values[name] = {r[field] for r in runs + alone if r[field] or all(p["type"] != "call" for p in r["problems"])}
    if differing := [name for name, found in values.items() if len(found) > 1]:
        return [f"the runs differ in their {' and '.join(differing)}"]
    short = [f"the runs don't say their {name}" for name, found in values.items() if found == {""}]
    findings = list(dict.fromkeys(name for run in runs for name in run["findings"]))
    calls = Counter(tuple(r["findings"]) for r in runs)
    of_size = {name: b for name, b in BATCHES.items() if len(b) == len(runs[0]["findings"])}
    batches = set(calls) == set(of_size.values())
    if not batches:
        short.append("they aren't a size's reading batches of the large root, which a cap has to rest on")
    if len(runs) != BATCHED_RUNS:
        short.append(f"{len(runs)} batched calls, where the count is fixed at {BATCHED_RUNS}")
    elif batches and len(of_size) > 1:
        per = BATCHED_RUNS // len(of_size)
        short += [
            f"{calls[b]} calls of batch {name}, where the count is fixed at {per}" for name, b in of_size.items() if calls[b] != per
        ]
    short += _short_of_the_count(findings, alone)
    readings = Counter(name for run in alone for name in run["claims"])
    count = max(readings[name] for name in findings)
    if count != ALONE_COUNT:
        short.append(f"{count} readings alone of a finding, where the count is fixed at {ALONE_COUNT}")
    for which, calls in (("batched", _calls(runs)), ("alone", _calls(alone))):
        if calls and (bound := _bound(calls)) > LIMIT:
            short.append(f"the bound {bound:.4f} on problems not caught {which} is over {LIMIT}")
    cost = _cost(runs, alone)
    if cost and cost[0] >= cost[1]:
        short.append(f"a batch spends {cost[0]:.0f} tokens per finding with its re-sends, not below {cost[1]:.0f} alone")
    return short


def _summary(runs: list[dict[str, Any]], alone: list[dict[str, Any]]) -> list[str]:
    """What `runs` came to, and, given runs `alone` to compare them with, whether they pass the bar."""

    failed = ", ".join(f"{_failed(runs, class_)} {class_}" for class_ in (REJECTING, CAUGHT, COUNTED))
    lines = [f"failed runs of {len(runs)}: {failed}"]
    failures = Counter(
        failure for run in runs for failure in {(p["finding"], p["type"], p["problem_class"]) for p in run["problems"]}
    )
    lines += [f"    {n} x {finding}: {type_} ({class_})" for (finding, type_, class_), n in sorted(failures.items())]
    alone = _same_findings(runs, alone)
    lines.append(f"claims listed per finding: {_claims_listed(runs)}" + (f", alone {_claims_listed(alone)}" if alone else ""))
    bounds = [
        f"{which} {_rate(calls):.4f}, bound {_bound(calls):.4f}"
        for which, calls in (("batched", _calls(runs)), ("alone", _calls(alone)))
        if calls
    ]
    if bounds:
        lines.append(f"not caught per finding read: {'; '.join(bounds)}; limit {LIMIT}")
    if cost := _cost(runs, alone):
        batched, by_itself, resends = cost
        lines.append(f"tokens per finding: batched {batched:.0f}, with {resends} re-sends; alone {by_itself:.0f}")
    if alone:
        short = _short_of_the_bar(runs, alone)
        lines += [f"doesn't pass the bar: {reason}" for reason in short] or ["passes the bar"]
    return lines


def _claims_listed(runs: list[dict[str, Any]]) -> str:
    listed = [n for run in runs for n in run["claims"].values()]
    return f"{sum(listed) / len(listed):.2f}" if listed else "none"


def _saved(directories: list[Path], parser: argparse.ArgumentParser) -> list[dict[str, Any]]:
    """The runs saved in `directories`, each graded again by this harness."""

    runs: list[dict[str, Any]] = []
    for directory in directories:
        files = sorted(directory.glob("*.json"))
        if not files:
            parser.error(f"{directory} holds no saved run")
        for file in files:
            run = json.loads(file.read_text(encoding="utf-8"))
            if not {"claims", "findings", "message", "reads", CONTRACT, *IDENTITY.values()} <= run.keys():
                parser.error(f"{file} was saved by an earlier harness, whose runs aren't judged by this bar")
            regraded = _regraded(run)
            if regraded is None:
                parser.error(f"{file} is of findings that are no batch this harness builds")
            runs.append(regraded)
    return runs


def _modes(args: argparse.Namespace) -> list[tuple[str, Callable[[Path], list[Finding]]]]:
    """Each call the mode `args` names makes: its label, and what builds its batch in a root."""

    if args.stress:
        return [("stress", _stress_batch)]
    if args.batch:
        return [(f"large-batch-{args.batch}", lambda root: _named_batch(root, BATCHES[args.batch], ROOTS["large"]))]
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
    mode.add_argument(
        "--batch",
        choices=BATCHES,
        help="Hand one call this named reading batch of the large root's findings, which a cap rests on.",
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
        return _exit_code(runs, alone)
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
            worst = next((c for c in (REJECTING, CAUGHT, COUNTED) if c in classes), "pass")
            print(f"[{worst.upper()}] {args.model} {label} {repeat}/{args.repeat}", flush=True)
            for p in run["problems"]:
                print(f"    {p['finding']}: {p['type']}: {p['detail']}", flush=True)
            if args.output_dir is not None:
                name = f"{re.sub(r'[ /]+', '-', label)}-{repeat:02d}.json"
                (args.output_dir / name).write_text(json.dumps(run, indent=2) + "\n", encoding="utf-8")
    print("\n".join(_summary(runs, alone)))
    return _exit_code(runs, alone)


def _exit_code(runs: list[dict[str, Any]], alone: list[dict[str, Any]]) -> int:
    """1 when `runs` don't pass the bar against `alone`, or, with no runs
    alone to judge the bar by, when any run has a problem not caught."""

    if alone:
        return int(bool(_short_of_the_bar(runs, alone)))
    return int(_failed(runs, REJECTING) > 0)


if __name__ == "__main__":
    raise SystemExit(main())
