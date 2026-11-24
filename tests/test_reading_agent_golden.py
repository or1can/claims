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

`scripts/run_reading_agent_golden.py --batched` hands every fixture's
finding to one call, each fixture's repository under its own prefix in
one root, and judges the array that comes back. These hold that judging
to what #274 asks of it: one object per finding, keyed by its
`file:line` and mode, and each judged as it would be alone.
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from scripts.run_reading_agent_golden import (  # noqa: E402
    Finding,
    _batch_root,
    _extract_array,
    _findings,
    _fixture_dirs,
    _judge_batch,
    _prefixed,
)


def _finding(path: str = "docs/design.md", line: int = 1, mode: str = "stale-claims") -> Finding:
    return Finding(
        name="f",
        text=f"[advisory] {path}:{line} ({mode}) 'Caching' names code — cache.py 2 commits\n\nSubjects: cache.py\n",
        expected={"false_claims": [], "outside_unit": ["written to disk"]},
        repo=Path("repo"),
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


class JudgeBatchTest(unittest.TestCase):
    def setUp(self) -> None:
        self.findings = [_prefixed(_finding(), "f01"), _prefixed(_finding("docs/faq.md", 3), "f02")]
        self.second = _report("f02/docs/faq.md:3 stale-claims", read=["f02/docs/faq.md", "f02/cache.py"])

    def test_one_true_object_per_finding_passes(self) -> None:
        self.assertIsNone(_judge_batch([_report("f01/docs/design.md:1 (stale-claims)"), self.second], self.findings))

    def test_a_bare_object_is_not_an_array(self) -> None:
        self.assertIn("array", _judge_batch(_report("f01/docs/design.md:1 stale-claims"), self.findings) or "")

    def test_a_missing_finding_fails(self) -> None:
        self.assertIn("f01/docs/design.md:1", _judge_batch([self.second], self.findings) or "")

    def test_a_duplicated_finding_fails(self) -> None:
        first = _report("f01/docs/design.md:1 stale-claims")
        self.assertIsNotNone(_judge_batch([first, first, self.second], self.findings))

    def test_an_unrecognised_finding_fails(self) -> None:
        first = _report("f01/docs/design.md:1 stale-claims")
        stray = _report("f09/docs/other.md:1 stale-claims")
        self.assertIn("f09", _judge_batch([first, self.second, stray], self.findings) or "")

    def test_a_wrong_verdict_in_one_finding_fails_the_batch(self) -> None:
        first = _report("f01/docs/design.md:1 stale-claims", verdict="false")
        self.assertIn("expected true", _judge_batch([first, self.second], self.findings) or "")

    def test_a_subject_missing_from_one_findings_read_fails(self) -> None:
        first = _report("f01/docs/design.md:1 stale-claims", read=["f01/docs/design.md"])
        self.assertIn("f01/cache.py", _judge_batch([first, self.second], self.findings) or "")


class FixturesTest(unittest.TestCase):
    def test_the_batched_run_is_ten_findings(self) -> None:
        self.assertEqual(len([f for d in _fixture_dirs() for f in _findings(d)]), 10)

    def test_a_pair_shares_a_subject_and_needs_opposite_verdicts(self) -> None:
        by_subject: dict[tuple[Path, str], list[Finding]] = {}
        for finding in (f for d in _fixture_dirs() for f in _findings(d)):
            for subject in finding.subjects:
                by_subject.setdefault((finding.repo, subject), []).append(finding)
        self.assertTrue(
            any(
                any(f.expected["false_claims"] for f in group) and any(not f.expected["false_claims"] for f in group)
                for group in by_subject.values()
            )
        )

    def test_each_findings_paths_exist_in_its_batch_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for finding in _batch_root(Path(tmp), _fixture_dirs()):
                for path in [finding.path, *finding.subjects]:
                    self.assertTrue((Path(tmp) / path).is_file(), path)


if __name__ == "__main__":
    unittest.main()
