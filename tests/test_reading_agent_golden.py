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

"""The reading-agent golden harness's own judging, without a live call.

These hold `scripts/run_reading_agent_golden.py` to what #274 and #281
ask of it: one object per finding, keyed by its `file:line` and mode, each
judged as it would be alone and every problem reported; batches of
findings that share subjects; and a call that is isolated. `claude`
itself is a script that records how it was called.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from scripts.run_reading_agent_golden import (  # noqa: E402
    BATCH,
    FIXTURES_DIR,
    REPO_ROOT,
    SIZES,
    Finding,
    Problem,
    _copied,
    _extract_array,
    _findings,
    _fixture_dirs,
    _judge,
    _judge_batch,
    _prefixed,
    _realistic_batch,
    _stress_batch,
    _unit,
    _unread,
    main,
)


def _finding(path: str = "docs/design.md", line: int = 1, mode: str = "stale-claims") -> Finding:
    return Finding(
        name="f",
        text=f"[advisory] {path}:{line} ({mode}) 'Caching' names code — cache.py 2 commits\n\nSubjects: cache.py\n",
        expected={"false_claims": [], "outside_unit": ["written to disk"]},
        repo=Path("/root-of-the-run"),
        path=path,
        line=line,
        mode=mode,
        subjects=["cache.py"],
    )


def _report(finding: str, verdict: str = "true", read: list[str] | None = None) -> dict[str, Any]:
    return {
        "finding": finding,
        "claims": [{"claim": "`get` returns `None`", "verdict": verdict, "kind": "current", "evidence": "cache.py:7"}],
        "read": ["f01/docs/design.md", "f01/cache.py"] if read is None else read,
        "searched": [],
        "note": "",
    }


class ExtractArrayTest(unittest.TestCase):
    def test_an_array_after_prose_is_read(self) -> None:
        self.assertEqual(_extract_array('Here:\n```json\n[{"finding": "a.md:1"}]\n```'), [{"finding": "a.md:1"}])

    def test_a_bare_object_is_not_read_as_its_claims_array(self) -> None:
        self.assertIsNone(_extract_array('{"finding": "a.md:1", "claims": [{"claim": "x"}]}'))


class PrefixedTest(unittest.TestCase):
    def test_every_path_the_finding_names_moves_under_the_prefix(self) -> None:
        moved = _prefixed(_finding(), "f01")
        self.assertEqual(moved.path, "f01/docs/design.md")
        self.assertEqual(moved.subjects, ["f01/cache.py"])
        self.assertIn("[advisory] f01/docs/design.md:1 (stale-claims)", moved.text)
        self.assertIn("Subjects: f01/cache.py", moved.text)
        self.assertIn("— f01/cache.py 2 commits", moved.text)


# The two reports run 2 on #281 returned for the opposite-verdicts pair, as
# recorded: each verdict is the one the other finding needed, and the cited
# lines are another fixture's `cache.py`.
RECORDED_SWAP: list[dict[str, Any]] = [
    {
        "finding": "f06/docs/design.md:1 (stale-claims)",
        "claims": [
            {
                "claim": "When the cache is full, `put` of a new key evicts the oldest entry first.",
                "verdict": "false",
                "kind": "current",
                "kind_evidence": "",
                "tree": "root",
                "tree_line": "",
                "evidence": "f06/cache.py:10-12",
                "reasoning": "The code evicts next(reversed(...)), which is the newest entry.",
            },
            {
                "claim": "`get` never evicts anything.",
                "verdict": "true",
                "kind": "current",
                "kind_evidence": "",
                "tree": "root",
                "tree_line": "",
                "evidence": "f06/cache.py:6-7",
                "reasoning": "get only reads from the dict.",
            },
        ],
        "read": ["f06/docs/design.md", "f06/cache.py"],
        "searched": [],
        "note": "Oldest-eviction claim false: the code evicts the newest. get claim true.",
    },
    {
        "finding": "f06/docs/faq.md:1 (stale-claims)",
        "claims": [
            {
                "claim": "When the cache is full, `put` of a new key evicts the newest entry first.",
                "verdict": "true",
                "kind": "current",
                "kind_evidence": "",
                "tree": "root",
                "tree_line": "",
                "evidence": "f06/cache.py:10-12",
                "reasoning": "next(reversed(self._entries)) is the most recently inserted entry.",
            },
            {
                "claim": "`get` never evicts anything.",
                "verdict": "true",
                "kind": "current",
                "kind_evidence": "",
                "tree": "root",
                "tree_line": "",
                "evidence": "f06/cache.py:6-7",
                "reasoning": "get only reads from the dict.",
            },
        ],
        "read": ["f06/docs/faq.md", "f06/cache.py"],
        "searched": [],
        "note": "Both Eviction claims hold at root.",
    },
]


def _types(problems: list[Problem]) -> list[tuple[str, str]]:
    return [(p.finding, p.type) for p in problems]


class JudgeBatchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.findings = [
            replace(_prefixed(_finding(), "f01"), name="first"),
            replace(_prefixed(_finding("docs/faq.md", 3), "f02"), name="second"),
        ]
        self.first = _report("f01/docs/design.md:1 (stale-claims)")
        self.second = _report("f02/docs/faq.md:3 stale-claims", read=["f02/docs/faq.md", "f02/cache.py"])

    def test_one_true_object_per_finding_passes(self) -> None:
        self.assertEqual(_judge_batch([self.first, self.second], self.findings), [])

    def test_a_bare_object_is_not_an_array(self) -> None:
        self.assertEqual(_types(_judge_batch(self.first, self.findings)), [(BATCH, "matching")])

    def test_a_missing_finding_fails(self) -> None:
        self.assertEqual(_types(_judge_batch([self.second], self.findings)), [("first", "matching")])

    def test_a_duplicated_finding_fails(self) -> None:
        self.assertEqual(
            _types(_judge_batch([self.first, self.first, self.second], self.findings)), [("first", "matching")]
        )

    def test_an_unrecognised_finding_fails(self) -> None:
        stray = _report("f09/docs/other.md:1 stale-claims")
        problems = _judge_batch([self.first, self.second, stray, "prose"], self.findings)
        self.assertEqual(_types(problems), [(BATCH, "matching"), (BATCH, "matching")])
        self.assertIn("f09", problems[0].detail)

    def test_two_failing_findings_are_both_reported(self) -> None:
        self.first["claims"][0]["verdict"] = "false"
        self.second["claims"][0]["verdict"] = "not checked"
        self.assertEqual(
            _types(_judge_batch([self.first, self.second], self.findings)),
            [("first", "verdict"), ("second", "verdict")],
        )

    def test_a_matching_failure_does_not_hide_another_findings_verdict(self) -> None:
        self.second["claims"][0]["verdict"] = "false"
        self.assertEqual(
            _types(_judge_batch([self.second], self.findings)), [("first", "matching"), ("second", "verdict")]
        )

    def test_a_subject_missing_from_one_findings_read_fails(self) -> None:
        self.first["read"] = ["f01/docs/design.md"]
        problems = _judge_batch([self.first, self.second], self.findings)
        self.assertEqual(_types(problems), [("first", "read")])
        self.assertIn("f01/cache.py", problems[0].detail)

    def test_the_recorded_verdict_swap_fails_both_findings(self) -> None:
        pair = [_prefixed(f, "f06") for f in _findings(FIXTURES_DIR / "shared_subject_opposite_verdicts")]
        self.assertEqual(
            _types(_judge_batch(RECORDED_SWAP, pair)),
            [
                ("shared_subject_opposite_verdicts/design.finding.txt", "verdict"),
                ("shared_subject_opposite_verdicts/faq.finding.txt", "verdict"),
            ],
        )


class JudgeTest(unittest.TestCase):
    """One report, judged against its finding."""

    def setUp(self) -> None:
        self.finding = replace(
            _finding(),
            expected={
                "false_claims": ["oldest"],
                "not_checked": ["reload"],
                "outside_unit": ["written to disk"],
                "kinds": {"oldest": "intended"},
            },
        )
        self.report = _report("docs/design.md:1 (stale-claims)", read=["docs/design.md", "cache.py"])
        self.report["claims"] += [
            {"claim": "evicts the oldest entry", "verdict": "false", "kind": "intended", "evidence": "cache.py:10"},
            {"claim": "a reload is quick", "verdict": "not checked", "kind": "current", "evidence": "cache.py:1"},
        ]

    def test_a_report_as_expected_has_no_problem(self) -> None:
        self.assertEqual(_judge(self.report, self.finding), [])

    def test_every_problem_in_one_report_is_reported(self) -> None:
        self.report["claims"][0]["verdict"] = "false"
        self.report["claims"][1].update(verdict="true", kind="current")
        self.report["claims"][2]["evidence"] = ""
        self.report["claims"].append({"claim": "Nothing is written to disk.", "verdict": "true", "evidence": "x"})
        self.report["read"] = ["cache.py"]
        self.assertEqual(
            sorted(p.type for p in _judge(self.report, self.finding)),
            ["kind", "read", "unit", "verdict", "verdict", "verdict"],
        )

    def test_a_claim_from_outside_the_unit_is_one_problem(self) -> None:
        self.report["claims"].append({"claim": "Nothing is written to disk.", "verdict": "false"})
        self.assertEqual([p.type for p in _judge(self.report, self.finding)], ["unit"])

    def test_a_report_listing_no_claims_is_one_verdict_problem(self) -> None:
        self.report["claims"] = []
        self.assertEqual([p.type for p in _judge(self.report, self.finding)], ["verdict"])

    def test_a_claim_reported_both_as_expected_and_not_is_a_problem(self) -> None:
        self.report["claims"].append({**self.report["claims"][1], "verdict": "true", "kind": "current"})
        self.assertEqual(sorted(p.type for p in _judge(self.report, self.finding)), ["kind", "verdict"])

    def test_a_claim_the_fixture_gives_no_kind_has_to_be_current(self) -> None:
        self.report["claims"][0]["kind"] = "past"
        self.assertEqual([p.type for p in _judge(self.report, self.finding)], ["kind"])

    def test_a_claim_given_a_kind_has_to_be_reported(self) -> None:
        finding = replace(self.finding, expected={**self.finding.expected, "kinds": {"never evicts": "current"}})
        self.report["claims"][1]["kind"] = "current"
        self.assertEqual([p.type for p in _judge(self.report, finding)], ["kind"])

    def test_a_malformed_claim_is_a_verdict_problem(self) -> None:
        self.report["claims"].append("not an object")
        self.assertEqual([p.type for p in _judge(self.report, self.finding)], ["verdict"])

    def test_read_may_name_a_path_under_the_root_or_absolutely(self) -> None:
        self.report["read"] = ["./docs/design.md", f"{self.finding.repo}/cache.py (full)"]
        self.assertEqual(_judge(self.report, self.finding), [])

    def test_a_copy_in_a_tree_is_not_the_roots_file(self) -> None:
        tree = ".claims/trees/4f1c2d3e"
        finding = replace(self.finding, expected={**self.finding.expected, "reads": [f"{tree}/cache.py"]})
        both = ["docs/design.md", "cache.py", f"{tree}/cache.py"]
        for read, missing in ((both, 0), (both[:2], 1), ([both[0], both[2]], 1)):
            self.report["read"] = read
            self.assertEqual([p.type for p in _judge(self.report, finding)], ["read"] * missing, read)

    def test_a_tree_read_may_be_named_by_its_commit(self) -> None:
        finding = replace(
            self.finding, expected={**self.finding.expected, "reads": [".claims/trees/4f1c2d3e5a/cache.py"]}
        )
        self.report["read"] = ["docs/design.md", "cache.py", "cache.py in tree 4f1c2d3"]
        self.assertEqual(_judge(self.report, finding), [])


    def test_a_tree_read_named_by_its_commit_or_role_is_not_the_roots_file(self) -> None:
        commit = "4f1c2d3e5a"
        tree = f".claims/trees/{commit}"
        finding = replace(
            self.finding,
            text=f"{self.finding.text}\nbefore {commit} /root-of-the-run/{tree}",
            expected={**self.finding.expected, "reads": [f"{tree}/cache.py"]},
        )
        for entry, missing in (
            ("cache.py at the before tree 4f1c2d3", 1),
            ("cache.py (before tree)", 1),
            ("cache.py (root, and before 4f1c2d3)", 0),
            ("cache.py (root and before tree)", 0),
        ):
            self.report["read"] = ["docs/design.md", entry]
            self.assertEqual([p.type for p in _judge(self.report, finding)], ["read"] * missing, entry)


class UnreadTest(unittest.TestCase):
    """The agent's own `Read` calls, whatever its report lists."""

    def test_every_path_no_read_call_opened_is_reported(self) -> None:
        tree_copy = ".claims/trees/4f1c2d3e/cache.py"
        finding = replace(_finding(), expected={**_finding().expected, "reads": [tree_copy]})
        problems = _unread([finding], [f"{finding.repo}/{tree_copy}"])
        self.assertEqual([p.type for p in problems], ["read", "read"])
        self.assertIn("docs/design.md", problems[0].detail)
        self.assertIn("'cache.py'", problems[1].detail)

    def test_relative_and_absolute_read_calls_both_count(self) -> None:
        finding = _finding()
        self.assertEqual(_unread([finding], ["docs/design.md", f"{finding.repo}/cache.py"]), [])


