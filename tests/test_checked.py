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
import unittest
from unittest import mock

from claims.checks import claim_words, restatement, spliced_docs, stale_claims
from claims.cli import main
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

    def mark(self, *entries: str, by: str | None = None, diff_range: str | None = None):
        argv = ["mark-checked"]
        if by is not None:
            argv += ["--by", by]
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

        self.assertTrue(self.summary().endswith(", 1 quiet while checked"))

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
        self.assertTrue(text.startswith("# audit of docs/a.md\n"))
        self.assertEqual(text.count("[[mark]]"), 2)
        self.assertNotIn("first", text)
        self.assertIn('note = "second"', text)

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
            self.run_cli("--diff-range", "HEAD~1")[1].endswith(", 1 quiet while checked\n")
        )


if __name__ == "__main__":
    unittest.main()
