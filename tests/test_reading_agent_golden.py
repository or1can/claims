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
import copy
import io
import json
import os
import re
import sys
import tempfile
import unittest
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from scripts.run_reading_agent_golden import (  # noqa: E402
    BATCH,
    COMPARED,
    COUNTED,
    EFFORT,
    FIXTURES_DIR,
    REJECTING,
    REPO_ROOT,
    ROOTS,
    SIZES,
    Finding,
    Problem,
    _bound,
    _copied,
    _extract_array,
    _findings,
    _fixture_dirs,
    _judge,
    _judge_batch,
    _opened,
    _prefixed,
    _short_of_the_bar,
    _summary,
    _realistic_batch,
    _stress_batch,
    _unit,
    _unopened,
    _unread,
    main,
)


SMALL = ROOTS["small"]
LARGE = ROOTS["large"]


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


# The reports of #284's batch of 2, run 5, as saved, less the fields no
# judging reads: the first lists the next section's sentence.
RECORDED_EXTRA_SENTENCE: list[dict[str, Any]] = [
    {
        "finding": "docs/design.md:1 (stale-claims)",
        "claims": [
            {
                "claim": "When the cache is full, `put` of a new key evicts the oldest entry first.",
                "verdict": "true",
                "kind": "current",
                "tree": "root (working directory)",
                "evidence": "cache.py:9-13",
            },
            {
                "claim": "`get` never evicts anything.",
                "verdict": "true",
                "kind": "current",
                "tree": "root (working directory)",
                "evidence": "cache.py:6-7",
            },
            {
                "claim": "Nothing is written to disk.",
                "verdict": "true",
                "kind": "current",
                "tree": "root (working directory)",
                "evidence": "cache.py:1-16",
                "reasoning": "This sentence is in the next section ('Storage'), outside the unit.",
            },
        ],
        "read": ["docs/design.md", "cache.py"],
    },
    {
        "finding": "docs/faq.md:1 (stale-claims)",
        "claims": [
            {
                "claim": "When the cache is full, `put` of a new key evicts the newest entry first.",
                "verdict": "false",
                "kind": "current",
                "tree": "root (working directory)",
                "evidence": "cache.py:10-12",
            },
            {
                "claim": "`get` never evicts anything.",
                "verdict": "true",
                "kind": "current",
                "tree": "root (working directory)",
                "evidence": "cache.py:6-7",
            },
        ],
        "read": ["docs/faq.md", "cache.py"],
    },
]


def _types(problems: list[Problem]) -> list[tuple[str, str]]:
    return [(p.finding, p.type) for p in problems]


def _classes(problems: list[Problem]) -> list[tuple[str, str]]:
    return [(p.type, p.problem_class) for p in problems]


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

    def test_the_recorded_verdict_swap_is_rejecting_for_the_false_claim_returned_true(self) -> None:
        pair = [_prefixed(f, "f06") for f in _findings(FIXTURES_DIR / "shared_subject_opposite_verdicts")]
        self.assertEqual(
            [p.problem_class for p in _judge_batch(RECORDED_SWAP, pair)],
            [COUNTED, REJECTING],
        )

    def test_the_recorded_extra_sentence_is_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            problems = _judge_batch(RECORDED_EXTRA_SENTENCE, _realistic_batch(Path(tmp).resolve(), 2, SMALL))
        self.assertEqual(
            [(p.finding, p.type, p.problem_class) for p in problems],
            [("shared_subject_batch/01-design.finding.txt", "unit-own-page", COUNTED)],
        )

    def test_a_matching_problem_is_counted(self) -> None:
        for reports in (self.first, [self.second], [self.first, self.first, self.second], ["x", self.first, self.second]):
            self.assertEqual(_classes(_judge_batch(reports, self.findings)), [("matching", COUNTED)])


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
            ["kind", "read", "unit-own-page", "verdict", "verdict", "verdict"],
        )

    def test_a_claim_from_outside_the_unit_is_one_problem(self) -> None:
        self.report["claims"].append({"claim": "Nothing is written to disk.", "verdict": "false"})
        self.assertEqual(_classes(_judge(self.report, self.finding)), [("unit-own-page", COUNTED)])

    def test_another_findings_claim_is_rejecting_though_it_is_on_the_same_page(self) -> None:
        finding = replace(self.finding, expected={**self.finding.expected, "elsewhere": ["written to disk"]})
        self.report["claims"].append({"claim": "Nothing is written to disk.", "verdict": "false"})
        self.assertEqual(_classes(_judge(self.report, finding)), [("unit-other", REJECTING)])

    def test_a_verdict_is_classed_by_what_it_would_hide(self) -> None:
        for index, verdict, problem_class in (
            (1, "true", REJECTING),
            (1, "not checked", REJECTING),
            (0, "false", COUNTED),
            (0, "not checked", REJECTING),
            (2, "true", REJECTING),
            (2, "false", REJECTING),
        ):
            report = copy.deepcopy(self.report)
            report["claims"][index]["verdict"] = verdict
            self.assertEqual(_classes(_judge(report, self.finding)), [("verdict", problem_class)], (index, verdict))

    def test_a_kind_is_classed_by_whether_it_sends_the_reading_to_an_old_tree(self) -> None:
        finding = replace(
            self.finding,
            expected={**self.finding.expected, "kinds": {"oldest": "intended", "reload": "past"}},
        )
        self.report["claims"][2]["kind"] = "past"
        self.assertEqual(_judge(self.report, finding), [])
        for index, kind, problem_class in (
            (0, "past", REJECTING),
            (0, "superseded", REJECTING),
            (0, "intended", COUNTED),
            (1, "superseded", REJECTING),
            (1, "past", REJECTING),
            (1, "current", COUNTED),
            (2, "current", COUNTED),
            (2, "superseded", COUNTED),
        ):
            report = copy.deepcopy(self.report)
            report["claims"][index]["kind"] = kind
            self.assertEqual(_classes(_judge(report, finding)), [("kind", problem_class)], (index, kind))

    def test_a_claim_not_reported_is_rejecting(self) -> None:
        for claim in (1, 2):
            report = copy.deepcopy(self.report)
            del report["claims"][claim]
            self.assertEqual({p.problem_class for p in _judge(report, self.finding)}, {REJECTING})

    def test_a_problem_in_no_list_is_rejecting(self) -> None:
        no_evidence, no_claims, malformed, unlisted = (copy.deepcopy(self.report) for _ in range(4))
        no_evidence["claims"][0]["evidence"] = ""
        no_claims["claims"] = []
        malformed["claims"].append("not an object")
        unlisted["read"] = ["docs/design.md"]
        for report, type_ in ((no_evidence, "verdict"), (no_claims, "verdict"), (malformed, "verdict"), (unlisted, "read")):
            self.assertEqual(_classes(_judge(report, self.finding)), [(type_, REJECTING)])

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


