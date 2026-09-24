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


if __name__ == "__main__":
    unittest.main()
