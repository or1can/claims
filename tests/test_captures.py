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

"""Freshness of the captured check output the documentation site shows.

Every file under `docs/captures/` is the real output of `claims` against
that check's worked example, written by `scripts/capture.py`. This test
calls the same function the script does and asserts the committed text is
what a fresh run produces now — so a hand edit to a capture, or a change to
any check's output, fails here rather than leaving a published page
asserting output the tool no longer produces.
"""

from __future__ import annotations

import unittest

from scripts.capture import CAPTURES_DIR, capture


class CaptureFreshnessTests(unittest.TestCase):
    def test_every_committed_capture_matches_a_fresh_run(self) -> None:
        captures = sorted(CAPTURES_DIR.glob("*.txt"))
        # An empty directory would otherwise pass vacuously.
        self.assertTrue(captures, f"no captures under {CAPTURES_DIR}")
        for path in captures:
            with self.subTest(capture=path.name):
                self.assertEqual(capture(path.stem), path.read_text(encoding="utf-8"))

    def test_an_example_history_is_committed_step_by_step_before_its_own_files(self) -> None:
        # `check-citations` flags a name the repository once declared and no
        # longer has, which no static tree can show: the example's
        # `history/` steps are committed in order first, so the declaring
        # commit is behind the one that removed it by the time the check
        # runs, and the citation of the removed name is a finding.
        self.assertIn("`loadWidget` no longer exists", capture("check-citations"))

    def test_an_example_with_only_history_ranks_by_fixed_commit_timestamps(self) -> None:
        # `stale-claims` scores a section by the commits its subjects saw
        # after the section's own last touch, read from blame and log
        # timestamps, so its example is history alone and the steps are
        # committed an hour apart at a fixed epoch. The capture ranks the
        # section whose subject churned most first, on every machine.
        text = capture("stale-claims")
        self.assertLess(text.index("'Caching'"), text.index("'Storage'"))
        self.assertNotIn("'Logging'", text)

    def test_an_example_own_files_are_staged_as_the_pending_change(self) -> None:
        # A diff-scoped check reads what a commit is about to change: the
        # hook runs it against the working tree before `git commit`
        # completes. The example's own files are written over the
        # committed history and staged, never committed, so `restatement`
        # sees the retracted sentence in its diff and reports the copy
        # that survives.
        text = capture("restatement")
        self.assertIn("docs/setup.md:7 (restatement-whole-line)", text)
        self.assertIn("docs/setup.md:7 (restatement-ngram)", text)
        # The banner all three pages share is duplicated past the
        # threshold and is not reported, in either file that keeps it.
        self.assertNotIn("docs/faq.md", text)

    def test_a_judgment_agent_candidate_names_the_pending_change_as_its_evidence(self) -> None:
        # With the rename staged and uncommitted there is no commit to
        # cite, and the candidate says so rather than naming nothing; that
        # is also what keeps the capture free of a commit hash.
        text = capture("judgment-agent")
        self.assertIn("`fetchRecord`, removed by this diff", text)
        self.assertIn("(uncommitted working-tree change)", text)

    def test_an_example_claims_toml_configures_the_check_it_is_captured_for(self) -> None:
        # `check-config-defaults` sees nothing for a setting with no mapping
        # entry, so its example carries the mapping in a `claims.toml` of
        # its own; the capture reads that file's section for the check the
        # way `runner.run` would, so the page can show the configuration
        # that brings the claim into scope beside the finding it produces.
        self.assertIn("`TIMEOUT` claims default `30`", capture("check-config-defaults"))
        # `claim-words` sweeps nothing until `files` names a file; its
        # example's `claims.toml` designates the record its own step
        # extends, and only the added sentences are read.
        text = capture("claim-words")
        self.assertIn("(claim-words-totalising)", text)
        self.assertNotIn("Every request reads through the same cache", text)
        self.assertNotIn("README.md", text)


if __name__ == "__main__":
    unittest.main()