class ReadingTest(unittest.TestCase):
    """The agent's own `Read` calls, whatever its report lists."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.tree_copy = ".claims/trees/4f1c2d3e/cache.py"
        for path, text in (
            ("docs/design.md", "# Design\n\nAbout it.\n\n## Caching\n\n`get` returns `None`.\n\n## Storage\n\nNone.\n"),
            ("cache.py", "x\n" * 40),
            ("other.py", "x\n" * 40),
            (self.tree_copy, "x\n" * 40),
        ):
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_text(text, encoding="utf-8")
        self.finding = replace(_finding(line=5), repo=self.root)

    def _opened(self, *reads: tuple[str, int, int]) -> dict[str, set[int]]:
        return _opened([{"file_path": path, "lines": [first, last]} for path, first, last in reads], self.root)


class UnreadTest(ReadingTest):
    def test_every_path_no_read_call_opened_is_rejecting(self) -> None:
        finding = replace(self.finding, expected={**self.finding.expected, "reads": [self.tree_copy]})
        problems = _unread([finding], self._opened((f"{self.root}/{self.tree_copy}", 1, 40)))
        self.assertEqual(_classes(problems), [("read", REJECTING), ("read", REJECTING)])
        self.assertIn("docs/design.md", problems[0].detail)
        self.assertIn("'cache.py'", problems[1].detail)

    def test_relative_and_absolute_read_calls_both_count(self) -> None:
        opened = self._opened(("docs/design.md", 1, 11), (f"{self.root}/cache.py", 1, 40))
        self.assertEqual(_unread([self.finding], opened), [])

    def test_a_subject_only_partly_read_is_rejecting(self) -> None:
        problems = _unread([self.finding], self._opened(("docs/design.md", 1, 11), ("cache.py", 1, 30)))
        self.assertEqual(_classes(problems), [("read", REJECTING)])
        self.assertIn("31", problems[0].detail)

    def test_a_tree_only_partly_read_is_rejecting(self) -> None:
        finding = replace(self.finding, expected={**self.finding.expected, "reads": [self.tree_copy]})
        opened = self._opened(("docs/design.md", 1, 11), ("cache.py", 1, 40), (self.tree_copy, 2, 40))
        self.assertEqual(_classes(_unread([finding], opened)), [("read", REJECTING)])

    def test_several_reads_together_cover_a_subject(self) -> None:
        opened = self._opened(("docs/design.md", 1, 11), ("cache.py", 1, 20), ("cache.py", 21, 41))
        self.assertEqual(_unread([self.finding], opened), [])

    def test_the_unit_is_read_by_its_own_lines_not_its_whole_page(self) -> None:
        self.assertEqual(_unread([self.finding], self._opened(("docs/design.md", 5, 7), ("cache.py", 1, 40))), [])
        problems = _unread([self.finding], self._opened(("docs/design.md", 5, 6), ("cache.py", 1, 40)))
        self.assertEqual(_classes(problems), [("read", REJECTING)])

    def test_a_read_call_that_failed_opened_nothing(self) -> None:
        opened = _opened([{"file_path": "cache.py"}], self.root)
        self.assertEqual([p.type for p in _unread([self.finding], opened)], ["read", "read"])


class UnopenedTest(ReadingTest):
    """What a `true` verdict cites, against the lines `Read` opened."""

    def _types(self, evidence: Any, *reads: tuple[str, int, int], verdict: str = "true", tree: str = "root") -> list[str]:
        claim = {"claim": "x", "verdict": verdict, "tree": tree, "evidence": evidence}
        problems = _unopened({"claims": [claim]}, self.finding, self._opened(*reads))
        self.assertLessEqual({p.problem_class for p in problems}, {COMPARED})
        return [p.type for p in problems]

    def test_evidence_in_lines_a_read_covered_has_no_problem(self) -> None:
        for evidence in (
            "cache.py:9-13",
            "cache.py:9",
            "cache.py",
            "./cache.py:9-13 (put)",
            f"{self.root}/cache.py:9",
            "cache.py:L9-L13",
            "cache.py lines 9-13",
            "cache.py:9–13",
            "cache.py:7-9, 12-13",
            "cache.py:7-9 (get, at 99) and 12-13",
            "read in full, at cache.py:9.",
            "cache.py:9 calls self._entries.get",
        ):
            self.assertEqual(self._types(evidence, ("cache.py", 7, 13)), [], evidence)

    def test_evidence_in_a_file_no_read_opened_is_compared(self) -> None:
        for evidence in ("cache.py:9-13", "cache.py", "cache.py:9; other.py:3"):
            self.assertEqual(self._types(evidence, ("docs/design.md", 1, 9)), ["unopened"], evidence)

    def test_evidence_in_lines_no_read_covered_is_compared(self) -> None:
        for evidence in (
            "cache.py:14",
            "cache.py:9-14",
            "cache.py:9, 14",
            "cache.py lines 12-14",
            "cache.py:9; cache.py:20",
            "cache.py:9 and 14-15",
            "cache.py:9 (get, line 1), 14 (put)",
            "cache.py:9-10 (get), plus 14",
            "cache.py:9-10; 14",
            "`cache.py`:14",
            "`cache.py:9`, `cache.py:14`",
            "cache.py (lines 9-14)",
            "cache.py, lines 9-14",
            "cache.py, line 14",
            "cache.py#L9-L14",
            "lines 9-14 of cache.py",
            "line 14 in `cache.py`",
        ):
            self.assertEqual(self._types(evidence, ("cache.py", 7, 13)), ["unopened"], evidence)

    def test_one_cited_file_opened_is_enough_when_another_was_not(self) -> None:
        self.assertEqual(self._types("other.py:3; cache.py:9", ("cache.py", 7, 13)), [])

    def test_evidence_naming_no_file_is_its_own_type(self) -> None:
        for evidence in ("the code", "missing.py:3", "self._entries.get", ["grep"], "cache:9", "../cache.py:1", "docs"):
            self.assertEqual(self._types(evidence, ("cache.py", 1, 40)), ["unresolved"], evidence)

    def test_a_cited_line_of_no_file_there_is_reported_beside_one_that_resolves(self) -> None:
        for evidence in ("cache.py:9; missing.py:3", "`missing.py`:3, cache.py:9"):
            self.assertEqual(self._types(evidence, ("cache.py", 7, 13)), ["unresolved"], evidence)

    def test_only_a_true_verdict_is_held_to_it_and_only_where_it_cites_something(self) -> None:
        for verdict in ("false", "not checked"):
            self.assertEqual(self._types("cache.py:9", verdict=verdict), [])
        self.assertEqual(self._types(""), [])

    def test_evidence_is_read_at_the_claims_own_tree(self) -> None:
        commit = "4f1c2d3e"
        self.finding = replace(self.finding, text=f"x\nbefore {commit} {self.root}/.claims/trees/{commit}\n")
        for tree in ("before 4f1c2d3", "the before tree"):
            self.assertEqual(self._types("cache.py:9", ("cache.py", 1, 40), tree=tree), ["unopened"], tree)
            self.assertEqual(self._types("cache.py:9", (self.tree_copy, 1, 40), tree=tree), [], tree)
            self.assertEqual(self._types("other.py:9", ("other.py", 1, 40), tree=tree), [], tree)
        self.assertEqual(self._types(f"{self.tree_copy}:9", (self.tree_copy, 1, 40)), [])
        self.assertEqual(self._types("cache.py:9", ("cache.py", 1, 40), tree="root and before 4f1c2d3"), [])

    def test_a_malformed_claim_or_none_is_no_evidence_problem(self) -> None:
        for report in ({}, {"claims": "x"}, {"claims": ["x"]}):
            self.assertEqual(_unopened(report, self.finding, {}), [])


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
        self.assertFalse({d.name for d in ROOTS.values()} & {f.name.split("/")[0] for f in self.batch})

    def test_a_pair_shares_a_subject_and_needs_opposite_verdicts(self) -> None:
        self.assertTrue(_opposite_verdicts(self.batch))

    def test_a_claim_of_another_page_is_rejecting_though_no_kinds_list_it(self) -> None:
        design = next(f for f in self.batch if f.name.startswith("shared_subject_opposite_verdicts/design"))
        report = {
            "claims": [{"claim": "it evicts the newest entry", "verdict": "true", "kind": "current", "evidence": "x"}],
            "read": design.must_read,
        }
        self.assertEqual(_classes(_judge(report, design)), [("unit-other", REJECTING)])

    def test_each_findings_paths_exist_in_its_root(self) -> None:
        for finding in self.batch:
            self.assertEqual(finding.repo, self.root)
            for path in finding.must_read:
                self.assertTrue((self.root / path).is_file(), path)


class RealisticBatchTest(unittest.TestCase):
    def _batch(self, size: int, fixture_dir: Path = SMALL) -> list[Finding]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return _realistic_batch(Path(tmp.name).resolve(), size, fixture_dir)

    def _each(self) -> Iterator[tuple[Path, int, list[Finding]]]:
        for fixture_dir in (SMALL, LARGE):
            for size in SIZES:
                yield fixture_dir, size, self._batch(size, fixture_dir)

    def test_the_sizes_are_those_the_cap_is_measured_at(self) -> None:
        self.assertEqual(SIZES, (2, 3, 5, 10))

    def test_each_size_holds_that_many_findings(self) -> None:
        for _, size, batch in self._each():
            self.assertEqual(len(batch), size)

    def test_each_size_holds_a_pair_needing_opposite_verdicts(self) -> None:
        for fixture_dir, size, batch in self._each():
            self.assertTrue(_opposite_verdicts(batch), (fixture_dir.name, size))

    def test_no_size_packs_unrelated_findings(self) -> None:
        for _, size, batch in self._each():
            joined = {batch[0]}
            while more := {f for f in batch if f not in joined and any(set(f.subjects) & set(j.subjects) for j in joined)}:
                joined |= more
            self.assertEqual(len(joined), size)

    def test_every_finding_has_the_fixtures_one_root_and_its_paths_exist_there(self) -> None:
        for fixture_dir in (SMALL, LARGE):
            batch = self._batch(10, fixture_dir)
            self.assertEqual(len({f.repo for f in batch}), 1)
            for finding in batch:
                for path in finding.must_read:
                    self.assertTrue((finding.repo / path).is_file(), path)

    def test_the_root_is_outside_this_repository(self) -> None:
        self.assertFalse(self._batch(2)[0].repo.is_relative_to(REPO_ROOT))

    def test_a_claim_of_another_page_is_not_also_a_sentence_of_the_findings_own(self) -> None:
        for fixture_dir in (SMALL, LARGE):
            batch = self._batch(10, fixture_dir)
            for finding in batch:
                page = " ".join((finding.repo / finding.path).read_text(encoding="utf-8").split())
                other_pages = [x for f in batch if f.path != finding.path for x in f.expected["kinds"]]
                for fragment in finding.expected["elsewhere"]:
                    if fragment in other_pages:
                        self.assertNotIn(fragment, page, finding.name)

    def test_every_expected_fragment_is_in_its_unit_and_no_outside_one_is(self) -> None:
        for finding in self._batch(10) + self._batch(10, LARGE):
            expected = finding.expected
            for fragment in [*expected["false_claims"], *expected.get("not_checked", []), *expected["kinds"]]:
                self.assertIn(fragment, _unit(finding), finding.name)
            for fragment in expected["outside_unit"]:
                self.assertNotIn(fragment, _unit(finding), finding.name)
                self.assertIn(fragment, (finding.repo / finding.path).read_text(encoding="utf-8"), finding.name)
            for fragment in expected["elsewhere"]:
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
            self.assertEqual(_classes(_judge(report, batch[into])), [("unit-other", REJECTING)], leaked)

    def test_a_claim_of_a_finding_not_in_the_call_is_the_pages_own_sentence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            finding = _copied(SMALL, Path(tmp).resolve())[6]
        for leaked, type_, problem_class in (
            ("`delete` now ignores a key the cache doesn't hold.", "unit-own-page", COUNTED),
            ("`put` of a new key evicts the oldest entry first.", "unit-other", REJECTING),
        ):
            report = _passing_report(finding)
            report["claims"].append({"claim": leaked, "verdict": "true", "kind": "current", "evidence": "x:1"})
            self.assertEqual(_classes(_judge(report, finding)), [(type_, problem_class)], leaked)

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


class LargeRootTest(unittest.TestCase):
    """What the large root's findings hold, which the small root's don't."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.batch = _realistic_batch(Path(tmp.name).resolve(), 10, LARGE)

    def _settled(self, finding: Finding) -> dict[str, tuple[str, int, int]]:
        """Where each claim `settled_by` lists is settled: a file, and its first and last line."""

        settled: dict[str, tuple[str, int, int]] = {}
        for fragment, place in finding.expected.get("settled_by", {}).items():
            path, _, lines = place.partition(":")
            first, _, last = lines.partition("-")
            settled[fragment] = (path, int(first), int(last))
        return settled

    def test_every_subject_is_hundreds_of_lines(self) -> None:
        for path in {s for f in self.batch for s in f.subjects}:
            length = len((self.batch[0].repo / path).read_text(encoding="utf-8").splitlines())
            self.assertGreater(length, 200, path)

    def test_each_place_a_claim_is_settled_is_there(self) -> None:
        for finding in self.batch:
            for fragment, (path, first, last) in self._settled(finding).items():
                self.assertIn(fragment, _unit(finding), finding.name)
                lines = (finding.repo / path).read_text(encoding="utf-8").splitlines()
                self.assertLessEqual(1, first)
                self.assertLessEqual(first, last)
                self.assertLessEqual(last, len(lines), finding.name)

    def test_false_claims_depend_on_code_late_in_a_subject(self) -> None:
        late = [
            f.name
            for f in self.batch
            for fragment, (path, first, _) in self._settled(f).items()
            if fragment in f.expected["false_claims"] and path in f.subjects and first > 190
        ]
        self.assertGreaterEqual(len(late), 4, late)

    def test_claims_true_and_false_are_settled_by_a_file_the_finding_does_not_name(self) -> None:
        for size in (3, 5, 10):
            unnamed = [f for f in self.batch[:size] if any(p not in f.must_read for p, _, _ in self._settled(f).values())]
            self.assertTrue(unnamed, size)
        verdicts = {
            fragment in f.expected["false_claims"]
            for f in self.batch
            for fragment, (path, _, _) in self._settled(f).items()
            if path not in f.must_read
        }
        self.assertEqual(verdicts, {True, False})

    def test_an_absence_claim_is_true_in_one_finding_and_false_in_another(self) -> None:
        for size in (5, 10):
            absent = {x in f.expected["false_claims"] for f in self.batch[:size] for x in f.expected.get("absent", [])}
            self.assertEqual(absent, {True, False}, size)


