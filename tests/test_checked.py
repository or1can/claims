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

"""Tests for checked marks (ADR 0010): `claims mark-checked` writing
`claims.checked.toml`, and a normal run keeping a marked advisory finding
quiet until what it was read against changes."""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from claims.checked import Mark, _render, load_marks, marks_at, write_marks
from claims.checks import check_file_refs, check_links, claim_words, restatement, spliced_docs, stale_claims
from claims.cli import main
from claims.config import ConfigError
from claims.gate import decide_repo
from claims.runner import Finding, clear_registry, register_check

from support import RegistryClearingTestCase, Repo

CONFIG = '[claim-words]\nfiles = ["docs/*.md"]\n'


class CheckedMarkTests(RegistryClearingTestCase):
    def setUp(self) -> None:
        super().setUp()
        register_check(claim_words.NAME, claim_words.check)
        self.repo = Repo().__enter__()
        self.addCleanup(self.repo.__exit__)
        self.repo.write("claims.toml", CONFIG)
        self.repo.write("README.md", "Readme.\n")
        self.repo.commit()

    def run_cli(self, *argv: str, stdin: str = "") -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch("sys.stdin", io.StringIO(stdin)),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            code = main([*argv, "--repo-root", str(self.repo.root)])
        return code, out.getvalue(), err.getvalue()

    def mark(
        self,
        *entries: str,
        by: str | None = None,
        diff_range: str | None = None,
        partial: bool = False,
        pending: bool = False,
        kind: str | None = None,
        evidence: tuple[str, ...] = (),
    ):
        argv = ["mark-checked"]
        if by is not None:
            argv += ["--by", by]
        if kind is not None:
            argv += ["--kind", kind]
        for ref in evidence:
            argv += ["--evidence", ref]
        if partial:
            argv.append("--partial")
        if pending:
            argv.append("--pending")
        if diff_range is not None:
            argv += ["--diff-range", diff_range]
        return self.run_cli(*argv, "-", stdin="".join(e + "\n" for e in entries))

    def test_a_marked_finding_is_quiet_and_counted(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")
        code, out, err = self.mark("docs/a.md:1 claim-words-totalising read the runner")
        self.assertEqual((code, err), (0, ""))

        code, out, _ = self.run_cli()

        self.assertEqual(code, 0)
        self.assertEqual(
            out.splitlines(),
            ["1 checked, 0 finding(s), 0 gate failure(s), 1 quiet while checked"],
        )

    def summary(self) -> str:
        return self.run_cli()[1].splitlines()[-1]

    def test_rewrapping_keeps_the_mark_and_changing_a_word_drops_it(self) -> None:
        self.repo.write("docs/a.md", "Every check runs before the commit lands.\n")
        self.mark("docs/a.md:1 claim-words-totalising read the runner")

        self.repo.write("docs/a.md", "Every check runs\nbefore the *commit* lands.\n")
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

        self.repo.write("docs/a.md", "Every check runs before the push lands.\n")
        code, out, _ = self.run_cli()
        self.assertIn("[advisory] docs/a.md:1 (claim-words-totalising)", out)
        self.assertNotIn("quiet", out)


    def test_a_mark_expires_when_a_subject_changes_and_returns_when_it_is_reverted(self) -> None:
        self.repo.write("src/cache.py", "CACHE = 1\n")
        self.repo.write("src/other.py", "OTHER = 1\n")
        self.repo.commit()
        self.repo.write("docs/a.md", "Every read goes through src/cache.py first.\n")
        self.mark("docs/a.md:1 claim-words-totalising read cache.py")

        self.repo.write("src/other.py", "OTHER = 2\n")
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

        self.repo.write("src/cache.py", "CACHE = 2\n")
        self.assertEqual(self.summary(), "1 checked, 1 finding(s), 0 gate failure(s)")

        self.repo.write("src/cache.py", "CACHE = 1\n")
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

    def test_a_mark_with_no_subject_survives_code_changes(self) -> None:
        self.repo.write("src/cache.py", "CACHE = 1\n")
        self.repo.commit()
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising wording only")

        self.repo.write("src/cache.py", "CACHE = 2\n")
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

    def test_a_unit_that_now_names_a_new_subject_comes_back(self) -> None:
        self.repo.write("docs/a.md", "Every read goes through `store`.\n")
        self.mark("docs/a.md:1 claim-words-totalising read the store")

        self.repo.write("src/store.py", "STORE = 1\n")
        self.assertEqual(self.summary(), "1 checked, 1 finding(s), 0 gate failure(s)")

    def test_a_mark_survives_a_squash_of_the_commits_around_it(self) -> None:
        self.repo.write("src/cache.py", "CACHE = 1\n")
        self.repo.commit()
        self.repo.write("docs/a.md", "Every read goes through src/cache.py first.\n")
        self.mark("docs/a.md:1 claim-words-totalising read cache.py")
        self.repo.commit()
        self.git("reset", "--soft", "HEAD~2")

        self.assertTrue(
            self.summary().endswith(", 1 quiet while checked, 1 mark(s) added in range")
        )

    def git(self, *args: str) -> None:
        import subprocess

        subprocess.run(["git", "-C", str(self.repo.root), *args], check=True, capture_output=True)

    def test_a_mark_on_one_mode_leaves_another_mode_shown(self) -> None:
        self.repo.write("docs/a.md", "Each of the three backends keeps a copy.\n")
        self.mark("docs/a.md:1 claim-words-counts counted the backends")

        code, out, _ = self.run_cli()

        self.assertIn("[advisory] docs/a.md:1 (claim-words-totalising)", out)
        self.assertTrue(out.splitlines()[-1].endswith(", 1 quiet while checked"))

    def test_a_second_copy_is_shown_until_it_is_marked_too(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read the runner")
        self.repo.commit()

        self.repo.write("docs/a.md", "Every check runs.\n\nEvery check runs.\n")
        code, out, _ = self.run_cli()
        self.assertIn("[advisory] docs/a.md:3 (claim-words-totalising)", out)
        self.assertNotIn("quiet", out)

        self.assertEqual(self.mark("docs/a.md:3 claim-words-totalising same runner")[0], 0)
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))
        self.assertIn("copies = 2", (self.repo.root / "claims.checked.toml").read_text())


    def test_a_marked_stale_claims_section_comes_back_when_a_subject_changes(self) -> None:
        register_check(stale_claims.NAME, stale_claims.check)
        self.repo.write("src/cache.py", "CACHE = 1\n")
        self.repo.write("notes/s.md", "## Caching\n\nReads go through src/cache.py.\n")
        self.repo.commit(when=1_700_000_000)
        self.repo.write("src/cache.py", "CACHE = 2\n")
        self.repo.commit(when=1_700_003_600)
        code, out, _ = self.run_cli("--diff-range", "HEAD~1")
        self.assertIn("[advisory] notes/s.md:1 (stale-claims)", out)

        self.assertEqual(
            self.mark("notes/s.md:1 stale-claims cache still read first", diff_range="HEAD~1")[0], 0
        )
        self.assertTrue(
            self.run_cli("--diff-range", "HEAD~1")[1].endswith(", 1 quiet while checked\n")
        )

        self.repo.write("src/cache.py", "CACHE = 3\n")
        code, out, _ = self.run_cli("--diff-range", "HEAD~1")
        self.assertIn("[advisory] notes/s.md:1 (stale-claims)", out)
        self.assertNotIn("quiet", out)

    def stale_section(self) -> None:
        """A `stale-claims` finding at notes/s.md:1 over `HEAD~1`."""

        register_check(stale_claims.NAME, stale_claims.check)
        self.repo.write("src/cache.py", "CACHE = 1\n")
        self.repo.write("notes/s.md", "## Caching\n\nReads go through src/cache.py.\n")
        self.repo.commit(when=1_700_000_000)
        self.repo.write("src/cache.py", "CACHE = 2\n")
        self.repo.commit(when=1_700_003_600)

    def test_a_partial_mark_keeps_its_finding_quiet_and_is_counted_apart(self) -> None:
        self.stale_section()

        code, _, err = self.mark(
            "notes/s.md:1 stale-claims spot-checked the cache paragraph",
            diff_range="HEAD~1",
            partial=True,
        )

        self.assertEqual((code, err), (0, ""))
        self.assertIn('extent = "partial"', (self.repo.root / "claims.checked.toml").read_text())
        out = self.run_cli("--diff-range", "HEAD~1")[1]
        self.assertNotIn("[advisory] notes/s.md:1", out)
        self.assertTrue(out.endswith(", 1 quiet while checked, 1 of them partly\n"))

    def test_only_a_section_or_doc_comment_can_be_marked_partial(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")

        code, _, err = self.mark("docs/a.md:1 claim-words-totalising read half", partial=True)

        self.assertEqual(code, 1)
        self.assertIn(
            "docs/a.md:1 claim-words-totalising read half: "
            "claim-words-totalising findings can't be marked partial",
            err,
        )
        self.assertFalse((self.repo.root / "claims.checked.toml").exists())

    def test_a_partial_mark_can_replace_a_full_one_only_once_it_has_expired(self) -> None:
        self.stale_section()
        self.mark("notes/s.md:1 stale-claims read the whole section", diff_range="HEAD~1")
        sidecar = (self.repo.root / "claims.checked.toml").read_text()

        code, _, err = self.mark(
            "notes/s.md:1 stale-claims spot-checked", diff_range="HEAD~1", partial=True
        )
        self.assertEqual(code, 1)
        self.assertIn(
            "notes/s.md:1 stale-claims spot-checked: "
            "a partial reading can't replace a current full one",
            err,
        )
        self.assertEqual((self.repo.root / "claims.checked.toml").read_text(), sidecar)

        self.repo.write("src/cache.py", "CACHE = 3\n")
        code, _, err = self.mark(
            "notes/s.md:1 stale-claims spot-checked", diff_range="HEAD~1", partial=True
        )
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(
            self.run_cli("--diff-range", "HEAD~1")[1].endswith(
                ", 1 quiet while checked, 1 of them partly\n"
            )
        )

    def test_a_full_mark_replaces_a_partial_one(self) -> None:
        self.stale_section()
        self.mark("notes/s.md:1 stale-claims spot-checked", diff_range="HEAD~1", partial=True)

        code, _, err = self.mark("notes/s.md:1 stale-claims read it all", diff_range="HEAD~1")

        self.assertEqual((code, err), (0, ""))
        sidecar = (self.repo.root / "claims.checked.toml").read_text()
        self.assertNotIn("extent", sidecar)
        self.assertEqual(sidecar.count("[[mark]]"), 1)
        self.assertTrue(
            self.run_cli("--diff-range", "HEAD~1")[1].endswith(", 1 quiet while checked\n")
        )

    def test_an_extent_other_than_full_or_partial_makes_the_sidecar_invalid(self) -> None:
        entry = (
            '[[mark]]\nfile = "docs/a.md"\nmode = "claim-words-totalising"\nunit = "x"\n'
            'copies = 1\nnote = "n"\nextent = {extent}\nsubjects = {{}}\n'
        )
        for extent, valid in (('"full"', True), ('"partial"', True), ('"half"', False), ("1", False)):
            with self.subTest(extent=extent):
                (self.repo.root / "claims.checked.toml").write_text(entry.format(extent=extent))
                out = self.run_cli()[1]
                self.assertEqual(
                    "[GATE] claims.checked.toml:0 (config) is invalid:" in out, not valid, out
                )
                if not valid:
                    self.assertIn("has an 'extent' that is neither \"full\" nor \"partial\"", out)

    def test_a_second_entry_with_the_same_key_makes_the_sidecar_invalid(self) -> None:
        entry = (
            '[[mark]]\nfile = "docs/a.md"\nmode = "{mode}"\nunit = "{unit}"\n'
            'copies = 1\nnote = "n"\nsubjects = {{}}\n'
        )
        first = entry.format(mode="claim-words-totalising", unit="x")
        sidecar = self.repo.root / "claims.checked.toml"
        for other, valid in (
            (first, False),
            (entry.format(mode="claim-words-counts", unit="x"), True),
            (entry.format(mode="claim-words-totalising", unit="y"), True),
        ):
            with self.subTest(other=other):
                sidecar.write_text(first + "\n" + other)
                if valid:
                    self.assertEqual(len(load_marks(self.repo.root)), 2)
                    continue
                with self.assertRaises(ConfigError) as tree:
                    load_marks(self.repo.root)
                self.repo.commit()
                with self.assertRaises(ConfigError) as committed:
                    marks_at(self.repo.root, "HEAD")
                for raised in (tree, committed):
                    self.assertEqual(
                        str(raised.exception),
                        "the [[mark]] at line 9 has the file, mode and unit of the one at line 1",
                    )

    def test_a_sidecar_with_no_extent_loads_unchanged_and_counts_as_full(self) -> None:
        self.stale_section()
        self.mark("notes/s.md:1 stale-claims read the whole section", diff_range="HEAD~1")
        sidecar = (self.repo.root / "claims.checked.toml").read_text()
        self.assertNotIn("extent", sidecar)

        self.assertTrue(
            self.run_cli("--diff-range", "HEAD~1")[1].endswith(", 1 quiet while checked\n")
        )
        self.assertEqual((self.repo.root / "claims.checked.toml").read_text(), sidecar)

    def test_a_partial_mark_counts_as_marked_under_the_flag(self) -> None:
        self.stale_section()
        self.mark("notes/s.md:1 stale-claims spot-checked", diff_range="HEAD~1", partial=True)

        code, out, _ = self.run_cli("--diff-range", "HEAD~1", "--fail-on-unmarked")

        self.assertEqual(code, 0)
        self.assertTrue(out.endswith(", 1 quiet while checked, 1 of them partly, 0 unmarked\n"))

    def test_the_hook_message_counts_partial_marks_apart(self) -> None:
        register_check(spliced_docs.NAME, spliced_docs.check)
        self.repo.write(
            "src/project.rs",
            "/// Loads the project, which is what `load_project` reads.\n"
            "/// The manifest a project is read from.\n"
            "pub struct Manifest {}\n\n"
            "pub fn load_project() {}\n",
        )
        self.mark("src/project.rs:2 spliced-docs-undocumented read line 2 only", partial=True)

        decision = decide_repo(self.repo.root)

        assert decision is not None
        self.assertTrue(decision.message.endswith("1 quiet while checked, 1 of them partly"))

    def test_the_hook_takes_a_partial_mark_as_marked_for_a_listed_check(self) -> None:
        register_check(spliced_docs.NAME, spliced_docs.check)
        self.hook_lists('["spliced-docs"]')
        self.repo.write(
            "src/project.rs",
            "/// Loads the project, which is what `load_project` reads.\n"
            "/// The manifest a project is read from.\n"
            "pub struct Manifest {}\n\n"
            "pub fn load_project() {}\n",
        )
        decision = decide_repo(self.repo.root)
        assert decision is not None
        self.assertTrue(decision.block)

        self.mark("src/project.rs:2 spliced-docs-undocumented read line 2 only", partial=True)
        decision = decide_repo(self.repo.root)

        assert decision is not None
        self.assertFalse(decision.block)

    def test_marking_takes_the_audit_range(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.repo.commit()

        code, _, err = self.mark("docs/a.md:1 claim-words-totalising read it")
        self.assertEqual(code, 1)
        self.assertIn("no advisory finding at docs/a.md:1 (claim-words-totalising)", err)

        code, _, err = self.mark("docs/a.md:1 claim-words-totalising read it", diff_range="HEAD~1")
        self.assertEqual((code, err), (0, ""))
        self.assertTrue(
            self.run_cli("--diff-range", "HEAD~1")[1].endswith(", 1 quiet while checked\n")
        )

    def test_one_bad_entry_writes_nothing_and_names_each_bad_entry(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n\nOnly one runs.\n")

        code, _, err = self.mark(
            "docs/a.md:1 claim-words-totalising read it",
            "docs/a.md:3 claim-words-totalising",
            "docs/a.md:9 claim-words-totalising read it",
        )

        self.assertEqual(code, 1)
        self.assertIn("docs/a.md:3 claim-words-totalising: needs a note", err)
        self.assertIn("docs/a.md:9 claim-words-totalising read it: no advisory finding", err)
        self.assertNotIn("docs/a.md:1", err)
        self.assertFalse((self.repo.root / "claims.checked.toml").exists())

    def test_a_batch_runs_the_checks_once(self) -> None:
        calls = []

        def counting(repo_root, diff_range, config):
            calls.append(diff_range)
            return claim_words.check(repo_root, diff_range, config)

        clear_registry()
        register_check(claim_words.NAME, counting)
        self.repo.write("docs/a.md", "Every check runs.\n\nOnly one runs.\n\nNever two.\n")

        code, out, _ = self.mark(
            "docs/a.md:1 claim-words-totalising a",
            "docs/a.md:3 claim-words-totalising b",
            "docs/a.md:5 claim-words-totalising c",
            by="reader",
        )

        self.assertEqual((code, len(calls)), (0, 1))
        self.assertEqual(out, "marked 3 finding(s) in claims.checked.toml\n")
        self.assertEqual(
            (self.repo.root / "claims.checked.toml").read_text().count('by = "reader"'), 3
        )

    def test_re_marking_replaces_the_entry_and_keeps_others_as_written(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n\nOnly one runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising first")
        sidecar = self.repo.root / "claims.checked.toml"
        sidecar.write_text("# audit of docs/a.md\n" + sidecar.read_text())
        self.mark("docs/a.md:3 claim-words-totalising other")
        self.mark("docs/a.md:1 claim-words-totalising second")

        text = sidecar.read_text()
        self.assertEqual(text.count("[[mark]]"), 2)
        self.assertNotIn("first", text)
        # The comment stays directly above the entry that replaced the one
        # it was above.
        self.assertIn('note = "second"', text.split("# audit of docs/a.md\n")[1].split("\n\n")[0])

    def test_re_marking_keeps_the_comment_above_the_next_entry(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n\nOnly one runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising first", "docs/a.md:3 claim-words-totalising other")
        sidecar = self.repo.root / "claims.checked.toml"
        (other,) = [e for e in sidecar.read_text().split("\n\n") if 'note = "other"' in e]
        sidecar.write_text(sidecar.read_text().replace(other, f"# about the other\n{other}"))

        self.mark("docs/a.md:1 claim-words-totalising second")

        self.assertIn(f"# about the other\n{other}", sidecar.read_text())

    def test_gate_findings_and_unmarkable_modes_are_refused(self) -> None:
        register_check(
            "gatey",
            lambda repo_root, diff_range, config: [
                Finding(file="docs/a.md", line=1, message="bad", mode="gatey", gate=True),
                Finding(file="docs/a.md", line=2, message="fyi", mode="gatey-advice", gate=False),
            ],
        )

        code, _, err = self.mark("docs/a.md:1 gatey read it", "docs/a.md:2 gatey-advice read it")

        self.assertEqual(code, 1)
        self.assertIn("docs/a.md:1 gatey read it: a gate finding can't be marked", err)
        self.assertIn("docs/a.md:2 gatey-advice read it: gatey-advice findings can't be marked", err)

    def test_a_hand_written_entry_for_a_gate_finding_quiets_nothing(self) -> None:
        register_check(
            "gatey",
            lambda repo_root, diff_range, config: [
                Finding(file="docs/a.md", line=1, message="bad", mode="gatey", gate=True)
            ],
        )
        self.repo.write("docs/a.md", "Every check runs.\n")
        (self.repo.root / "claims.checked.toml").write_text(
            '[[mark]]\nfile = "docs/a.md"\nmode = "gatey"\nunit = "x"\ncopies = 1\n'
            'note = "n"\nsubjects = {}\n'
        )

        code, out, _ = self.run_cli()

        self.assertEqual(code, 1)
        self.assertIn("[GATE] docs/a.md:1 (gatey) bad", out)
        self.assertIn("[advisory] claims.checked.toml:1 (checked-mark)", out)

    def test_a_mark_whose_sentence_was_deleted_is_an_orphan(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it")
        self.repo.commit()
        self.repo.write("README.md", "Readme, edited.\n")
        self.assertEqual(self.run_cli()[1], "1 checked, 0 finding(s), 0 gate failure(s)\n")

        self.repo.write("docs/a.md", "Some checks run.\n")
        code, out, _ = self.run_cli()

        self.assertIn(
            "[advisory] claims.checked.toml:1 (checked-mark) checked mark "
            "(claim-words-totalising) is for a sentence no longer in docs/a.md",
            out,
        )

    def prune(self, *entries: str) -> tuple[int, str, str]:
        return self.run_cli("mark-checked", "--prune", "-", stdin="".join(e + "\n" for e in entries))

    def test_prune_removes_a_reworded_sentences_mark(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it")
        self.repo.write("docs/a.md", "Some checks run.\n")

        code, out, err = self.prune()

        self.assertEqual((code, out, err), (0, "pruned 1 orphaned mark(s) from claims.checked.toml\n", ""))
        self.assertNotIn("(checked-mark)", self.run_cli()[1])

    def test_one_prune_call_removes_the_orphan_and_marks_the_reworded_sentence(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it")
        self.repo.write("docs/a.md", "Every check runs twice.\n")

        code, out, err = self.prune("docs/a.md:1 claim-words-totalising read it again")

        self.assertEqual(
            (code, out, err),
            (
                0,
                "marked 1 finding(s) in claims.checked.toml\n"
                "pruned 1 orphaned mark(s) from claims.checked.toml\n",
                "",
            ),
        )
        text = (self.repo.root / "claims.checked.toml").read_text()
        self.assertEqual(text.count("[[mark]]"), 1)
        self.assertIn('note = "read it again"', text)
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

    def test_prune_removes_a_mark_whose_file_is_gone_and_one_with_an_unmarkable_mode(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it")
        sidecar = self.repo.root / "claims.checked.toml"
        sidecar.write_text(
            sidecar.read_text()
            + '\n[[mark]]\nfile = "README.md"\nmode = "gatey"\nunit = "x"\ncopies = 1\n'
            'note = "n"\nsubjects = {}\n'
        )
        (self.repo.root / "docs/a.md").unlink()

        code, out, _ = self.prune()

        self.assertEqual((code, out), (0, "pruned 2 orphaned mark(s) from claims.checked.toml\n"))
        self.assertEqual(sidecar.read_text().count("[[mark]]"), 0)

    def test_prune_keeps_an_expired_mark_whose_sentence_is_still_there(self) -> None:
        self.repo.write("src/cache.py", "CACHE = 1\n")
        self.repo.commit()
        self.repo.write("docs/a.md", "Every read goes through src/cache.py first.\n")
        self.mark("docs/a.md:1 claim-words-totalising read cache.py")
        self.repo.write("src/cache.py", "CACHE = 2\n")
        before = (self.repo.root / "claims.checked.toml").read_text()

        code, out, _ = self.prune()

        self.assertEqual((code, out), (0, "pruned 0 orphaned mark(s) from claims.checked.toml\n"))
        self.assertEqual((self.repo.root / "claims.checked.toml").read_text(), before)

    def test_prune_keeps_a_mark_whose_file_holds_fewer_copies_than_recorded(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n\nEvery check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it")
        self.assertIn("copies = 2", (self.repo.root / "claims.checked.toml").read_text())
        self.repo.write("docs/a.md", "Every check runs.\n")

        code, out, _ = self.prune()

        self.assertEqual((code, out), (0, "pruned 0 orphaned mark(s) from claims.checked.toml\n"))
        self.assertIn("[[mark]]", (self.repo.root / "claims.checked.toml").read_text())

    def test_prune_keeps_every_other_entry_and_comment_as_written(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n\nOnly one runs.\n\nNever two.\n")
        self.mark(
            "docs/a.md:1 claim-words-totalising a",
            "docs/a.md:3 claim-words-totalising b",
            "docs/a.md:5 claim-words-totalising c",
        )
        sidecar = self.repo.root / "claims.checked.toml"
        first, second, third = sorted(
            sidecar.read_text().rstrip("\n").split("\n\n"), key=lambda e: e.split("note = ")[1]
        )
        third += "\n"
        # Out of key order, as a hand edit might leave it: `b` sorts first.
        sidecar.write_text(
            f"# audit of docs/a.md\n\n{first}\n\n\n# second\n{second}\n\n# third\n{third}"
        )
        self.repo.write("docs/a.md", "Every check runs.\n\nOnly two run.\n\nNever two.\n")

        code, out, _ = self.prune()

        self.assertEqual((code, out), (0, "pruned 1 orphaned mark(s) from claims.checked.toml\n"))
        # `# second` is the pruned entry's own, and goes with it.
        self.assertEqual(
            sidecar.read_text(), f"# audit of docs/a.md\n\n{first}\n\n\n# third\n{third}"
        )

    def test_pruning_never_takes_the_comment_of_a_replaced_entry_above_it(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n\nOnly one runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising a", "docs/a.md:3 claim-words-totalising b")
        sidecar = self.repo.root / "claims.checked.toml"
        (first,) = [e for e in sidecar.read_text().split("\n\n") if 'note = "a"' in e]
        sidecar.write_text(sidecar.read_text().replace(first, f"# about the first\n{first}"))
        self.repo.write("docs/a.md", "Every check runs.\n\nOnly two run.\n")

        code, _, _ = self.prune("docs/a.md:1 claim-words-totalising a again")

        self.assertEqual(code, 0)
        self.assertIn("# about the first\n", sidecar.read_text())

    def test_a_bad_entry_with_prune_writes_nothing(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it")
        self.repo.write("docs/a.md", "Some checks run.\n")
        before = (self.repo.root / "claims.checked.toml").read_text()

        code, out, err = self.prune("docs/a.md:9 claim-words-totalising read it")

        self.assertEqual((code, out), (1, ""))
        self.assertIn("nothing marked: 1 bad entry", err)
        self.assertEqual((self.repo.root / "claims.checked.toml").read_text(), before)

    def test_prune_with_nothing_to_do_succeeds_and_says_so(self) -> None:
        code, out, err = self.prune()

        self.assertEqual(
            (code, out, err), (0, "pruned 0 orphaned mark(s) from claims.checked.toml\n", "")
        )
        self.assertFalse((self.repo.root / "claims.checked.toml").exists())
        # Without `--prune`, no entries is still an error.
        self.assertEqual(self.mark()[0], 1)

    def test_prune_alone_at_a_terminal_does_not_wait_for_entries(self) -> None:
        stdin = mock.Mock()
        stdin.isatty.return_value = True
        stdin.read.side_effect = AssertionError("read stdin")
        out = io.StringIO()
        with mock.patch("sys.stdin", stdin), contextlib.redirect_stdout(out):
            code = main(["mark-checked", "--prune", "--repo-root", str(self.repo.root)])

        self.assertEqual(
            (code, out.getvalue()), (0, "pruned 0 orphaned mark(s) from claims.checked.toml\n")
        )

    def test_an_invalid_sidecar_blocks_at_commit_time(self) -> None:
        for text in ("[[mark]\n", '[[mark]]\nfile = "docs/a.md"\n'):
            with self.subTest(text=text):
                (self.repo.root / "claims.checked.toml").write_text(text)
                decision = decide_repo(self.repo.root)
                assert decision is not None
                self.assertTrue(decision.block)
                self.assertIn("[GATE] claims.checked.toml:0 (config) is invalid:", decision.message)

    def test_the_hook_message_counts_quiet_findings(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n\nOnly one runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it")

        decision = decide_repo(self.repo.root)

        assert decision is not None
        self.assertFalse(decision.block)
        self.assertTrue(decision.message.endswith("\n1 quiet while checked"))
        self.assertNotIn("docs/a.md:1", decision.message)


    def hook_lists(self, value: str) -> None:
        self.repo.write("claims.toml", CONFIG + f"\n[hook]\nfail_on_unmarked = {value}\n")

    def test_the_hook_blocks_on_an_unmarked_finding_from_a_listed_check(self) -> None:
        self.hook_lists('["claim-words"]')
        self.repo.write("docs/a.md", "Every check runs.\n")

        decision = decide_repo(self.repo.root)

        assert decision is not None
        self.assertTrue(decision.block)
        self.assertIn("docs/a.md:1 (claim-words-totalising)", decision.message)
        self.assertTrue(
            decision.message.endswith(
                "\nfailing: 1 unmarked advisory finding(s); fix or mark each"
            )
        )

        self.mark("docs/a.md:1 claim-words-totalising read it")
        decision = decide_repo(self.repo.root)

        assert decision is not None
        self.assertFalse(decision.block)
        self.assertEqual(decision.message, "1 quiet while checked")


    def test_the_hook_lets_through_an_unmarked_finding_from_an_unlisted_check(self) -> None:
        self.hook_lists('["restatement"]')
        self.repo.write("docs/a.md", "Every check runs.\n")

        decision = decide_repo(self.repo.root)

        assert decision is not None
        self.assertFalse(decision.block)
        self.assertNotIn("failing:", decision.message)

    def orphan(self, mode: str) -> None:
        """An orphaned mark for `mode`, on a sentence since reworded."""
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it")
        sidecar = self.repo.root / "claims.checked.toml"
        sidecar.write_text(
            sidecar.read_text().replace('"claim-words-totalising"', f'"{mode}"')
        )
        self.repo.write("docs/a.md", "Some checks run.\n")

    def test_the_hook_blocks_on_an_orphaned_mark_only_for_a_listed_check(self) -> None:
        self.hook_lists('["claim-words"]')
        for mode, blocks in (
            ("claim-words-totalising", True),
            ("stale-claims", False),
            ("unmarkable", False),
        ):
            with self.subTest(mode=mode):
                self.orphan(mode)

                decision = decide_repo(self.repo.root)

                assert decision is not None
                self.assertIn(f"(checked-mark) checked mark ({mode})", decision.message)
                self.assertEqual(decision.block, blocks)

    def test_the_hook_lets_through_an_orphan_of_a_listed_check_silenced_at_commit(self) -> None:
        self.repo.write(
            "claims.toml",
            CONFIG + 'enabled = false\n\n[hook]\nfail_on_unmarked = ["claim-words"]\n',
        )
        self.orphan("claim-words-totalising")

        decision = decide_repo(self.repo.root)

        assert decision is not None
        self.assertIn("(checked-mark)", decision.message)
        self.assertFalse(decision.block)


    def test_a_restatement_unit_is_the_surviving_line_and_its_retracted_run(self) -> None:
        register_check(restatement.NAME, restatement.check)
        line = "The cache is flushed whenever the configuration file changes on disk.\n"
        self.repo.write("docs/x.md", "# X\n\n" + line)
        self.repo.write("docs/y.md", "# Y\n\n" + line)
        self.repo.commit()
        self.repo.write("docs/x.md", "# X\n")
        code, out, _ = self.run_cli()
        self.assertIn("docs/y.md:3 (restatement-whole-line)", out)

        self.mark("docs/y.md:3 restatement-whole-line y still holds")

        code, out, _ = self.run_cli()
        self.assertNotIn("restatement-whole-line", out)
        self.assertIn("docs/y.md:3 (restatement-ngram)", out)
        self.assertTrue(out.endswith(", 1 quiet while checked\n"))

    def test_a_spliced_docs_unit_is_the_doc_comment_run(self) -> None:
        register_check(spliced_docs.NAME, spliced_docs.check)
        source = (
            "/// Loads the project, which is what `load_project` reads.\n"
            "/// The manifest a project is read from.\n"
            "pub struct Manifest {}\n\n"
            "pub fn load_project() {}\n"
        )
        self.repo.write("src/project.rs", source)
        self.mark("src/project.rs:2 spliced-docs-undocumented split on purpose")
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

        self.repo.write("src/project.rs", source.replace("reads.", "loads."))
        code, out, _ = self.run_cli()
        self.assertIn("[advisory] src/project.rs:2 (spliced-docs-undocumented)", out)
        self.assertNotIn("quiet", out)


    def test_a_mark_on_one_of_two_same_named_sections_leaves_the_other_shown(self) -> None:
        register_check(stale_claims.NAME, stale_claims.check)
        self.repo.write("src/a.py", "A = 1\n")
        self.repo.write("src/b.py", "B = 1\n")
        self.repo.write(
            "notes/s.md",
            "## Usage\n\nCall src/a.py first.\n\n## Usage\n\nCall src/b.py first.\n",
        )
        self.repo.commit(when=1_700_000_000)
        self.repo.write("src/a.py", "A = 2\n")
        self.repo.write("src/b.py", "B = 2\n")
        self.repo.commit(when=1_700_003_600)
        self.mark("notes/s.md:1 stale-claims a.py still first", diff_range="HEAD~1")

        code, out, _ = self.run_cli("--diff-range", "HEAD~1")

        self.assertIn("[advisory] notes/s.md:5 (stale-claims)", out)
        self.assertNotIn("notes/s.md:1", out)
        self.assertTrue(out.endswith(", 1 quiet while checked\n"))

    def test_a_sidecar_that_is_not_utf8_is_invalid_not_a_crash(self) -> None:
        (self.repo.root / "claims.checked.toml").write_bytes(b"\xff\xfe")

        code, out, _ = self.run_cli()

        self.assertEqual(code, 1)
        self.assertIn("[GATE] claims.checked.toml:0 (config) is invalid:", out)

    def test_a_subject_missing_from_disk_does_not_kill_the_mark(self) -> None:
        self.repo.write("src/gone.py", "G = 1\n")
        self.repo.commit()
        (self.repo.root / "src/gone.py").unlink()
        self.repo.write("docs/a.md", "Every read goes through src/gone.py first.\n")
        self.assertEqual(self.mark("docs/a.md:1 claim-words-totalising gone on purpose")[0], 0)

        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

    def test_a_missing_entries_file_is_an_error_not_a_traceback(self) -> None:
        code, _, err = self.run_cli("mark-checked", "no-such-file.txt")

        self.assertEqual(code, 2)
        self.assertIn("no-such-file.txt", err)

    def test_a_mark_survives_a_rebase_onto_a_new_base(self) -> None:
        self.repo.write("src/cache.py", "CACHE = 1\n")
        self.repo.commit()
        self.git("branch", "base")
        self.repo.write("docs/a.md", "Every read goes through src/cache.py first.\n")
        self.mark("docs/a.md:1 claim-words-totalising read cache.py")
        self.repo.commit()
        self.git("checkout", "-q", "base")
        self.repo.write("NOTES.md", "Unrelated.\n")
        self.repo.commit()
        self.git("checkout", "-q", "-")
        self.git("rebase", "-q", "base")

        self.assertTrue(
            self.run_cli("--diff-range", "HEAD~1")[1].endswith(
                ", 1 quiet while checked, 1 mark(s) added in range\n"
            )
        )


    def outside_file(self) -> str:
        # A small regular file outside the repository, never a device: if
        # the guard regresses, the test fails rather than reading forever.
        handle = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
        handle.write("outside\n")
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_a_path_outside_the_repository_is_invalid(self) -> None:
        outside = json.dumps(self.outside_file())
        entry = '[[mark]]\nfile = {file}\nmode = "claim-words-totalising"\nunit = "x"\ncopies = 1\nnote = "n"\nsubjects = {{ {subject} = "h" }}\n'
        for file, subject in (
            (outside, '"docs/a.md"'),
            ('"docs/a.md"', outside),
            ('"docs/a.md"', '"../outside.txt"'),
            ('"docs/../../outside.md"', '"docs/a.md"'),
        ):
            with self.subTest(file=file, subject=subject):
                (self.repo.root / "claims.checked.toml").write_text(
                    entry.format(file=file, subject=subject)
                )
                code, out, _ = self.run_cli()
                self.assertEqual(code, 1)
                self.assertIn("[GATE] claims.checked.toml:0 (config) is invalid:", out)

    def test_a_symlink_out_of_the_repository_is_never_read(self) -> None:
        self.repo.write("docs/a.md", "Every read goes through src/cache.py first.\n")
        (self.repo.root / "src").mkdir()
        (self.repo.root / "src/cache.py").symlink_to(self.outside_file())
        self.git("add", "src/cache.py")

        code, _, err = self.mark("docs/a.md:1 claim-words-totalising read it")

        self.assertEqual((code, err), (0, ""))
        self.assertIn("subjects = {}", (self.repo.root / "claims.checked.toml").read_text())


    def test_a_sentence_sharing_a_line_with_an_earlier_one_is_its_own_unit(self) -> None:
        self.repo.write("docs/a.md", "Intro wraps onto\nthe next line. It always works.\n")
        self.mark("docs/a.md:2 claim-words-totalising read it")

        self.repo.write("docs/a.md", "Intro wraps onto\nthe next page. It always works.\n")
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

        self.repo.write("docs/a.md", "Intro wraps onto\nthe next line. It never works.\n")
        self.assertNotIn("quiet", self.summary())

    def test_a_bad_module_reference_scope_is_not_blamed_on_the_sidecar(self) -> None:
        self.repo.write("claims.toml", CONFIG + "\n[stale-claims]\nmodule_reference_scope = 3\n")
        register_check(stale_claims.NAME, lambda repo_root, diff_range, config: [])
        self.repo.write("docs/a.md", "Every check runs.\n")

        code, _, err = self.mark("docs/a.md:1 claim-words-totalising read it")

        self.assertEqual((code, err), (0, ""))
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

    def test_a_stale_claims_section_with_no_heading_can_be_marked(self) -> None:
        register_check(stale_claims.NAME, stale_claims.check)
        self.repo.write("src/x.py", "X = 1\n")
        self.repo.write("notes/n.md", "Reads go through src/x.py.\n")
        self.repo.commit(when=1_700_000_000)
        self.repo.write("src/x.py", "X = 2\n")
        self.repo.commit(when=1_700_003_600)

        code, _, err = self.mark("notes/n.md:1 stale-claims x still read", diff_range="HEAD~1")

        self.assertEqual((code, err), (0, ""))
        self.assertTrue(
            self.run_cli("--diff-range", "HEAD~1")[1].endswith(", 1 quiet while checked\n")
        )

    def test_a_finding_on_a_fenced_line_can_be_marked(self) -> None:
        register_check(
            "fenced",
            lambda repo_root, diff_range, config: [
                Finding(file="docs/a.md", line=2, message="m", mode="judgment-agent-added", gate=False)
            ],
        )
        self.repo.write("docs/a.md", "```\nload(`foo`)\n```\n")

        code, _, err = self.mark("docs/a.md:2 judgment-agent-added foo is real")

        self.assertEqual((code, err), (0, ""))
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

    def test_an_error_applying_marks_is_reported_not_raised(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it")

        with mock.patch("claims.checked.tracked_files", side_effect=FileNotFoundError("git")):
            code, out, _ = self.run_cli()

        self.assertEqual(code, 1)
        self.assertIn("[advisory] docs/a.md:1 (claim-words-totalising)", out)
        self.assertIn("(checked-marks) check 'checked-marks' crashed: FileNotFoundError", out)

    def test_a_sidecar_symlinked_out_of_the_repository_is_invalid_and_never_written(self) -> None:
        outside = self.outside_file()
        Path(outside).write_text("")
        (self.repo.root / "claims.checked.toml").symlink_to(outside)
        self.repo.write("docs/a.md", "Every check runs.\n")

        code, out, _ = self.run_cli()
        self.assertIn("[GATE] claims.checked.toml:0 (config) is invalid:", out)

        code, _, _ = self.mark("docs/a.md:1 claim-words-totalising read it")
        self.assertEqual(code, 2)
        self.assertEqual(Path(outside).read_text(), "")

    def test_a_path_with_a_space_can_be_marked(self) -> None:
        self.repo.write("claims.toml", '[claim-words]\nfiles = ["docs/*"]\n')
        self.repo.write("docs/user guide.md", "Every check runs.\n")

        code, _, err = self.mark("docs/user guide.md:1 claim-words-totalising read it")

        self.assertEqual((code, err), (0, ""))
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

    def test_a_stale_claims_mark_records_subjects_named_below_a_fenced_hash_line(self) -> None:
        # The section runs past the fence's `# comment`, so `src/a.py`
        # below it is one of the mark's subjects and changing it expires
        # the mark.
        register_check(stale_claims.NAME, stale_claims.check)
        self.repo.write("src/a.py", "V = 1\n")
        self.repo.write("notes/s.md", "# Real\n\n```sh\n# comment\n```\n\nsrc/a.py\n")
        self.repo.commit(when=1_700_000_000)
        self.repo.write("src/a.py", "V = 2\n")
        self.repo.commit(when=1_700_003_600)
        code, _, err = self.mark("notes/s.md:1 stale-claims a read", diff_range="HEAD~1")
        self.assertEqual((code, err), (0, ""))

        self.repo.write("src/a.py", "V = 3\n")
        _, out, _ = self.run_cli("--diff-range", "HEAD~1")

        self.assertIn("[advisory] notes/s.md:1 (stale-claims)", out)

    def test_a_repeated_heading_never_shares_a_unit_with_a_numbered_one(self) -> None:
        register_check(stale_claims.NAME, stale_claims.check)
        for name in ("a", "b", "c"):
            self.repo.write(f"src/{name}.py", "V = 1\n")
        self.repo.write(
            "notes/s.md",
            "# Foo\n\nsrc/a.py\n\n# Foo\n\nsrc/b.py\n\n# Foo 1\n\nsrc/c.py\n",
        )
        self.repo.commit(when=1_700_000_000)
        for name in ("a", "b", "c"):
            self.repo.write(f"src/{name}.py", "V = 2\n")
        self.repo.commit(when=1_700_003_600)
        self.mark("notes/s.md:5 stale-claims b read", diff_range="HEAD~1")

        code, out, _ = self.run_cli("--diff-range", "HEAD~1")

        self.assertIn("[advisory] notes/s.md:9 (stale-claims)", out)
        self.assertNotIn("copies = 2", (self.repo.root / "claims.checked.toml").read_text())


    def test_a_judgment_agent_mark_is_on_the_sentence_holding_the_citation(self) -> None:
        register_check(
            "cites",
            lambda repo_root, diff_range, config: [
                Finding(
                    file="docs/a.md", line=2, message="cites `foo`, removed by this diff",
                    mode="judgment-agent-removed", gate=False,
                )
            ],
        )
        self.repo.write("docs/a.md", "The first sentence wraps\nonto `foo` here. Second one starts.\n")
        self.mark("docs/a.md:2 judgment-agent-removed foo is gone on purpose")

        self.repo.write("docs/a.md", "The first sentence wraps\nonto `foo` here. Second one ends.\n")
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

        self.repo.write("docs/a.md", "The first sentence moves\nonto `foo` here. Second one starts.\n")
        self.assertNotIn("quiet", self.summary())

    def test_one_entry_marks_every_finding_of_its_mode_at_its_citation(self) -> None:
        self.repo.write("docs/a.md", "Always quick. Always safe.\n")

        self.assertEqual(self.mark("docs/a.md:1 claim-words-totalising read both")[0], 0)

        self.assertTrue(self.summary().endswith(", 2 quiet while checked"))

    def test_a_sidecar_symlinked_inside_the_repository_is_invalid_and_never_written(self) -> None:
        self.repo.write("empty.py", "")
        (self.repo.root / "claims.checked.toml").symlink_to("empty.py")
        self.repo.write("docs/a.md", "Every check runs.\n")

        code, out, _ = self.run_cli()
        self.assertIn("[GATE] claims.checked.toml:0 (config) is invalid:", out)

        self.assertEqual(self.mark("docs/a.md:1 claim-words-totalising read it")[0], 2)
        self.assertEqual((self.repo.root / "empty.py").read_text(), "")

    def test_a_fenced_copy_of_a_marked_sentence_is_not_a_copy(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it")

        self.repo.write("docs/a.md", "Every check runs.\n\n```\nEvery check runs.\n```\n")

        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

    def test_an_unmarked_finding_fails_under_the_flag_until_it_is_marked(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")

        code, out, _ = self.run_cli("--fail-on-unmarked")

        self.assertEqual(code, 3)
        self.assertEqual(
            out.splitlines()[-2:],
            [
                "1 checked, 1 finding(s), 0 gate failure(s), 1 unmarked",
                "failing: 1 unmarked advisory finding(s); fix or mark each",
            ],
        )

        self.mark("docs/a.md:1 claim-words-totalising read the runner")
        code, out, _ = self.run_cli("--fail-on-unmarked")

        self.assertEqual(code, 0)
        self.assertEqual(
            out.splitlines(),
            ["1 checked, 0 finding(s), 0 gate failure(s), 1 quiet while checked, 0 unmarked"],
        )

    def test_the_flag_covers_only_the_checks_it_names(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")

        code, out, _ = self.run_cli("--fail-on-unmarked=restatement")

        self.assertEqual(code, 0)
        self.assertTrue(out.endswith(", 0 unmarked\n"))

    def test_an_orphaned_mark_fails_under_the_flag_until_its_entry_is_deleted(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it")
        self.repo.write("docs/a.md", "Some checks run.\n")

        # Whatever checks the flag names: deleting the entry resolves it.
        code, out, _ = self.run_cli("--fail-on-unmarked=restatement")
        self.assertEqual(code, 3)
        self.assertIn("(checked-mark)", out)

        (self.repo.root / "claims.checked.toml").unlink()
        self.assertEqual(self.run_cli("--fail-on-unmarked")[0], 0)

    def test_an_advisory_finding_no_mark_can_hold_never_fails_the_run(self) -> None:
        register_check(
            "unmarkable",
            lambda repo_root, diff_range, config: [
                Finding(file="a.md", line=1, message="fyi", mode="unmarkable", gate=False)
            ],
        )

        code, out, _ = self.run_cli("--fail-on-unmarked")

        self.assertEqual(code, 0)
        self.assertTrue(out.endswith(", 0 unmarked\n"))

    def test_a_gate_finding_exits_1_ahead_of_unmarked_findings(self) -> None:
        register_check(
            "gatey",
            lambda repo_root, diff_range, config: [
                Finding(file="docs/a.md", line=1, message="bad", mode="gatey", gate=True)
            ],
        )
        self.repo.write("docs/a.md", "Every check runs.\n")

        code, out, _ = self.run_cli("--fail-on-unmarked")

        self.assertEqual(code, 1)
        self.assertTrue(out.endswith("1 gate failure(s), 1 unmarked\n"))

    def test_the_summary_counts_the_mark_entries_the_range_added(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n\nEvery rule holds.\n")
        self.assertEqual(self.mark("docs/a.md:1 claim-words-totalising read it")[0], 0)
        self.repo.commit()
        base = self.repo.short_head()
        # Marked over the commit that added both sentences.
        for entry in ("docs/a.md:1 claim-words-totalising read it again", "docs/a.md:3 claim-words-totalising read it"):
            self.assertEqual(self.mark(entry, diff_range="HEAD~1")[0], 0)
        self.repo.write("docs/a.md", "Every check runs.\n\nEvery rule holds.\n\nEvery check passes.\n")
        self.assertEqual(self.mark("docs/a.md:5 claim-words-totalising read it")[0], 0)
        self.repo.commit()

        # Re-marking the first finding replaced its entry, which adds none.
        self.assertEqual(
            self.run_cli("--diff-range", base)[1].splitlines()[-1],
            "1 checked, 0 finding(s), 0 gate failure(s), 1 quiet while checked, "
            "2 mark(s) added in range",
        )

    def test_a_name_that_is_not_a_markable_check_is_a_usage_error(self) -> None:
        err = io.StringIO()
        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stderr(err):
            main(["--fail-on-unmarked=claim-words,nope", "--repo-root", str(self.repo.root)])

        self.assertEqual(raised.exception.code, 2)
        self.assertIn("--fail-on-unmarked: nope is not a markable check", err.getvalue())


    QUIET = ", 1 quiet while checked"
    SHOWN = "1 checked, 1 finding(s), 0 gate failure(s)"
    LOG = "# Log\n\n## Unreleased\n\n- Next.\n\n## 1.0\n\n- First.\n"

    def mark_release_claim(self, cited: str, log: str = "CHANGELOG.md") -> None:
        """A marked sentence citing `cited`, with `log` committed holding `LOG`."""

        self.repo.write(log, self.LOG)
        self.repo.commit()
        self.repo.write("docs/a.md", f"Every release is in {cited}.\n")
        self.assertEqual(self.mark("docs/a.md:1 claim-words-totalising read the log")[0], 0)

    def test_a_mark_on_a_changelog_holds_after_an_append_at_either_end(self) -> None:
        self.mark_release_claim("`CHANGELOG.md`")

        self.repo.write("CHANGELOG.md", self.LOG.replace("- Next.", "- Newer.\n- Next."))
        self.assertTrue(self.summary().endswith(self.QUIET))
        self.repo.write("CHANGELOG.md", self.LOG + "- Also.\n")
        self.assertTrue(self.summary().endswith(self.QUIET))

    def test_a_mark_on_a_changelog_expires_when_a_line_changes_or_goes(self) -> None:
        self.mark_release_claim("`CHANGELOG.md`")

        self.repo.write("CHANGELOG.md", self.LOG.replace("## Unreleased", "## 1.1"))
        self.assertEqual(self.summary(), self.SHOWN)
        self.repo.write("CHANGELOG.md", self.LOG.replace("- First.\n", ""))
        self.assertEqual(self.summary(), self.SHOWN)

    def test_a_mark_whose_recorded_blob_is_not_in_the_store_expires(self) -> None:
        self.mark_release_claim("`CHANGELOG.md`")
        # Never staged, so its blob is in no object store.
        (self.repo.root / "CHANGELOG.md").write_text(self.LOG + "- Unstaged.\n")
        self.assertEqual(self.mark("docs/a.md:1 claim-words-totalising read the log")[0], 0)
        self.assertTrue(self.summary().endswith(self.QUIET))

        (self.repo.root / "CHANGELOG.md").write_text(self.LOG + "- Unstaged.\n- More.\n")
        self.assertEqual(self.summary(), self.SHOWN)

    def test_a_mark_whose_recorded_blob_a_rewrite_left_dangling_expires(self) -> None:
        self.mark_release_claim("`CHANGELOG.md`")
        # Amending the commit away leaves the recorded blob in this
        # clone's store, but in no commit `HEAD` reaches: a clone that
        # fetched the branch never had it.
        self.repo.write("CHANGELOG.md", self.LOG.replace("- First.", "- Initial."))
        subprocess.run(
            ["git", "-C", str(self.repo.root), "commit", "-q", "--amend", "--no-edit", "--", "CHANGELOG.md"],
            check=True,
        )
        (self.repo.root / "CHANGELOG.md").write_text(self.LOG + "- Also.\n")

        self.assertEqual(self.summary(), self.SHOWN)

    def test_a_mark_whose_recorded_blob_is_in_an_ancestor_holds_after_an_append(self) -> None:
        self.mark_release_claim("`CHANGELOG.md`")
        self.repo.write("CHANGELOG.md", self.LOG + "- Also.\n")
        subprocess.run(
            ["git", "-C", str(self.repo.root), "commit", "-q", "-m", "log", "--", "CHANGELOG.md"],
            check=True,
        )

        (self.repo.root / "CHANGELOG.md").write_text(self.LOG + "- Also.\n- More.\n")
        self.assertTrue(self.summary().endswith(self.QUIET))

    def test_a_mark_whose_recorded_blob_is_staged_holds_after_an_append(self) -> None:
        self.mark_release_claim("`CHANGELOG.md`")
        self.repo.write("CHANGELOG.md", self.LOG + "- Staged.\n")
        self.assertEqual(self.mark("docs/a.md:1 claim-words-totalising read the log")[0], 0)

        (self.repo.root / "CHANGELOG.md").write_text(self.LOG + "- Staged.\n- More.\n")
        self.assertTrue(self.summary().endswith(self.QUIET))

    def test_an_unchanged_append_only_file_holds_without_reading_its_history(self) -> None:
        self.mark_release_claim("`CHANGELOG.md`")

        with mock.patch("claims.checked.path_blobs", side_effect=AssertionError("read history")):
            self.assertTrue(self.summary().endswith(self.QUIET))

    def test_a_mark_on_a_changelog_checked_out_with_crlf_holds_after_an_append(self) -> None:
        # Stored with `\n`, checked out with `\r\n`: the recorded blob has
        # to be the one git stored, not the bytes on disk.
        self.repo.config("core.autocrlf", "true")
        crlf = self.LOG.replace("\n", "\r\n").encode()
        (self.repo.root / "CHANGELOG.md").write_bytes(crlf)
        self.repo.commit()
        self.repo.write("docs/a.md", "Every release is in `CHANGELOG.md`.\n")
        self.assertEqual(self.mark("docs/a.md:1 claim-words-totalising read the log")[0], 0)

        (self.repo.root / "CHANGELOG.md").write_bytes(crlf + b"- Also.\r\n")
        self.assertTrue(self.summary().endswith(self.QUIET))

    def test_a_carriage_return_inside_a_changelog_line_does_not_split_it(self) -> None:
        log = self.LOG.replace("- First.", "- First\rpart.")
        self.repo.write("CHANGELOG.md", log)
        self.repo.commit()
        self.repo.write("docs/a.md", "Every release is in `CHANGELOG.md`.\n")
        self.assertEqual(self.mark("docs/a.md:1 claim-words-totalising read the log")[0], 0)

        self.repo.write("CHANGELOG.md", log + "- Also.\n")
        self.assertTrue(self.summary().endswith(self.QUIET))

    def test_a_listed_append_only_file_holds_after_an_append(self) -> None:
        self.repo.write("claims.toml", CONFIG + '\n[subjects]\nappend_only = "RELEASES.md"\n')
        self.mark_release_claim("`RELEASES.md`", log="RELEASES.md")

        self.repo.write("RELEASES.md", self.LOG + "- Also.\n")
        self.assertTrue(self.summary().endswith(self.QUIET))

    def test_a_mark_written_before_a_file_was_append_only_expires_on_an_append(self) -> None:
        self.mark_release_claim("`RELEASES.md`", log="RELEASES.md")
        self.repo.write("claims.toml", CONFIG + '\n[subjects]\nappend_only = "RELEASES.md"\n')
        self.assertTrue(self.summary().endswith(self.QUIET))

        self.repo.write("RELEASES.md", self.LOG + "- Also.\n")
        self.assertEqual(self.summary(), self.SHOWN)

    def test_an_anchored_changelog_subject_reads_only_its_section(self) -> None:
        self.mark_release_claim("[the log](../CHANGELOG.md#unreleased)")
        self.assertIn('"CHANGELOG.md#unreleased"', (self.repo.root / "claims.checked.toml").read_text())

        self.repo.write("CHANGELOG.md", self.LOG.replace("- Next.", "- Newer.\n- Next."))
        self.assertTrue(self.summary().endswith(self.QUIET))
        self.repo.write("CHANGELOG.md", self.LOG.replace("- First.", "- Second."))
        self.assertTrue(self.summary().endswith(self.QUIET))
        self.repo.write("CHANGELOG.md", self.LOG.replace("- Next.", "- Later."))
        self.assertEqual(self.summary(), self.SHOWN)

    HUB = "# Hub\n\n## Intro\n\nIntro v0.\n\n## Exit codes\n\nCode v0.\n"
    NAVIGATION = CONFIG + '\n[subjects]\nnavigation = "docs/hub.md"\n'

    def mark_hub_claim(self, link: str, listed: bool = True) -> None:
        """A marked sentence in `docs/a.md` linking `link`, a repo-relative
        path, with `docs/hub.md` committed holding `HUB` and listed in
        `navigation` when `listed`."""

        if listed:
            self.repo.write("claims.toml", self.NAVIGATION)
        self.repo.write("docs/hub.md", self.HUB)
        self.repo.commit()
        self.repo.write("docs/a.md", f"Every exit is in [the hub](../{link}).\n")
        self.assertEqual(self.mark("docs/a.md:1 claim-words-totalising read the hub")[0], 0)

    def test_a_listed_navigation_page_named_whole_is_no_subject(self) -> None:
        self.mark_hub_claim("docs/hub.md")
        self.assertNotIn("docs/hub.md", (self.repo.root / "claims.checked.toml").read_text())

        self.repo.write("docs/hub.md", self.HUB.replace("Code v0.", "Code v1."))
        self.assertTrue(self.summary().endswith(self.QUIET))
        self.repo.write("docs/a.md", "Every exit is listed in [the hub](../docs/hub.md).\n")
        out = self.run_cli()[1]
        self.assertIn("[advisory] docs/a.md:1 (claim-words-totalising)", out)
        self.assertNotIn("quiet", out)

    def test_an_anchored_link_into_a_navigation_page_reads_its_section(self) -> None:
        self.mark_hub_claim("docs/hub.md#exit-codes")
        self.assertIn('"docs/hub.md#exit-codes"', (self.repo.root / "claims.checked.toml").read_text())

        self.repo.write("docs/hub.md", self.HUB.replace("Intro v0.", "Intro v1."))
        self.assertTrue(self.summary().endswith(self.QUIET))
        self.repo.write("docs/hub.md", self.HUB.replace("Code v0.", "Code v1."))
        self.assertEqual(self.summary(), self.SHOWN)

    def test_an_unlisted_page_named_whole_is_still_a_subject(self) -> None:
        self.mark_hub_claim("docs/hub.md", listed=False)

        self.repo.write("docs/hub.md", self.HUB.replace("Intro v0.", "Intro v1."))
        self.assertEqual(self.summary(), self.SHOWN)

    def test_a_mark_recording_a_page_before_it_was_listed_ignores_it(self) -> None:
        self.mark_hub_claim("docs/hub.md", listed=False)
        self.assertIn('"docs/hub.md"', (self.repo.root / "claims.checked.toml").read_text())
        self.repo.write("claims.toml", self.NAVIGATION)

        self.repo.write("docs/hub.md", self.HUB.replace("Code v0.", "Code v1."))
        self.assertTrue(self.summary().endswith(self.QUIET))

    # Pending marks (#245, ADR 0014).

    def test_a_review_other_than_pending_makes_the_sidecar_invalid(self) -> None:
        entry = (
            '[[mark]]\nfile = "docs/a.md"\nmode = "claim-words-totalising"\nunit = "x"\n'
            'copies = 1\nnote = "n"\nreview = {review}\nsubjects = {{}}\n'
        )
        for review, valid in (('"pending"', True), ('"approved"', False), ("true", False)):
            with self.subTest(review=review):
                (self.repo.root / "claims.checked.toml").write_text(entry.format(review=review))
                out = self.run_cli()[1]
                self.assertEqual(
                    "[GATE] claims.checked.toml:0 (config) is invalid:" in out, not valid, out
                )
                if not valid:
                    self.assertIn("has a 'review' that is not \"pending\"", out)

    def test_an_approved_by_that_is_not_a_string_makes_the_sidecar_invalid(self) -> None:
        entry = (
            '[[mark]]\nfile = "docs/a.md"\nmode = "claim-words-totalising"\nunit = "x"\n'
            'copies = 1\nnote = "n"\n{approved_by}subjects = {{}}\n'
        )
        for approved_by, valid in (("", True), ('approved_by = "Kevin"\n', True), ("approved_by = 1\n", False)):
            with self.subTest(approved_by=approved_by):
                (self.repo.root / "claims.checked.toml").write_text(entry.format(approved_by=approved_by))
                out = self.run_cli()[1]
                self.assertEqual(
                    "[GATE] claims.checked.toml:0 (config) is invalid:" in out, not valid, out
                )
                if not valid:
                    self.assertIn("has an 'approved_by' that is not a string", out)
                else:
                    self.assertEqual(
                        [m.approved_by for m in load_marks(self.repo.root)],
                        ["Kevin" if approved_by else None],
                    )

    def test_a_pending_mark_is_written_with_its_review_and_quiets_its_finding(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n\nEvery rule holds.\n")
        self.mark("docs/a.md:1 claim-words-totalising read the runner")

        code, out, err = self.mark("docs/a.md:3 claim-words-totalising read the rules", pending=True)

        self.assertEqual((code, err), (0, ""))
        marks = load_marks(self.repo.root)
        self.assertEqual(
            {m.note: m.pending for m in marks}, {"read the runner": False, "read the rules": True}
        )
        sidecar = (self.repo.root / "claims.checked.toml").read_text()
        self.assertEqual(sidecar.count('review = "pending"'), 1)
        self.assertEqual(
            self.summary(),
            "1 checked, 0 finding(s), 0 gate failure(s), 2 quiet while checked, 1 of them pending",
        )

    def test_a_pending_partial_mark_records_both_and_is_counted_both_ways(self) -> None:
        self.stale_section()

        code, _, err = self.mark(
            "notes/s.md:1 stale-claims spot-checked", diff_range="HEAD~1", partial=True, pending=True
        )

        self.assertEqual((code, err), (0, ""))
        sidecar = (self.repo.root / "claims.checked.toml").read_text()
        self.assertIn('extent = "partial"', sidecar)
        self.assertIn('review = "pending"', sidecar)
        self.assertTrue(
            self.run_cli("--diff-range", "HEAD~1")[1].endswith(
                ", 1 quiet while checked, 1 of them partly, 1 of them pending\n"
            )
        )

    def test_a_plain_mark_replaces_a_pending_one_as_reviewed(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it", pending=True)

        self.mark("docs/a.md:1 claim-words-totalising read it myself")

        self.assertEqual([m.pending for m in load_marks(self.repo.root)], [False])

    def test_a_pending_mark_never_blocks_the_hook_and_is_counted(self) -> None:
        self.hook_lists('["claim-words"]')
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it", pending=True)

        decision = decide_repo(self.repo.root)

        assert decision is not None
        self.assertFalse(decision.block)
        self.assertTrue(decision.message.endswith("1 quiet while checked, 1 of them pending"))

    def test_a_pending_mark_counts_as_marked_under_the_flag(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it", pending=True)

        code, out, _ = self.run_cli("--fail-on-unmarked")

        self.assertEqual(code, 0)
        self.assertTrue(out.endswith(", 1 quiet while checked, 1 of them pending, 0 unmarked\n"))

    def test_the_marks_added_count_says_how_many_are_pending(self) -> None:
        base = self.repo.short_head()
        self.repo.write("docs/a.md", "Every check runs.\n\nEvery rule holds.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it")
        self.mark("docs/a.md:3 claim-words-totalising read it", pending=True)
        self.repo.commit()

        self.assertEqual(
            self.run_cli("--diff-range", base)[1].splitlines()[-1],
            "1 checked, 0 finding(s), 0 gate failure(s), 2 quiet while checked, "
            "1 of them pending, 2 mark(s) added in range, 1 of them pending",
        )

    def two_marks_one_pending(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n\nEvery rule holds.\n")
        self.mark("docs/a.md:1 claim-words-totalising read the runner")
        self.mark("docs/a.md:3 claim-words-totalising read the rules", pending=True)

    def test_pending_marks_lists_each_pending_mark_and_fails(self) -> None:
        self.two_marks_one_pending()

        code, out, err = self.run_cli("pending-marks")

        self.assertEqual((code, err), (1, ""))
        self.assertEqual(
            out, "docs/a.md:3 claim-words-totalising read the rules [current]\n1 pending mark(s)\n"
        )

    def test_pending_marks_names_each_marks_reader(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n\nEvery rule holds.\n")
        self.mark("docs/a.md:1 claim-words-totalising read the runner", pending=True)
        self.mark(
            "docs/a.md:3 claim-words-totalising read the rules",
            by="claims:reading-agent (sonnet)",
            pending=True,
        )

        code, out, err = self.run_cli("pending-marks")

        self.assertEqual((code, err), (1, ""))
        self.assertEqual(
            sorted(out.splitlines()),
            [
                "2 pending mark(s)",
                "docs/a.md:1 claim-words-totalising read the runner [current]",
                "docs/a.md:3 claim-words-totalising read the rules (by claims:reading-agent (sonnet)) [current]",
            ],
        )

    def test_pending_marks_passes_with_none_pending(self) -> None:
        self.assertEqual(self.run_cli("pending-marks"), (0, "0 pending mark(s)\n", ""))
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it")
        self.assertEqual(self.run_cli("pending-marks"), (0, "0 pending mark(s)\n", ""))

    def test_pending_marks_lists_an_orphaned_pending_mark_at_line_0(self) -> None:
        self.two_marks_one_pending()
        self.repo.write("docs/a.md", "Every check runs.\n")

        code, out, _ = self.run_cli("pending-marks")

        self.assertEqual(code, 1)
        self.assertIn("docs/a.md:0 claim-words-totalising read the rules [current]\n", out)

    def test_pending_marks_at_a_commit_reads_that_commits_file(self) -> None:
        base = self.repo.short_head()
        self.two_marks_one_pending()
        self.repo.commit()
        # Moved down a line and approved since, in the working tree only.
        self.repo.write("docs/a.md", "Intro.\n\nEvery check runs.\n\nEvery rule holds.\n")
        self.assertEqual(
            self.mark("docs/a.md:5 claim-words-totalising read the rules myself", diff_range=base)[0], 0
        )

        self.assertEqual(self.run_cli("pending-marks")[0], 0)
        code, out, _ = self.run_cli("pending-marks", "--at", "HEAD")
        self.assertEqual(code, 1)
        self.assertIn("docs/a.md:3 claim-words-totalising read the rules [current]\n", out)
        self.assertEqual(self.run_cli("pending-marks", "--at", base), (0, "0 pending mark(s)\n", ""))

    def test_pending_marks_with_a_bad_commit_or_an_invalid_file_exits_2(self) -> None:
        code, _, err = self.run_cli("pending-marks", "--at", "no-such-rev")
        self.assertEqual(code, 2)
        self.assertIn("no-such-rev", err)

        (self.repo.root / "claims.checked.toml").write_text("[[mark]\n")
        code, _, err = self.run_cli("pending-marks")
        self.assertEqual(code, 2)
        self.assertIn("claims.checked.toml is invalid", err)

    def test_approve_marks_approves_only_marks_unchanged_and_pending_since_the_commit(self) -> None:
        base = self.repo.short_head()
        self.repo.write(
            "docs/a.md", "Every check runs.\n\nEvery rule holds.\n\nEvery test passes.\n"
        )
        self.mark("docs/a.md:1 claim-words-totalising read the runner", pending=True)
        self.mark("docs/a.md:3 claim-words-totalising read the rules", pending=True)
        self.mark("docs/a.md:5 claim-words-totalising read the tests")
        self.repo.commit()
        reviewed = self.repo.short_head()
        # Since the review: one re-marked, one added, one reviewed then made pending.
        for entry in (
            "docs/a.md:3 claim-words-totalising read the rules again",
            "docs/a.md:5 claim-words-totalising read the tests again",
        ):
            self.assertEqual(self.mark(entry, diff_range=base, pending=True)[0], 0)
        self.repo.write(
            "docs/a.md",
            "Every check runs.\n\nEvery rule holds.\n\nEvery test passes.\n\nEvery doc builds.\n",
        )
        self.assertEqual(
            self.mark("docs/a.md:7 claim-words-totalising read the build", pending=True)[0], 0
        )
        sidecar = self.repo.root / "claims.checked.toml"
        sidecar.write_text("# reviewed in batches\n" + sidecar.read_text())
        before = sidecar.read_text()

        code, out, err = self.run_cli("approve-marks", reviewed)

        self.assertEqual((code, err), (0, ""))
        self.assertEqual(
            sorted(out.splitlines()),
            sorted(
                [
                    "approved docs/a.md:1 claim-words-totalising read the runner [current]",
                    f"left pending docs/a.md:3 claim-words-totalising read the rules again [current]: changed since {reviewed}",
                    f"left pending docs/a.md:5 claim-words-totalising read the tests again [current]: changed since {reviewed}",
                    f"left pending docs/a.md:7 claim-words-totalising read the build [current]: not in {reviewed}",
                    "approved 1 mark(s), left 3 pending",
                ]
            ),
        )
        self.assertEqual(
            {m.note: m.pending for m in load_marks(self.repo.root)},
            {
                "read the runner": False,
                "read the rules again": True,
                "read the tests again": True,
                "read the build": True,
            },
        )
        # Only the approved entry's `review` line is gone; every other
        # line, the comment heading the file included, is as it was.
        after = sidecar.read_text()
        self.assertEqual(after.count('review = "pending"'), 3)
        self.assertEqual(
            [line for line in before.splitlines() if line != 'review = "pending"'],
            [line for line in after.splitlines() if line != 'review = "pending"'],
        )

    def test_approve_marks_by_names_the_approver_on_each_approved_entry_only_and_keeps_its_reader(self) -> None:
        base = self.repo.short_head()
        self.repo.write(
            "docs/a.md", "Every check runs.\n\nEvery rule holds.\n\nEvery test passes.\n"
        )
        self.mark("docs/a.md:1 claim-words-totalising read the runner", by="agent", pending=True)
        self.mark("docs/a.md:3 claim-words-totalising read the rules", pending=True)
        self.mark("docs/a.md:5 claim-words-totalising read the tests", by="agent", pending=True)
        self.repo.commit()
        reviewed = self.repo.short_head()
        # Since the review: one entry's `by` alone changed, and one added.
        self.assertEqual(
            self.mark(
                "docs/a.md:5 claim-words-totalising read the tests",
                by="another agent",
                diff_range=base,
                pending=True,
            )[0],
            0,
        )
        self.repo.write(
            "docs/a.md",
            "Every check runs.\n\nEvery rule holds.\n\nEvery test passes.\n\nEvery doc builds.\n",
        )
        self.assertEqual(
            self.mark("docs/a.md:7 claim-words-totalising read the build", by="agent", pending=True)[0],
            0,
        )

        code, out, err = self.run_cli("approve-marks", reviewed, "--by", "Kevin")

        self.assertEqual((code, err), (0, ""))
        self.assertEqual(
            sorted(out.splitlines()),
            sorted(
                [
                    "approved docs/a.md:1 claim-words-totalising read the runner (by agent) [current]",
                    "approved docs/a.md:3 claim-words-totalising read the rules [current]",
                    f"left pending docs/a.md:5 claim-words-totalising read the tests (by another agent) [current]: changed since {reviewed}",
                    f"left pending docs/a.md:7 claim-words-totalising read the build (by agent) [current]: not in {reviewed}",
                    "approved 2 mark(s), left 2 pending",
                ]
            ),
        )
        # The reader stays in `by`; the approver goes in `approved_by`.
        self.assertEqual(
            {m.note: (m.by, m.approved_by, m.pending) for m in load_marks(self.repo.root)},
            {
                "read the runner": ("agent", "Kevin", False),
                "read the rules": (None, "Kevin", False),
                "read the tests": ("another agent", None, True),
                "read the build": ("agent", None, True),
            },
        )

    def test_approve_marks_with_nothing_to_approve_exits_0(self) -> None:
        base = self.repo.short_head()
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it", pending=True)

        code, out, _ = self.run_cli("approve-marks", base)

        self.assertEqual(code, 0)
        self.assertTrue(out.endswith("approved 0 mark(s), left 1 pending\n"))
        self.assertEqual([m.pending for m in load_marks(self.repo.root)], [True])

    def test_approve_marks_with_a_bad_commit_or_an_invalid_file_exits_2(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it", pending=True)
        self.repo.commit()
        sidecar = self.repo.root / "claims.checked.toml"
        good = sidecar.read_text()

        code, _, err = self.run_cli("approve-marks", "no-such-rev")
        self.assertEqual(code, 2)
        self.assertIn("no-such-rev", err)

        sidecar.write_text("[[mark]\n")
        code, _, err = self.run_cli("approve-marks", "HEAD")
        self.assertEqual(code, 2)
        self.assertIn("claims.checked.toml is invalid", err)

        self.repo.commit()
        sidecar.write_text(good)
        self.repo.commit()
        code, _, err = self.run_cli("approve-marks", "HEAD~1")
        self.assertEqual(code, 2)
        self.assertIn("claims.checked.toml is invalid at HEAD~1", err)
        self.assertEqual(sidecar.read_text(), good)

    def test_approve_marks_against_a_duplicated_entry_exits_2_and_writes_nothing(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read it", pending=True)
        sidecar = self.repo.root / "claims.checked.toml"
        # What a conflict resolution keeping both sides leaves.
        sidecar.write_text(sidecar.read_text() + "\n" + sidecar.read_text())
        self.repo.commit()
        before = sidecar.read_bytes()

        code, out, err = self.run_cli("approve-marks", "HEAD", "--by", "Kevin")

        self.assertEqual((code, out), (2, ""))
        self.assertIn("claims.checked.toml is invalid", err)
        self.assertIn("has the file, mode and unit of the one at line 1", err)
        self.assertEqual(sidecar.read_bytes(), before)


    # Kinds (ADR 0019): a mark records its claim's kind, and a past or
    # superseded mark expires on its unit's text and its evidence.

    def sidecar(self) -> Path:
        return self.repo.root / "claims.checked.toml"

    def test_a_mark_with_no_kind_loads_as_current(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")
        self.mark("docs/a.md:1 claim-words-totalising read the runner")

        text = self.sidecar().read_text()
        self.assertNotIn("kind", text)
        self.assertNotIn("text =", text)
        self.assertNotIn("evidence", text)
        [mark] = load_marks(self.repo.root)
        self.assertEqual((mark.kind, mark.text, dict(mark.evidence)), (None, None, {}))

    def test_a_past_mark_records_its_kind_and_text(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n")

        code, _, err = self.mark("docs/a.md:1 claim-words-totalising held at its writing", kind="past")

        self.assertEqual((code, err), (0, ""))
        self.assertIn('kind = "past"', self.sidecar().read_text())
        [mark] = load_marks(self.repo.root)
        self.assertEqual(mark.kind, "past")
        self.assertIsNotNone(mark.text)
        self.assertEqual(load_marks(self.repo.root), [mark])
        self.assertEqual(_render(mark).count("text ="), 1)

    def test_a_past_mark_holds_when_a_subject_changes(self) -> None:
        self.repo.write("src/cache.py", "CACHE = 1\n")
        self.repo.commit()
        self.repo.write("docs/a.md", "Every read went through src/cache.py first.\n")
        self.mark("docs/a.md:1 claim-words-totalising read at its writing", kind="past")

        self.repo.write("src/cache.py", "CACHE = 2\n")
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))
        self.repo.write("src/cache.py", "")
        (self.repo.root / "src/cache.py").unlink()
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

    def test_a_past_mark_holds_when_its_unit_names_a_new_subject(self) -> None:
        self.repo.write("docs/a.md", "Every read went through `store`.\n")
        self.mark("docs/a.md:1 claim-words-totalising read at its writing", kind="past")

        self.repo.write("src/store.py", "STORE = 1\n")
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

    def test_an_intended_mark_records_its_kind_and_expires_as_a_current_one(self) -> None:
        self.repo.write("src/cache.py", "CACHE = 1\n")
        self.repo.commit()
        self.repo.write("docs/a.md", "Every read will go through src/cache.py first.\n")
        self.mark("docs/a.md:1 claim-words-totalising delivered", kind="intended")

        self.assertIn('kind = "intended"', self.sidecar().read_text())
        self.assertNotIn("text =", self.sidecar().read_text())
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))
        self.repo.write("src/cache.py", "CACHE = 2\n")
        self.assertEqual(self.summary(), "1 checked, 1 finding(s), 0 gate failure(s)")

    def section_always_reported(self) -> None:
        """notes/s.md, one section naming src/cache.py, which a stand-in
        for `stale-claims` reports on every run, whatever its staleness:
        these tests are about the mark, not the ranking."""

        register_check(
            stale_claims.NAME,
            lambda root, diff_range, config: [
                Finding(file="notes/s.md", line=1, message="stale", mode=stale_claims.NAME, gate=False)
            ],
        )
        self.repo.write("src/cache.py", "CACHE = 1\n")
        self.repo.write("notes/s.md", "## Caching\n\nReads go through src/cache.py.\n")
        self.assertEqual(self.mark("notes/s.md:1 stale-claims read at its writing", kind="past")[0], 0)

    def test_a_past_section_mark_expires_on_a_word_of_its_body_and_not_on_a_subject(self) -> None:
        self.section_always_reported()

        self.repo.write("src/cache.py", "CACHE = 3\n")
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

        # The heading, the unit's hash, is unchanged; a word under it isn't.
        self.repo.write("notes/s.md", "## Caching\n\nReads went through src/cache.py.\n")
        self.assertIn("[advisory] notes/s.md:1 (stale-claims)", self.run_cli()[1])
        self.assertNotIn("quiet", self.summary())

    def test_a_reflow_keeps_a_past_mark(self) -> None:
        self.section_always_reported()

        self.repo.write("notes/s.md", "## Caching\n\nReads go\nthrough *src/cache.py*.\n")

        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

    def test_a_partial_past_mark_can_be_written_for_a_section_only(self) -> None:
        self.stale_section()
        code, _, err = self.mark(
            "notes/s.md:1 stale-claims read part at its writing",
            diff_range="HEAD~1",
            partial=True,
            kind="past",
        )
        self.assertEqual((code, err), (0, ""))
        self.assertEqual([(m.kind, m.partial) for m in load_marks(self.repo.root)], [("past", True)])

        self.repo.write("docs/a.md", "Every check ran.\n")
        code, _, err = self.mark("docs/a.md:1 claim-words-totalising read", partial=True, kind="past")
        self.assertEqual(code, 1)
        self.assertIn("can't be marked partial", err)

    def adr(self, status: str = "Superseded by ADR 2.") -> None:
        self.repo.write("decisions/1.md", f"# 1\n\n## Status\n\n{status}\n\n## Decision\n\nEvery check runs.\n")

    def superseded(self) -> None:
        self.adr()
        self.repo.commit()
        self.repo.write("docs/a.md", "Every read goes through src/cache.py first.\n")
        code, _, err = self.mark(
            "docs/a.md:1 claim-words-totalising held before ADR 2",
            kind="superseded",
            evidence=("decisions/1.md#status",),
        )
        self.assertEqual((code, err), (0, ""))

    def test_a_superseded_mark_records_its_evidence_and_holds_while_it_does(self) -> None:
        self.superseded()

        [mark] = load_marks(self.repo.root)
        self.assertEqual((mark.kind, list(mark.evidence)), ("superseded", ["decisions/1.md#status"]))
        self.repo.write("src/cache.py", "CACHE = 1\n")
        self.repo.write("decisions/1.md", (self.repo.root / "decisions/1.md").read_text() + "More.\n")
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

    def test_a_superseded_mark_expires_when_its_evidence_changes_and_not_on_a_reflow(self) -> None:
        self.superseded()

        self.adr("Superseded\nby *ADR 2*.")
        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

        self.adr("Accepted.")
        self.assertEqual(self.summary(), "1 checked, 1 finding(s), 0 gate failure(s)")

        self.adr()
        self.repo.write("decisions/1.md", "# 1\n\nNo status any more.\n")
        self.assertEqual(self.summary(), "1 checked, 1 finding(s), 0 gate failure(s)")

    def test_a_superseded_mark_needs_evidence_and_only_past_or_superseded_take_any(self) -> None:
        self.adr()
        self.repo.write("docs/a.md", "Every check runs.\n")
        entry = "docs/a.md:1 claim-words-totalising read"

        for kwargs in (
            {"kind": "superseded"},
            {"evidence": ("decisions/1.md#status",)},
            {"kind": "intended", "evidence": ("decisions/1.md#status",)},
            {"kind": "bogus"},
        ):
            with self.subTest(**kwargs), self.assertRaises(SystemExit) as raised:
                self.mark(entry, **kwargs)  # type: ignore[arg-type]
            self.assertEqual(raised.exception.code, 2)
            self.assertFalse(self.sidecar().exists())

        code, _, err = self.mark(entry, kind="past", evidence=("decisions/1.md#no-such",))
        self.assertEqual(code, 1)
        self.assertIn("decisions/1.md#no-such", err)
        self.assertFalse(self.sidecar().exists())

        code, _, err = self.mark(entry, kind="past", evidence=("decisions/1.md#status",))
        self.assertEqual((code, err), (0, ""))

    def test_a_bad_kind_or_its_keys_make_the_sidecar_invalid_and_nothing_is_written(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n\nEvery rule holds.\n")
        self.mark("docs/a.md:1 claim-words-totalising read the runner", kind="past")
        good = self.sidecar().read_text()

        for bad, problem in (
            (good.replace('kind = "past"', 'kind = "bogus"'), "'kind'"),
            (good.replace('kind = "past"', 'kind = "current"'), "'kind'"),
            ("\n".join(l for l in good.splitlines() if not l.startswith("text =")), "'text'"),
            (good.replace('kind = "past"', 'kind = "intended"'), "'text'"),
            (good.replace('kind = "past"', 'kind = "superseded"'), "'evidence'"),
            (good.replace("subjects =", 'evidence = { "../x.md" = "h" }\nsubjects ='), "outside"),
            (good.replace("subjects =", 'evidence = { "x.md" = 1 }\nsubjects ='), "'evidence'"),
        ):
            with self.subTest(problem=problem, bad=bad):
                self.sidecar().write_text(bad)
                code, _, err = self.mark("docs/a.md:3 claim-words-totalising read the rules")
                self.assertEqual(code, 2)
                self.assertIn(problem, err)
                self.assertEqual(self.sidecar().read_text(), bad)

    def test_the_listing_shows_each_marks_kind(self) -> None:
        self.repo.write("docs/a.md", "Every check runs.\n\nEvery rule held.\n")
        self.mark("docs/a.md:1 claim-words-totalising read the runner", pending=True)
        self.mark("docs/a.md:3 claim-words-totalising read the rules", pending=True, kind="past")

        code, out, err = self.run_cli("pending-marks")

        self.assertEqual((code, err), (1, ""))
        self.assertEqual(
            out,
            "docs/a.md:1 claim-words-totalising read the runner [current]\n"
            "docs/a.md:3 claim-words-totalising read the rules [past]\n"
            "2 pending mark(s)\n",
        )

    def test_the_listing_flags_a_superseded_mark_whose_evidence_changed_with_it(self) -> None:
        start = self.repo.short_head()
        self.repo.write("docs/a.md", "Every read goes through src/cache.py first.\n\nEvery rule holds.\n")
        self.adr("Accepted.")
        self.repo.commit()
        # One commit both supersedes the claim and marks it so.
        self.adr()
        self.mark(
            "docs/a.md:1 claim-words-totalising held before ADR 2",
            pending=True,
            kind="superseded",
            evidence=("decisions/1.md#status",),
            diff_range=start,
        )
        self.mark(
            "docs/a.md:3 claim-words-totalising read the rules",
            pending=True,
            kind="past",
            evidence=("README.md",),
            diff_range=start,
        )
        flagged = (
            "docs/a.md:1 claim-words-totalising held before ADR 2 "
            "[superseded; evidence decisions/1.md#status added or changed in range]"
        )
        held = "docs/a.md:3 claim-words-totalising read the rules [past]"

        self.assertEqual(sorted(self.run_cli("pending-marks")[1].splitlines()[:2]), [flagged, held])
        self.repo.commit()
        self.assertEqual(
            sorted(self.run_cli("pending-marks", "--at", "HEAD")[1].splitlines()[:2]), [flagged, held]
        )
        code, out, _ = self.run_cli("approve-marks", "HEAD")
        self.assertEqual(code, 0)
        self.assertIn(f"approved {flagged}", out.splitlines())

        # Evidence that was already there when the mark was written isn't flagged.
        self.repo.write("docs/a.md", "Every read goes through src/cache.py first.\n\nEvery rule holds.\n\nEvery test passes.\n")
        self.mark(
            "docs/a.md:5 claim-words-totalising read the tests",
            pending=True,
            kind="superseded",
            evidence=("decisions/1.md#status",),
            diff_range=start,
        )
        self.assertIn(
            "docs/a.md:5 claim-words-totalising read the tests [superseded]",
            self.run_cli("pending-marks")[1].splitlines(),
        )


def a_mark(file: str, note: str = "n", unit: str = "u") -> Mark:
    return Mark(file=file, mode="claim-words-totalising", unit=unit, copies=1, subjects={}, note=note)


class SortedSidecarTests(unittest.TestCase):
    """`write_marks` keeps `claims.checked.toml` sorted by key, so two
    branches marking findings in different files merge cleanly (#241)."""

    def setUp(self) -> None:
        self.repo = Repo().__enter__()
        self.addCleanup(self.repo.__exit__)
        self.sidecar = self.repo.root / "claims.checked.toml"

    def files(self) -> list[str]:
        return [m.file for m in load_marks(self.repo.root)]

    def test_entries_are_written_in_key_order(self) -> None:
        write_marks(self.repo.root, [a_mark("docs/c.md"), a_mark("docs/a.md")])
        write_marks(self.repo.root, [a_mark("docs/b.md")])

        self.assertEqual(self.files(), ["docs/a.md", "docs/b.md", "docs/c.md"])

    def test_a_replacement_takes_its_sorted_slot_with_the_comment_above_it(self) -> None:
        # Hand-edited out of order; reading doesn't care.
        self.sidecar.write_text(
            "# about c\n" + _render(a_mark("docs/c.md", "old")) + "\n" + _render(a_mark("docs/a.md"))
        )
        self.assertEqual(self.files(), ["docs/c.md", "docs/a.md"])

        write_marks(self.repo.root, [a_mark("docs/c.md", "new")])

        self.assertEqual(
            self.sidecar.read_text(),
            _render(a_mark("docs/a.md")) + "\n# about c\n" + _render(a_mark("docs/c.md", "new")),
        )

    def test_writing_a_sorted_file_with_nothing_new_changes_no_byte(self) -> None:
        text = (
            "# audit\n\n"
            + _render(a_mark("docs/a.md"))
            + "\n\n# about b\n"
            + _render(a_mark("docs/b.md"))
            + _render(a_mark("docs/c.md"))
            + "\n# trailing\n"
        )
        self.sidecar.write_text(text)

        write_marks(self.repo.root, [])

        self.assertEqual(self.sidecar.read_text(), text)

    def test_a_file_of_only_comments_keeps_them_above_its_first_entry(self) -> None:
        self.sidecar.write_text("# audit\n")

        write_marks(self.repo.root, [a_mark("docs/a.md")])

        self.assertEqual(self.sidecar.read_text(), "# audit\n\n" + _render(a_mark("docs/a.md")))

    def test_a_pruned_entry_leaves_a_comment_not_directly_above_it(self) -> None:
        self.sidecar.write_text(
            _render(a_mark("docs/a.md"))
            + "\n# note\n\n# about b\n"
            + _render(a_mark("docs/b.md"))
            + "\n"
            + _render(a_mark("docs/c.md"))
        )

        write_marks(self.repo.root, [], pruned=[a_mark("docs/b.md")])

        self.assertEqual(
            self.sidecar.read_text(),
            _render(a_mark("docs/a.md")) + "\n# note\n\n" + _render(a_mark("docs/c.md")),
        )

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.repo.root), *args],
            capture_output=True,
            text=True,
            check=args[0] != "merge",
        )

    def test_two_branches_marking_different_files_merge_without_conflict(self) -> None:
        # Enough entries between the two new ones that git sees their
        # insertions as separate hunks; keys that sort next to each other
        # can still conflict.
        write_marks(self.repo.root, [a_mark(f"docs/{n}.md") for n in "bcdefghijklmnop"])
        self.repo.commit()
        base = self.git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        self.git("checkout", "-q", "-b", "other")
        write_marks(self.repo.root, [a_mark("docs/z.md")])
        self.repo.commit()
        self.git("checkout", "-q", base)
        write_marks(self.repo.root, [a_mark("docs/a.md")])
        self.repo.commit()

        merge = self.git("merge", "-q", "--no-edit", "other")

        self.assertEqual(merge.returncode, 0, merge.stdout + merge.stderr)
        self.assertEqual(
            self.files(), ["docs/a.md", *(f"docs/{n}.md" for n in "bcdefghijklmnop"), "docs/z.md"]
        )


class DemotedHistoricalMarkTests(RegistryClearingTestCase):
    """ADR 0020: a reference in a `historical` file that held at its
    writing is a `<check>-historical` advisory finding, which a checked
    mark keeps quiet and `--fail-on-unmarked` covers."""

    TOML = (
        '[check-file-refs]\nhistorical = ["CHANGELOG.md"]\n'
        '[check-links]\nhistorical = ["CHANGELOG.md"]\n'
    )

    def setUp(self) -> None:
        super().setUp()
        register_check(check_file_refs.NAME, check_file_refs.check)
        register_check(check_links.NAME, check_links.check)
        self.repo = Repo().__enter__()
        self.addCleanup(self.repo.__exit__)
        self.repo.write("claims.toml", self.TOML)
        self.repo.write("docs/old.md", "# Old\n")
        self.repo.write("CHANGELOG.md", "- Added `docs/old.md` and [a link](docs/old.md).\n")
        self.repo.commit()
        self.repo.rm("docs/old.md")
        self.repo.commit()

    run_cli = CheckedMarkTests.run_cli
    mark = CheckedMarkTests.mark

    def test_an_unmarked_demoted_finding_fails_under_the_flag_until_it_is_marked(self) -> None:
        code, out, _ = self.run_cli("--fail-on-unmarked")
        self.assertEqual(code, 3, out)
        self.assertIn("CHANGELOG.md:1 (check-file-refs-historical)", out)
        self.assertIn("CHANGELOG.md:1 (check-links-historical)", out)

        code, out, err = self.mark(
            "CHANGELOG.md:1 check-file-refs-historical past: docs/old.md was added there",
            "CHANGELOG.md:1 check-links-historical past: docs/old.md was added there",
            kind="past",
        )
        self.assertEqual(code, 0, out + err)

        code, out, _ = self.run_cli("--fail-on-unmarked")
        self.assertEqual(code, 0, out)
        self.assertTrue(out.endswith(", 2 quiet while checked, 0 unmarked\n"), out)

    def test_the_flag_names_a_demoted_mode_by_its_check(self) -> None:
        self.assertEqual(self.run_cli("--fail-on-unmarked=check-links")[0], 3)
        self.assertEqual(self.run_cli("--fail-on-unmarked=claim-words")[0], 0)

    def test_rewording_the_line_orphans_the_mark_and_gates_the_reference(self) -> None:
        # Reworded, the line is the working tree's, where the path is gone
        # and was gone at `HEAD` too (ADR 0002): no reading settles that.
        self.mark(
            "CHANGELOG.md:1 check-file-refs-historical past: docs/old.md was added there",
            kind="past",
        )
        self.repo.write("CHANGELOG.md", "- Added `docs/old.md` and [a link](docs/old.md) too.\n")

        code, out, _ = self.run_cli("--fail-on-unmarked=check-file-refs")

        self.assertEqual(code, 1, out)
        self.assertIn("[GATE] CHANGELOG.md:1 (check-file-refs) ", out)
        self.assertIn("(checked-mark)", out)

    def test_a_gate_finding_of_the_same_check_still_cant_be_marked(self) -> None:
        self.repo.write("README.md", "See `docs/nope.md`.\n")

        code, _, err = self.mark("README.md:1 check-file-refs read it")

        self.assertEqual(code, 1)
        self.assertIn("a gate finding can't be marked", err)

    def test_the_checks_other_advisory_finding_cant_be_marked(self) -> None:
        # A dangling example marker is `check-file-refs`' own advisory
        # finding, settled by deleting the marker; only the demoted mode
        # takes a mark.
        self.repo.write("README.md", "No path here <!-- example -->.\n")

        code, out, _ = self.run_cli("--fail-on-unmarked=check-file-refs")
        self.assertIn("README.md:1 (check-file-refs)", out)
        code, _, err = self.mark("README.md:1 check-file-refs read it")

        self.assertEqual(code, 1)
        self.assertIn("check-file-refs findings can't be marked", err)


if __name__ == "__main__":
    unittest.main()