def _opposite_verdicts(batch: list[Finding]) -> bool:
    """Whether two findings in `batch` share a subject, one all true and one holding a false claim."""

    clean = [f for f in batch if not f.expected["false_claims"] and not f.expected.get("not_checked")]
    return any(set(t.subjects) & set(f.subjects) for t in clean for f in batch if f.expected["false_claims"])


class StressBatchTest(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.batch = _stress_batch(self.root)

    def test_it_is_every_unrelated_fixtures_findings(self) -> None:
        self.assertEqual(len(self.batch), 10)
        self.assertNotIn("shared_subject_batch", {f.name.split("/")[0] for f in self.batch})

    def test_a_pair_shares_a_subject_and_needs_opposite_verdicts(self) -> None:
        self.assertTrue(_opposite_verdicts(self.batch))

    def test_each_findings_paths_exist_in_its_root(self) -> None:
        for finding in self.batch:
            self.assertEqual(finding.repo, self.root)
            for path in finding.must_read:
                self.assertTrue((self.root / path).is_file(), path)


class RealisticBatchTest(unittest.TestCase):
    def _batch(self, size: int) -> list[Finding]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return _realistic_batch(Path(tmp.name).resolve(), size)

    def test_the_sizes_are_those_the_cap_is_measured_at(self) -> None:
        self.assertEqual(SIZES, (2, 3, 5, 10))

    def test_each_size_holds_that_many_findings(self) -> None:
        for size in SIZES:
            self.assertEqual(len(self._batch(size)), size)

    def test_each_size_holds_a_pair_needing_opposite_verdicts(self) -> None:
        for size in SIZES:
            self.assertTrue(_opposite_verdicts(self._batch(size)), size)

    def test_no_size_packs_unrelated_findings(self) -> None:
        for size in SIZES:
            batch = self._batch(size)
            joined = {batch[0]}
            while more := {f for f in batch if f not in joined and any(set(f.subjects) & set(j.subjects) for j in joined)}:
                joined |= more
            self.assertEqual(len(joined), size)

    def test_every_finding_has_the_fixtures_one_root_and_its_paths_exist_there(self) -> None:
        batch = self._batch(10)
        self.assertEqual(len({f.repo for f in batch}), 1)
        for finding in batch:
            for path in finding.must_read:
                self.assertTrue((finding.repo / path).is_file(), path)

    def test_the_root_is_outside_this_repository(self) -> None:
        self.assertFalse(self._batch(2)[0].repo.is_relative_to(REPO_ROOT))

    def test_every_expected_fragment_is_in_its_unit_and_no_outside_one_is(self) -> None:
        for finding in self._batch(10):
            expected = finding.expected
            for fragment in [*expected["false_claims"], *expected.get("not_checked", []), *expected["kinds"]]:
                self.assertIn(fragment, _unit(finding), finding.name)
            for fragment in expected["outside_unit"]:
                self.assertNotIn(fragment, _unit(finding), finding.name)

    def test_a_claim_of_another_findings_is_from_outside_the_unit(self) -> None:
        batch = {f.name.split("/")[1].split(".")[0]: f for f in self._batch(10)}
        for into, leaked in (
            ("02-faq", "`put` of a new key evicts the oldest entry first."),
            ("01-design", "`put` of a new key evicts the newest entry\nfirst."),
            ("01-design", "Its capacity is 128."),
            ("07-api-totalising", "`delete` now ignores a key the cache doesn't hold."),
        ):
            report = _passing_report(batch[into])
            self.assertEqual(_judge(report, batch[into]), [])
            report["claims"].append({"claim": leaked, "verdict": "true", "kind": "current", "evidence": "x:1"})
            self.assertEqual([p.type for p in _judge(report, batch[into])], ["unit"], leaked)

    def test_one_finding_carries_a_tree_where_a_shared_path_differs(self) -> None:
        batch = self._batch(10)
        carrying = [f for f in batch if "Trees, named from" in f.text]
        self.assertEqual(len(carrying), 1)
        (finding,) = carrying
        for tree_path in finding.expected["reads"]:
            commit, _, shared = tree_path.removeprefix(".claims/trees/").partition("/")
            self.assertIn(f"{commit} {finding.repo}/.claims/trees/{commit}", finding.text)
            self.assertNotEqual((finding.repo / tree_path).read_text(), (finding.repo / shared).read_text())
            self.assertTrue(any(shared in f.subjects for f in batch if f is not finding))
        self.assertIn(finding.name, {f.name for f in self._batch(3)})

    def test_each_tree_a_finding_names_is_there(self) -> None:
        for finding in self._batch(10):
            self.assertNotIn("{root}", finding.text)
            for named in re.findall(r"^(?:written|before) \w+ (\S+)$", finding.text, re.M):
                self.assertTrue(Path(named).is_dir(), named)


class AloneTest(unittest.TestCase):
    def test_every_fixtures_every_finding_is_run_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            roots = [Path(tmp).resolve() / d.name for d in _fixture_dirs()]
            found = [f for d, root in zip(_fixture_dirs(), roots, strict=True) for f in _copied(d, root)]
            self.assertEqual(len(found), 20)
            for finding in found:
                for path in finding.must_read:
                    self.assertTrue((finding.repo / path).is_file(), path)


# Stands in for the `claude` binary: records how it was called, and prints
# the stream `reply.json` beside it says to.
FAKE_CLAUDE = """#!{python}
import json, os, sys
from pathlib import Path
here = Path(__file__).parent
with (here / "calls.jsonl").open("a") as calls:
    calls.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd()}}) + "\\n")
reply = json.loads((here / "reply.json").read_text())
if "exit" in reply:
    print(reply["exit"], file=sys.stderr)
    raise SystemExit(1)
print(json.dumps({{"type": "system", "subtype": "init"}}))
for path in reply["reads"]:
    block = {{"type": "tool_use", "name": "Read", "input": {{"file_path": path}}}}
    print(json.dumps({{"type": "assistant", "message": {{"content": [block]}}}}))
print(json.dumps({{"type": "result", "result": reply["message"], "usage": {{"output_tokens": 7}}}}))
"""


def _passing_report(finding: Finding) -> dict[str, Any]:
    expected = finding.expected
    verdicts = {f: "false" for f in expected["false_claims"]} | {f: "not checked" for f in expected.get("not_checked", [])}
    claims = [
        {"claim": f, "verdict": verdicts.get(f, "true"), "kind": expected.get("kinds", {}).get(f, "current"), "evidence": "x:1"}
        for f in dict.fromkeys([*verdicts, *expected.get("kinds", {})])
    ]
    return {"finding": f"{finding.path}:{finding.line} ({finding.mode})", "claims": claims, "read": finding.must_read}


class MainTest(unittest.TestCase):
    """The command line, with `claude` replaced by a script that records its call."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.bin = Path(tmp.name) / "bin"
        self.bin.mkdir()
        self.out = Path(tmp.name) / "out"
        fake = self.bin / "claude"
        fake.write_text(FAKE_CLAUDE.format(python=sys.executable), encoding="utf-8")
        fake.chmod(0o755)
        patcher = mock.patch.dict(os.environ, {"PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}"})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.batch = _findings(FIXTURES_DIR / "shared_subject_batch")[:2]
        self._reply([_passing_report(f) for f in self.batch], [p for f in self.batch for p in f.must_read])

    def _reply(self, reports: Any, reads: list[str]) -> None:
        reply = {"message": json.dumps(reports), "reads": reads}
        (self.bin / "reply.json").write_text(json.dumps(reply), encoding="utf-8")

    def _main(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                code = main(list(args))
            except SystemExit as exc:
                code = int(exc.code or 0)
        return code, out.getvalue()

    def _calls(self) -> list[dict[str, Any]]:
        recorded = self.bin / "calls.jsonl"
        return [json.loads(line) for line in recorded.read_text().splitlines()] if recorded.exists() else []

    def test_a_call_has_only_the_contract_and_the_three_tools(self) -> None:
        self._main("--batch-size", "2")
        (call,) = self._calls()
        argv: list[str] = call["argv"]
        self.assertIn("--safe-mode", argv)
        self.assertIn("--strict-mcp-config", argv)
        self.assertEqual(argv[argv.index("--tools") + 1], "Read,Glob,Grep")
        system_prompt = argv[argv.index("--system-prompt") + 1]
        self.assertTrue(system_prompt.startswith("You read each advisory finding"))
        self.assertNotIn("--append-system-prompt", argv)
        self.assertNotIn("--mcp-config", argv)
        self.assertFalse(Path(call["cwd"]).resolve().is_relative_to(REPO_ROOT))

    def test_every_finding_alone_is_isolated_too(self) -> None:
        self._main()
        calls = self._calls()
        self.assertEqual(len(calls), 20)
        self.assertEqual(len({c["cwd"] for c in calls}), 20)
        for call in calls:
            self.assertIn("--safe-mode", call["argv"])
            self.assertFalse(Path(call["cwd"]).resolve().is_relative_to(REPO_ROOT))

    def test_a_batch_passes_when_each_finding_does(self) -> None:
        code, out = self._main("--batch-size", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("failed runs: 0 of 1", out)

    def test_repeats_count_failed_runs_and_failures_by_finding_and_type(self) -> None:
        reports = [_passing_report(f) for f in self.batch]
        for report in reports:
            report["claims"][0]["verdict"] = "not checked"
        self._reply(reports, [p for f in self.batch for p in f.must_read])
        code, out = self._main("--batch-size", "2", "--repeat", "3")
        self.assertEqual(code, 1)
        self.assertEqual(len(self._calls()), 3)
        self.assertIn("failed runs: 3 of 3", out)
        self.assertIn("3 x shared_subject_batch/01-design.finding.txt: verdict", out)
        self.assertIn("3 x shared_subject_batch/02-faq.finding.txt: verdict", out)

    def test_a_run_whose_call_fails_is_a_failed_run_of_its_own_type(self) -> None:
        (self.bin / "reply.json").write_text(json.dumps({"exit": "usage limit"}), encoding="utf-8")
        code, out = self._main("--batch-size", "2", "--repeat", "2")
        self.assertEqual(code, 1)
        self.assertIn("failed runs: 2 of 2", out)
        self.assertIn("2 x the whole call: call", out)
        self.assertIn("usage limit", out)

    def test_each_runs_message_and_reads_are_saved(self) -> None:
        self._main("--batch-size", "2", "--repeat", "2", "--output-dir", str(self.out))
        saved = sorted(self.out.iterdir())
        self.assertEqual(len(saved), 2)
        run = json.loads(saved[0].read_text(encoding="utf-8"))
        self.assertEqual(json.loads(run["message"]), [_passing_report(f) for f in self.batch])
        self.assertEqual([r["file_path"] for r in run["reads"]], [p for f in self.batch for p in f.must_read])
        self.assertEqual(run["usage"], {"output_tokens": 7})
        self.assertEqual(run["problems"], [])

    def test_a_failed_runs_message_is_saved_with_its_problems(self) -> None:
        self._reply([], [])
        self._main("--batch-size", "2", "--output-dir", str(self.out))
        (saved,) = self.out.iterdir()
        run = json.loads(saved.read_text(encoding="utf-8"))
        self.assertEqual(run["message"], "[]")
        self.assertEqual({p["type"] for p in run["problems"]}, {"matching", "read"})

    def test_every_finding_alone_is_saved_to_a_file_of_its_own(self) -> None:
        self._main("--output-dir", str(self.out))
        self.assertEqual(len(list(self.out.iterdir())), 20)

    def test_a_call_failing_for_a_finding_alone_is_reported_against_it(self) -> None:
        (self.bin / "reply.json").write_text(json.dumps({"exit": "usage limit"}), encoding="utf-8")
        _, out = self._main()
        self.assertIn("1 x known_true/finding.txt: call", out)
        self.assertNotIn(BATCH, out)

    def test_the_stress_run_is_one_call_of_the_unrelated_findings(self) -> None:
        code, out = self._main("--stress")
        self.assertEqual(code, 1)
        (call,) = self._calls()
        self.assertIn("f08/docs/design.md:1", " ".join(call["argv"]))

    def test_an_output_directory_holding_files_is_refused_before_any_call(self) -> None:
        self.out.mkdir()
        (self.out / "earlier.json").write_text("{}", encoding="utf-8")
        code, _ = self._main("--batch-size", "2", "--output-dir", str(self.out))
        self.assertEqual(code, 2)
        self.assertEqual(self._calls(), [])

    def test_a_size_the_cap_is_not_measured_at_no_repeats_and_two_modes_are_refused(self) -> None:
        for args in (["--batch-size", "4"], ["--repeat", "0"], ["--batch-size", "2", "--stress"]):
            code, _ = self._main(*args)
            self.assertEqual(code, 2, args)
        self.assertEqual(self._calls(), [])


if __name__ == "__main__":
    unittest.main()