class AloneTest(unittest.TestCase):
    def test_every_fixtures_every_finding_is_run_alone(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            roots = [Path(tmp).resolve() / d.name for d in _fixture_dirs()]
            found = [f for d, root in zip(_fixture_dirs(), roots, strict=True) for f in _copied(d, root)]
            self.assertEqual(len(found), 30)
            for finding in found:
                for path in finding.must_read:
                    self.assertTrue((finding.repo / path).is_file(), path)


def _record(findings: list[Finding], *problems: tuple[int, str, str], **fields: Any) -> dict[str, Any]:
    """A run as it is saved, with a problem of a type and class in each finding named by its index."""

    return {
        "model": "sonnet",
        "effort": EFFORT,
        "model_id": "claude-sonnet-5-5",
        "claude_code_version": "2.1.311",
        "findings": [f.name for f in findings],
        "claims": {f.name: 2 for f in findings},
        "problems": [
            {"finding": findings[i].name, "type": type_, "problem_class": class_, "detail": "x"} for i, type_, class_ in problems
        ],
        **fields,
    }


UNOPENED = ("unopened", COMPARED)
# A reading batch's calls, and calls of one finding, none with the compared problem.
CLEAN_BATCHES = [(0, 2)] * 60
CLEAN_ALONE = [(0, 1)] * 60


class BoundTest(unittest.TestCase):
    """The one-sided 95% upper bound on the batched rate less the alone rate.
    Each call is its findings with the compared problem, and its findings."""

    def test_none_in_sixty_calls_is_bounded_under_five_points_not_at_zero(self) -> None:
        self.assertAlmostEqual(_bound(CLEAN_BATCHES, CLEAN_ALONE), 0.0487, places=4)

    def test_none_in_twenty_calls_is_too_few(self) -> None:
        self.assertAlmostEqual(_bound(CLEAN_BATCHES[:20], CLEAN_ALONE), 0.1391, places=4)

    def test_a_rate_that_is_the_same_batched_and_alone_is_bounded_by_its_spread(self) -> None:
        # 6 of 120 either way: 1.645 * sqrt(0.5 * 0.5 * 0.1 * 0.9 / 60 + 0.05 * 0.95 / 120) is 0.046.
        bound = _bound([(1, 2)] * 6 + [(0, 2)] * 54, [(1, 1)] * 6 + [(0, 1)] * 114)
        self.assertAlmostEqual(bound, 0.046, delta=0.008)

    def test_whole_calls_are_resampled_so_problems_in_one_call_count_for_less(self) -> None:
        apart = _bound([(1, 2)] * 12 + [(0, 2)] * 48, CLEAN_ALONE)
        together = _bound([(2, 2)] * 6 + [(0, 2)] * 54, CLEAN_ALONE)
        # 0.1 + 1.645 * sqrt(0.25 * 0.2 * 0.8 / 60), and 0.1 + 1.645 * sqrt(0.1 * 0.9 / 60).
        self.assertAlmostEqual(apart, 0.142, delta=0.012)
        self.assertAlmostEqual(together, 0.164, delta=0.012)

    def test_one_reading_with_the_problem_is_bounded_no_lower_than_none(self) -> None:
        ten = [(0, 10)] * 60
        self.assertGreaterEqual(_bound([(1, 10), *ten[1:]], CLEAN_ALONE), _bound(ten, CLEAN_ALONE))

    def test_the_same_counts_give_the_same_bound(self) -> None:
        calls = [(1, 2)] * 6 + [(0, 2)] * 54
        self.assertEqual(_bound(calls, CLEAN_ALONE), _bound(calls, CLEAN_ALONE))


class BarTest(unittest.TestCase):
    """Whether saved runs of a size pass ADR 0021's bar, and if not, why."""

    def setUp(self) -> None:
        self.batch = _findings(LARGE)[:2]
        self.batched = [_record(self.batch) for _ in range(60)]
        self.alone = [_record([f]) for f in self.batch for _ in range(30)]

    def _short(self) -> str:
        return "; ".join(_short_of_the_bar(self.batched, self.alone))

    def test_sixty_clean_runs_against_as_many_clean_readings_alone_pass(self) -> None:
        self.assertEqual(self._short(), "")

    def test_one_rejecting_problem_rejects(self) -> None:
        self.batched[7] = _record(self.batch, (1, "verdict", REJECTING))
        self.assertIn("1 of 60 runs with a rejecting problem", self._short())

    def test_counted_problems_never_reject(self) -> None:
        self.batched = [_record(self.batch, (0, "unit-own-page", COUNTED)) for _ in range(60)]
        self.assertEqual(self._short(), "")

    def test_fewer_than_sixty_runs_are_too_few(self) -> None:
        del self.batched[0]
        self.assertIn("59 runs", self._short())

    def test_a_run_that_returned_no_object_for_a_finding_is_not_one_of_the_sixty(self) -> None:
        self.batched[0] = _record(self.batch, (1, "matching", COUNTED), claims={self.batch[0].name: 2})
        self.assertIn("59 runs", self._short())

    def test_runs_that_returned_nothing_readable_do_not_pass(self) -> None:
        self.batched = [_record(self.batch, claims={}) for _ in range(60)]
        self.assertIn("0 runs", self._short())

    def test_a_compared_rate_above_the_alone_rates_margin_does_not_pass(self) -> None:
        self.batched[:12] = [_record(self.batch, (0, *UNOPENED)) for _ in range(12)]
        self.assertIn("margin 0.050", self._short())

    def test_the_margin_is_the_alone_rate_once_that_is_five_points(self) -> None:
        self.batched[:12] = [_record(self.batch, (0, *UNOPENED)) for _ in range(12)]
        self.alone[:12] = [_record([self.batch[0]], (0, *UNOPENED)) for _ in range(12)]
        # 0.1 batched against 0.2 alone, whose margin is 0.2.
        self.assertEqual(self._short(), "")

    def test_evidence_naming_no_file_weighs_against_the_batch_and_not_for_the_alone_rate(self) -> None:
        unresolved = ("unresolved", COMPARED)
        self.batched[:12] = [_record(self.batch, (0, *unresolved)) for _ in range(12)]
        self.alone[:12] = [_record([self.batch[0]], (0, *unresolved)) for _ in range(12)]
        self.assertIn("margin 0.050", self._short())

    def test_one_finding_with_the_problem_twice_is_one_reading(self) -> None:
        self.batched[:2] = [_record(self.batch, *[(0, *UNOPENED)] * 5) for _ in range(2)]
        self.alone[:6] = [_record([self.batch[0]], (0, *UNOPENED)) for _ in range(6)]
        self.assertEqual(self._short(), "")

    def test_the_alone_rate_is_of_the_same_findings_each_read_as_often(self) -> None:
        other = _findings(LARGE)[2]
        self.alone += [_record([other], (0, *UNOPENED)) for _ in range(30)]
        self.assertEqual(self._short(), "")
        self.alone += [_record([self.batch[0]])]
        self.assertIn("not each read alone as often", self._short())

    def test_the_runs_of_a_size_are_not_readings_alone(self) -> None:
        self.alone = self.batched
        self.assertIn("0 readings alone", self._short())

    def test_too_few_readings_alone_do_not_pass(self) -> None:
        self.alone = [_record([f]) for f in self.batch for _ in range(29)]
        self.assertIn("58 readings alone", self._short())

    def test_an_alone_call_that_returned_nothing_is_no_reading(self) -> None:
        self.alone[0] = _record([self.batch[0]], (0, "call", REJECTING), claims={})
        self.assertIn("not each read alone as often", self._short())

    def test_the_small_root_alone_does_not_pass(self) -> None:
        batch = _findings(SMALL)[:2]
        self.batched = [_record(batch) for _ in range(60)]
        self.alone = [_record([f]) for f in batch for _ in range(30)]
        self.assertIn("the large root", self._short())

    def test_the_stress_pack_does_not_pass(self) -> None:
        batch = [f for d in _fixture_dirs() if d not in ROOTS.values() for f in _findings(d)]
        self.batched = [_record(batch) for _ in range(60)]
        self.alone = [_record([f]) for f in batch for _ in range(30)]
        self.assertIn("the large root", self._short())

    def test_runs_that_differ_in_findings_model_or_effort_are_not_compared(self) -> None:
        for changed in (
            [_record(self.batch[:1])],
            [_record(self.batch, model="haiku")],
            [_record(self.batch, effort="high")],
        ):
            self.assertIn("differ", "; ".join(_short_of_the_bar(self.batched + changed, self.alone)), changed)
        self.alone = [{**r, "effort": "high"} for r in self.alone]
        self.assertIn("differ", self._short())

    def _differs(self, batched: list[dict[str, Any]], alone: list[dict[str, Any]]) -> str:
        """The one line of the summary that says the runs differ, or `""`."""

        lines = _summary(batched, alone)
        if "passes the bar" in lines:
            return ""
        (line,) = [x for x in lines if x.startswith("doesn't pass the bar: the runs differ")]
        return line

    def test_runs_that_differ_in_model_id_or_version_alone_do_not_pass_and_the_summary_says_which(self) -> None:
        for field, value, said, unsaid in (
            ("model_id", "claude-sonnet-5-6", "model ID", "version"),
            ("claude_code_version", "2.1.312", "Claude Code version", "model"),
        ):
            changed = _record(self.batch, **{field: value})
            among_batched = self._differs([*self.batched, changed], self.alone)
            against_alone = self._differs(self.batched, [{**r, field: value} for r in self.alone])
            among_alone = self._differs(self.batched, [*self.alone[1:], {**self.alone[0], field: value}])
            for line in (among_batched, against_alone, among_alone):
                self.assertIn(said, line)
                self.assertNotIn(unsaid, line)

    def test_runs_that_differ_in_both_say_both(self) -> None:
        line = self._differs([*self.batched, _record(self.batch, model_id="m", claude_code_version="v")], self.alone)
        self.assertIn("model ID", line)
        self.assertIn("Claude Code version", line)

    def test_a_failed_call_that_names_neither_is_no_difference(self) -> None:
        neither = {"model_id": "", "claude_code_version": "", "claims": {}}
        failed = _record(self.batch, (0, "call", REJECTING), **neither)
        short = "; ".join(_short_of_the_bar([*self.batched, failed], self.alone))
        self.assertEqual(short, "1 of 61 runs with a rejecting problem")
        alone_failed = _record([self.batch[0]], (0, "call", REJECTING), **neither)
        self.assertEqual(_short_of_the_bar(self.batched, [*self.alone, alone_failed]), [])

    def test_a_failed_calls_own_version_is_still_compared(self) -> None:
        failed = _record(self.batch, (0, "call", REJECTING), model_id="", claude_code_version="2.1.312", claims={})
        self.assertIn("Claude Code version", self._differs([*self.batched, failed], self.alone))

    def test_calls_that_returned_a_message_without_naming_one_are_not_taken_to_agree(self) -> None:
        for field, said in (("model_id", "model ID"), ("claude_code_version", "Claude Code version")):
            runs, alone = ([{**r, field: ""} for r in x] for x in (self.batched, self.alone))
            self.assertEqual(_short_of_the_bar(runs, alone), [f"the runs don't say their {said}"])

    def test_the_summary_counts_failed_runs_by_class_and_claims_per_finding(self) -> None:
        self.batched[0] = _record(self.batch, (0, "unit-own-page", COUNTED), (1, "verdict", REJECTING))
        self.batched[1] = _record(self.batch, (0, "unit-own-page", COUNTED), (0, "unit-own-page", COUNTED))
        self.batched[2] = _record(self.batch, (0, "unresolved", COMPARED), claims={f.name: 5 for f in self.batch})
        out = "\n".join(_summary(self.batched, self.alone))
        self.assertIn("failed runs of 60: 1 rejecting, 1 compared, 2 counted", out)
        self.assertIn("2 x shared_subject_large/01-holds.finding.txt: unit-own-page (counted)", out)
        self.assertIn("evidence naming no file: 1 reading", out)
        self.assertIn("claims listed per finding: 2.05, alone 2.00", out)
        self.assertIn("doesn't pass the bar", out)

    def test_the_summary_of_a_passing_size_says_so_with_its_bound(self) -> None:
        out = "\n".join(_summary(self.batched, self.alone))
        self.assertIn("batched 0.000, alone 0.000, upper bound on the difference 0.049, margin 0.050", out)
        self.assertIn("passes the bar", out)

    def test_the_summary_without_alone_runs_gives_no_verdict(self) -> None:
        self.assertNotIn("the bar", "\n".join(_summary(self.batched, [])))


# Stands in for the `claude` binary: records how it was called, and prints
# the stream `reply.json` beside it says to.
FAKE_CLAUDE = """#!{python}
import json, os, sys
from pathlib import Path
here = Path(__file__).parent
with (here / "calls.jsonl").open("a") as calls:
    effort = os.environ.get("CLAUDE_CODE_EFFORT_LEVEL")
    calls.write(json.dumps({{"argv": sys.argv[1:], "cwd": os.getcwd(), "effort": effort}}) + "\\n")
reply = json.loads((here / "reply.json").read_text())
if "exit" in reply:
    print(reply["exit"], file=sys.stderr)
    raise SystemExit(1)
models = reply.get("models", ["claude-sonnet-5-5"])
init = {{"type": "system", "subtype": "init", "model": "claude-asked-for", "claude_code_version": "2.1.311"}}
print(json.dumps(init))
for number, path in enumerate(reply["reads"]):
    block = {{"type": "tool_use", "id": f"t{{number}}", "name": "Read", "input": {{"file_path": path}}}}
    print(json.dumps({{"type": "assistant", "message": {{"model": models[0], "content": [block]}}}}))
    result = {{"type": "tool_result", "tool_use_id": f"t{{number}}", "content": ""}}
    event = {{"type": "user", "message": {{"content": [result]}}, "tool_use_result": "Error: File does not exist."}}
    if os.path.exists(path):
        lines = len(Path(path).read_text().splitlines()[: reply.get("limit")])
        event["tool_use_result"] = {{"type": "text", "file": {{"filePath": path, "startLine": 1, "numLines": lines}}}}
    print(json.dumps(event))
for model in models:
    block = {{"type": "text", "text": reply["message"]}}
    print(json.dumps({{"type": "assistant", "message": {{"model": model, "content": [block]}}}}))
result = {{"type": "result", "result": reply["message"], "usage": {{"output_tokens": 7}}}}
print(json.dumps({{**result, "is_error": reply.get("is_error", False)}}))
"""


def _passing_report(finding: Finding) -> dict[str, Any]:
    expected = finding.expected
    verdicts = {f: "false" for f in expected["false_claims"]} | {f: "not checked" for f in expected.get("not_checked", [])}
    claims = [
        {"claim": f, "verdict": verdicts.get(f, "true"), "kind": expected.get("kinds", {}).get(f, "current"), "evidence": f"{finding.subjects[0]}:1"}
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

    def _reply(self, reports: Any, reads: list[str], limit: int | None = None, **fields: Any) -> None:
        reply = {"message": json.dumps(reports), "reads": reads, "limit": limit, **fields}
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
        self._main("--root", "small", "--batch-size", "2")
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

    def test_a_calls_effort_is_pinned_whatever_the_environment_sets(self) -> None:
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_EFFORT_LEVEL": "max"}):
            self._main("--root", "small", "--batch-size", "2", "--output-dir", str(self.out))
        (call,) = self._calls()
        argv: list[str] = call["argv"]
        self.assertEqual(argv[argv.index("--effort") + 1], "medium")
        self.assertEqual(call["effort"], "medium")
        (saved,) = self.out.iterdir()
        self.assertEqual(json.loads(saved.read_text(encoding="utf-8"))["effort"], "medium")

    def test_the_agent_runs_at_the_effort_its_golden_runs_do(self) -> None:
        # A session's own effort would otherwise set the reader's, and the
        # cap rests on runs at this one (#296).
        text = (REPO_ROOT / "claims" / "subagent" / "reading_agent.md").read_text(encoding="utf-8")
        _, frontmatter, _ = text.split("---\n", 2)
        fields = dict(line.split(": ", 1) for line in frontmatter.splitlines())
        self.assertEqual(fields.get("effort"), EFFORT)

    def _saved_identity(self) -> tuple[str, str]:
        self._main("--root", "small", "--batch-size", "2", "--output-dir", str(self.out))
        (saved,) = self.out.iterdir()
        run = json.loads(saved.read_text(encoding="utf-8"))
        self.assertEqual(run["model"], "sonnet")
        return run["model_id"], run["claude_code_version"]

    def test_the_model_that_answered_and_the_version_that_called_it_are_saved(self) -> None:
        self.assertEqual(self._saved_identity(), ("claude-sonnet-5-5", "2.1.311"))

    def test_each_model_that_answered_one_call_is_saved(self) -> None:
        self._reply([], ["missing.py"], models=["claude-sonnet-5-5", "claude-opus-5-5"])
        self.assertEqual(self._saved_identity(), ("claude-sonnet-5-5, claude-opus-5-5", "2.1.311"))

    def test_an_error_message_no_model_wrote_saves_no_model(self) -> None:
        self._reply([], [], models=["<synthetic>"], is_error=True)
        self.assertEqual(self._saved_identity(), ("", "2.1.311"))

    def test_a_call_that_returned_neither_is_saved_as_a_call_problem(self) -> None:
        (self.bin / "reply.json").write_text(json.dumps({"exit": "usage limit"}), encoding="utf-8")
        self.assertEqual(self._saved_identity(), ("", ""))
        (saved,) = self.out.iterdir()
        self.assertEqual([p["type"] for p in json.loads(saved.read_text(encoding="utf-8"))["problems"]], ["call"])

    def test_the_claims_each_finding_listed_are_saved(self) -> None:
        self._main("--root", "small", "--batch-size", "2", "--output-dir", str(self.out))
        (saved,) = self.out.iterdir()
        run = json.loads(saved.read_text(encoding="utf-8"))
        self.assertEqual(run["claims"], {f.name: 2 for f in self.batch})

    def test_saved_runs_are_summarised_against_saved_alone_runs_with_no_call(self) -> None:
        batch = _findings(LARGE)[:2]
        for directory, records in (
            ("batched", [_record(batch)] * 30),
            ("more", [_record(batch)] * 30),
            ("alone", [_record([f]) for f in batch for _ in range(30)]),
        ):
            (self.out / directory).mkdir(parents=True)
            for i, record in enumerate(records):
                (self.out / directory / f"{i}.json").write_text(json.dumps(record), encoding="utf-8")
        code, out = self._main(
            "--saved", str(self.out / "batched"), "--saved", str(self.out / "more"), "--alone", str(self.out / "alone")
        )
        self.assertEqual(self._calls(), [])
        self.assertEqual(code, 0, out)
        self.assertIn("failed runs of 60: 0 rejecting", out)
        self.assertIn("passes the bar", out)

    def test_saved_runs_of_the_earlier_harness_are_refused(self) -> None:
        self.out.mkdir()
        (self.out / "old.json").write_text(json.dumps({"findings": [], "problems": []}), encoding="utf-8")
        for option in ("--saved", "--alone"):
            code, out = self._main(option, str(self.out))
            self.assertEqual(code, 2)
            self.assertIn("old.json", out)
            for field in ("model_id", "claude_code_version"):
                run = _record(_findings(LARGE)[:1])
                del run[field]
                (self.out / "old.json").write_text(json.dumps(run), encoding="utf-8")
                code, out = self._main(option, str(self.out))
                self.assertEqual(code, 2, field)
                self.assertIn("old.json was saved by an earlier harness", out)
        code, _ = self._main("--saved", str(self.out / "none"))
        self.assertEqual(code, 2)
        self.assertEqual(self._calls(), [])

    def test_a_run_with_only_a_counted_problem_does_not_fail_the_command(self) -> None:
        self._reply([_passing_report(self.batch[0])], [p for f in self.batch for p in f.must_read])
        code, out = self._main("--root", "small", "--batch-size", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("[COUNTED] sonnet small-batch-2 1/1", out)
        self.assertIn("failed runs of 1: 0 rejecting, 0 compared, 1 counted", out)

    def test_every_finding_alone_is_isolated_too(self) -> None:
        self._main()
        calls = self._calls()
        self.assertEqual(len(calls), 30)
        self.assertEqual(len({c["cwd"] for c in calls}), 30)
        for call in calls:
            self.assertIn("--safe-mode", call["argv"])
            self.assertFalse(Path(call["cwd"]).resolve().is_relative_to(REPO_ROOT))

    def test_only_a_fixtures_findings_are_run_alone_when_it_is_named(self) -> None:
        _, out = self._main("--only", "shared_subject_batch", "--output-dir", str(self.out))
        self.assertIn("failed runs of 10: ", out)
        self.assertEqual(len(self._calls()), 10)
        names = [json.loads(p.read_text(encoding="utf-8"))["findings"] for p in sorted(self.out.iterdir())]
        self.assertEqual(names, [[f.name] for f in _findings(FIXTURES_DIR / "shared_subject_batch")])

    def test_only_the_findings_named_are_run_alone_each_repeat(self) -> None:
        named = ["shared_subject_batch/02-faq.finding.txt", "known_true/finding.txt"]
        _, out = self._main("--only", named[0], "--only", named[1], "--repeat", "3")
        self.assertEqual(len(self._calls()), 6)
        for name in named:
            self.assertEqual(out.count(f"alone {name} "), 3, out)

    def test_a_name_no_finding_has_is_refused_before_any_call(self) -> None:
        for name in ("shared_subject", "shared_subject_batch/02-faq"):
            code, _ = self._main("--only", "known_true", "--only", name)
            self.assertEqual(code, 2, name)
        self.assertEqual(self._calls(), [])

    def test_a_name_no_finding_has_leaves_no_output_directory(self) -> None:
        self._main("--only", "shared_subject", "--output-dir", str(self.out))
        self.assertFalse(self.out.exists())

    def test_a_batch_passes_when_each_finding_does(self) -> None:
        code, out = self._main("--root", "small", "--batch-size", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("failed runs of 1: 0 rejecting, 0 compared, 0 counted", out)

    def test_repeats_count_failed_runs_and_failures_by_finding_and_type(self) -> None:
        reports = [_passing_report(f) for f in self.batch]
        for report in reports:
            report["claims"][0]["verdict"] = "not checked"
        self._reply(reports, [p for f in self.batch for p in f.must_read])
        code, out = self._main("--root", "small", "--batch-size", "2", "--repeat", "3")
        self.assertEqual(code, 1)
        self.assertEqual(len(self._calls()), 3)
        self.assertIn("failed runs of 3: 3 rejecting, 0 compared, 0 counted", out)
        self.assertIn("3 x shared_subject_batch/01-design.finding.txt: verdict", out)
        self.assertIn("3 x shared_subject_batch/02-faq.finding.txt: verdict", out)

    def test_a_run_whose_call_fails_is_a_failed_run_of_its_own_type(self) -> None:
        (self.bin / "reply.json").write_text(json.dumps({"exit": "usage limit"}), encoding="utf-8")
        code, out = self._main("--root", "small", "--batch-size", "2", "--repeat", "2")
        self.assertEqual(code, 1)
        self.assertIn("failed runs of 2: 2 rejecting, 0 compared, 0 counted", out)
        self.assertIn("2 x the whole call: call", out)
        self.assertIn("usage limit", out)

    def test_a_subject_the_call_read_part_of_rejects_the_run(self) -> None:
        self._reply([_passing_report(f) for f in self.batch], [p for f in self.batch for p in f.must_read], limit=8)
        code, out = self._main("--root", "small", "--batch-size", "2")
        self.assertEqual(code, 1)
        self.assertIn("only partly read", out)

    def test_evidence_the_call_did_not_open_is_reported_with_its_class(self) -> None:
        report = _passing_report(self.batch[0])
        report["claims"][0]["evidence"] = "settings.py:3"
        report["claims"][1]["evidence"] = "the code"
        self._reply([report, _passing_report(self.batch[1])], [p for f in self.batch for p in f.must_read])
        code, out = self._main("--root", "small", "--batch-size", "2", "--output-dir", str(self.out))
        self.assertEqual(code, 0, out)
        (saved,) = self.out.iterdir()
        run = json.loads(saved.read_text(encoding="utf-8"))
        self.assertEqual(
            [(p["type"], p["problem_class"]) for p in run["problems"]], [("unopened", COMPARED), ("unresolved", COMPARED)]
        )

    def test_a_read_call_that_failed_is_saved_with_no_lines(self) -> None:
        self._reply([], ["missing.py"])
        self._main("--root", "small", "--batch-size", "2", "--output-dir", str(self.out))
        (saved,) = self.out.iterdir()
        self.assertEqual(json.loads(saved.read_text(encoding="utf-8"))["reads"], [{"file_path": "missing.py"}])

    def test_each_runs_message_and_reads_are_saved(self) -> None:
        self._main("--root", "small", "--batch-size", "2", "--repeat", "2", "--output-dir", str(self.out))
        saved = sorted(self.out.iterdir())
        self.assertEqual(len(saved), 2)
        run = json.loads(saved[0].read_text(encoding="utf-8"))
        self.assertEqual(json.loads(run["message"]), [_passing_report(f) for f in self.batch])
        self.assertEqual([r["file_path"] for r in run["reads"]], [p for f in self.batch for p in f.must_read])
        self.assertEqual(run["reads"][0]["lines"], [1, 8])
        self.assertEqual(run["usage"], {"output_tokens": 7})
        self.assertEqual(run["problems"], [])

    def test_a_failed_runs_message_is_saved_with_its_problems(self) -> None:
        self._reply([], [])
        self._main("--root", "small", "--batch-size", "2", "--output-dir", str(self.out))
        (saved,) = self.out.iterdir()
        run = json.loads(saved.read_text(encoding="utf-8"))
        self.assertEqual(run["message"], "[]")
        self.assertEqual({p["type"] for p in run["problems"]}, {"matching", "read"})

    def test_every_finding_alone_is_saved_to_a_file_of_its_own(self) -> None:
        self._main("--output-dir", str(self.out))
        self.assertEqual(len(list(self.out.iterdir())), 30)

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
        code, _ = self._main("--root", "small", "--batch-size", "2", "--output-dir", str(self.out))
        self.assertEqual(code, 2)
        self.assertEqual(self._calls(), [])

    def test_a_size_the_cap_is_not_measured_at_no_repeats_and_two_modes_are_refused(self) -> None:
        for args in (
            ["--batch-size", "4"],
            ["--repeat", "0"],
            ["--batch-size", "2", "--stress"],
            ["--batch-size", "2", "--only", "known_true"],
            ["--stress", "--only", "known_true"],
            ["--saved", "x", "--stress"],
        ):
            code, _ = self._main(*args)
            self.assertEqual(code, 2, args)
        self.assertEqual(self._calls(), [])


if __name__ == "__main__":
    unittest.main()
