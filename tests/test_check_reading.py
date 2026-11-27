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

"""`check-reading` (#299): a reading agent's output, checked against the
findings the session sent it, before anything is marked. Each test hands
the command a hand-written array, as the agent would return it, and reads
what it prints and how it exits."""

from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from claims.cli import main
from claims.reading import check_reading, load_sent

GUIDE = "# Guide\n\nThe cache has one reader, `get`.\n\n## Next\n\nOther prose.\n"
CACHE = "".join(f"line {n}\n" for n in range(1, 21))
LINE = "[advisory] docs/guide.md:1 (stale-claims) 'Guide' names code — src/cache.py 2 commits"
NAME = "docs/guide.md:1 stale-claims"
COMMIT = "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b"


def _claim(verdict: str = "true", evidence: str = "src/cache.py:1-20", tree: str = "root", **extra: str) -> dict[str, str]:
    return {"claim": "The cache has one reader, `get`.", "verdict": verdict, "kind": "current", "tree": tree, "evidence": evidence, **extra}


def _report(finding: str = NAME, claims: list[dict[str, str]] | None = None, read: list[str] | None = None) -> dict[str, Any]:
    return {
        "finding": finding,
        "claims": [_claim()] if claims is None else claims,
        "read": ["docs/guide.md", "src/cache.py"] if read is None else read,
        "searched": [],
        "note": "read src/cache.py; the claim holds",
    }


class CheckReadingTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        (self.root / "docs").mkdir()
        (self.root / "src").mkdir()
        (self.root / "docs" / "guide.md").write_text(GUIDE, encoding="utf-8")
        (self.root / "src" / "cache.py").write_text(CACHE, encoding="utf-8")
        self.sent: list[dict[str, Any]] = [{"finding": LINE, "subjects": ["src/cache.py"], "root": str(self.root)}]

    def _check(self, output: Any) -> tuple[int, list[str]]:
        """The exit code, and each item flagged, without the closing count."""

        out_file = self.root / "out.json"
        sent_file = self.root / "sent.json"
        out_file.write_text(output if isinstance(output, str) else json.dumps(output), encoding="utf-8")
        sent_file.write_text(json.dumps(self.sent), encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["check-reading", str(out_file), str(sent_file)])
        *flagged, count = stdout.getvalue().splitlines()
        self.assertEqual(count, f"{len(flagged)} item(s) flagged")
        return code, flagged

    def _types(self, output: Any) -> list[str]:
        code, flagged = self._check(output)
        self.assertEqual(code, 1 if flagged else 0)
        return [line.removeprefix(f"{NAME} ").split(":")[0] for line in flagged]

    def test_a_clean_array_flags_nothing_and_exits_0(self) -> None:
        self.assertEqual(self._check([_report()]), (0, []))

    def test_a_finding_with_no_object_is_flagged_for_matching(self) -> None:
        code, flagged = self._check([])
        self.assertEqual(code, 1)
        self.assertEqual(flagged, [f"{NAME} matching: no object for it"])

    def test_a_finding_with_two_objects_is_flagged_for_matching(self) -> None:
        self.assertEqual(self._types([_report(), _report()]), ["matching"])

    def test_an_object_for_a_finding_not_sent_is_flagged(self) -> None:
        code, flagged = self._check([_report(), _report(finding="docs/other.md:3 claim-words-totalising")])
        self.assertEqual(code, 1)
        self.assertEqual(len(flagged), 1)
        self.assertTrue(flagged[0].startswith("(not sent) matching: "), flagged)

    def test_output_holding_no_array_flags_every_finding_for_matching(self) -> None:
        self.assertEqual(self._types(json.dumps(_report())), ["matching"])


    def test_a_subject_missing_from_read_is_flagged(self) -> None:
        # The claim citing it is flagged too.
        self.assertEqual(self._types([_report(read=["docs/guide.md"])]), ["read", "cited"])

    def test_the_unit_missing_from_read_is_flagged(self) -> None:
        self.assertEqual(self._types([_report(read=["src/cache.py"])]), ["read"])

    def test_a_subject_listed_with_only_part_of_it_is_flagged(self) -> None:
        for entry in ("src/cache.py:1-10", "src/cache.py lines 1-19", "lines 2-20 of src/cache.py"):
            self.assertEqual(self._types([_report(read=["docs/guide.md", entry])]), ["read", "cited"], entry)

    def test_a_read_flag_names_the_file_it_is_about(self) -> None:
        sent = load_sent(self.sent)
        for read, path in ((["src/cache.py"], "docs/guide.md"), (["docs/guide.md", "src/cache.py:1-10"], "src/cache.py")):
            flags = [f for f in check_reading([_report(read=read)], sent) if f.type == "read"]
            self.assertEqual([f.path for f in flags], [path], read)

    def test_a_subject_listed_with_every_line_is_read(self) -> None:
        for entry in ("src/cache.py:1-20", "src/cache.py lines 1-10 and 11-20"):
            self.assertEqual(self._types([_report(read=["docs/guide.md", entry])]), [], entry)

    def test_the_unit_is_read_by_the_lines_or_the_section_it_is(self) -> None:
        for entry in ("docs/guide.md:1-3", "docs/guide.md#guide", "docs/guide.md lines 1-4"):
            self.assertEqual(self._types([_report(read=[entry, "src/cache.py"])]), [], entry)
        for entry in ("docs/guide.md:1-2", "docs/guide.md#next", "docs/guide.md:5-8"):
            self.assertEqual(self._types([_report(read=[entry, "src/cache.py"])]), ["read"], entry)

    def test_an_anchored_subject_is_read_by_its_section(self) -> None:
        self.sent[0]["subjects"] = ["docs/guide.md#next"]
        for entry in ("docs/guide.md#next", "docs/guide.md:5-7", "docs/guide.md"):
            self.assertEqual(self._types([_report(read=["docs/guide.md:1-3", entry, "src/cache.py"])]), [], entry)
        self.assertEqual(self._types([_report(read=["docs/guide.md:1-3", "src/cache.py"])]), ["read"])

    def test_a_path_given_from_the_root_or_in_full_names_the_file(self) -> None:
        for entry in ("./src/cache.py", f"{self.root}/src/cache.py", "`src/cache.py` (all 20 lines)"):
            self.assertEqual(self._types([_report(read=["docs/guide.md", entry])]), [], entry)

    def test_a_bare_file_name_names_no_file(self) -> None:
        self.assertEqual(self._types([_report(read=["docs/guide.md", "cache.py"])]), ["read", "cited"])

    def test_a_subject_the_root_does_not_hold_is_not_flagged(self) -> None:
        self.sent[0]["subjects"] = ["src/cache.py", "src/gone.py"]
        self.assertEqual(self._types([_report()]), [])


    def test_a_true_claim_citing_a_file_not_in_read_is_flagged(self) -> None:
        (self.root / "src" / "other.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
        for evidence in ("src/other.py:2", "src/cache.py:3 and src/other.py:2"):
            report = _report(claims=[_claim(evidence=evidence)])
            self.assertEqual(self._types([report]), ["cited"], evidence)

    def test_a_true_claim_citing_lines_outside_its_read_entry_is_flagged(self) -> None:
        self.sent[0]["subjects"] = []
        read = ["docs/guide.md", "src/cache.py:1-10"]
        self.assertEqual(self._types([_report(claims=[_claim(evidence="src/cache.py:4-9")], read=read)]), [])
        self.assertEqual(self._types([_report(claims=[_claim(evidence="src/cache.py:9-15")], read=read)]), ["cited"])

    def test_a_true_claim_citing_lines_outside_its_read_section_is_flagged(self) -> None:
        read = ["docs/guide.md:1-3", "docs/guide.md#next", "src/cache.py"]
        self.assertEqual(self._types([_report(claims=[_claim(evidence="docs/guide.md:6")], read=read)]), [])
        self.assertEqual(self._types([_report(claims=[_claim(evidence="docs/guide.md:4")], read=read)]), ["cited"])

    def test_a_claim_other_than_true_is_not_held_to_read(self) -> None:
        for verdict in ("false", "not checked"):
            claims = [_claim(verdict=verdict, evidence="src/cache.py:3")]
            report = _report(claims=claims, read=["docs/guide.md", "src/cache.py"])
            self.assertNotIn("cited", self._types([report]), verdict)

    def test_a_path_in_a_tree_is_read_at_the_claims_own_tree(self) -> None:
        tree = self.root / ".claims" / "trees" / COMMIT / "src"
        tree.mkdir(parents=True)
        (tree / "cache.py").write_text("old\nold\nold\n", encoding="utf-8")
        self.sent[0]["trees"] = [f"before {COMMIT} {tree.parent}"]
        claims = [_claim(evidence="src/cache.py:3", tree=f"before {COMMIT[:7]}", kind="past")]
        for entry in (f".claims/trees/{COMMIT}/src/cache.py", f"src/cache.py (before {COMMIT[:7]})", f"{tree}/cache.py"):
            report = _report(claims=claims, read=["docs/guide.md", "src/cache.py", entry])
            self.assertEqual(self._types([report]), [], entry)
        # The root's own copy is a different file from the tree's.
        self.assertEqual(self._types([_report(claims=claims)]), ["cited"])


    def test_a_true_claim_whose_evidence_names_no_file_is_flagged(self) -> None:
        # A bare file name names no file: `cache.py` is `src/cache.py`.
        for evidence in ("the docstring says so", "cache.py:3", "src/cache.py:3 and src/gone.py:4"):
            report = _report(claims=[_claim(evidence=evidence)])
            self.assertEqual(self._types([report]), ["no-file"], evidence)

    def test_an_object_listing_no_claims_is_flagged(self) -> None:
        self.assertEqual(self._types([_report(claims=[])]), ["no-claims"])

    def test_a_not_checked_claim_is_listed_with_what_it_would_need(self) -> None:
        claims = [_claim(), _claim(verdict="not checked", evidence="docs/guide.md:3", reasoning="needs a run of the command")]
        code, flagged = self._check([_report(claims=claims)])
        self.assertEqual(code, 1)
        self.assertEqual(len(flagged), 1)
        self.assertTrue(flagged[0].startswith(f"{NAME} not-checked: "), flagged)
        self.assertIn("needs a run of the command", flagged[0])

    def test_flags_come_per_finding_in_the_order_sent(self) -> None:
        self.sent.append({"finding": LINE.replace(":1 ", ":3 ").replace("stale-claims", "claim-words-totalising"), "subjects": [], "root": str(self.root)})
        second = "docs/guide.md:3 claim-words-totalising"
        output = [_report(finding="docs/other.md:9 restatement"), _report(finding=second, claims=[]), _report(read=[])]
        _, flagged = self._check(output)
        self.assertEqual(
            [line.partition(": ")[0] for line in flagged],
            [f"{NAME} read", f"{NAME} read", f"{NAME} cited", f"{second} no-claims", "(not sent) matching"],
        )

    def test_findings_sent_in_another_shape_are_refused(self) -> None:
        for sent in ({"finding": LINE}, [{"finding": "no finding line", "subjects": [], "root": "."}], [{"finding": LINE, "root": "."}]):
            self.sent = sent  # type: ignore[assignment]
            out_file, sent_file = self.root / "out.json", self.root / "sent.json"
            out_file.write_text("[]", encoding="utf-8")
            sent_file.write_text(json.dumps(sent), encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main(["check-reading", str(out_file), str(sent_file)]), 2, sent)
            self.assertIn("can't read", err.getvalue())


if __name__ == "__main__":
    unittest.main()
