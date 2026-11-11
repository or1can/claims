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

"""The tutorial page, its steps and its captured output agree (#220).

`docs/tutorial.md` shows each step's commands, included by anchor from
`examples/tutorial/steps.sh`, beside that step's output, captured into
`docs/captures/tutorial/<step>.txt` by `scripts/tutorial.py capture`. The
freshness assertion calls the same `capture` function the script writes
with, as `tests/test_captures.py` does for the per-check captures, so a
change to `claims`' output, to the fixture or to a step fails here rather
than leaving the page asserting a transcript nothing produces any more.

The anchors are read here with a pattern of this test's own rather than
through the script, so the correspondence between steps, captures and the
page is not checked by the code that writes them.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STEPS = REPO_ROOT / "examples" / "tutorial" / "steps.sh"
CAPTURES_DIR = REPO_ROOT / "docs" / "captures" / "tutorial"
PAGE = REPO_ROOT / "docs" / "tutorial.md"
SUMMARY = REPO_ROOT / "docs" / "SUMMARY.md"

ANCHOR = re.compile(r"^# ANCHOR: (\S+)$", re.MULTILINE)


def _anchors() -> list[str]:
    return ANCHOR.findall(STEPS.read_text(encoding="utf-8"))


class TutorialTests(unittest.TestCase):
    def test_every_committed_capture_matches_a_fresh_run(self) -> None:
        # Imported here rather than at the top, so the three assertions
        # below still run, and fail for their own reasons, without it.
        from scripts.tutorial import capture

        fresh = capture()
        # No steps at all would otherwise pass vacuously.
        self.assertTrue(fresh, "capture() ran no steps")
        for step, text in fresh.items():
            with self.subTest(step=step):
                path = CAPTURES_DIR / f"{step}.txt"
                self.assertTrue(path.is_file(), f"no committed capture at {path}")
                self.assertEqual(text, path.read_text(encoding="utf-8"))

    def test_steps_and_captures_correspond_one_to_one(self) -> None:
        self.assertTrue(STEPS.is_file(), f"no steps file at {STEPS}")
        anchors = _anchors()
        self.assertEqual(len(anchors), len(set(anchors)), "an anchor is repeated")
        captured = {p.stem for p in CAPTURES_DIR.glob("*.txt")}
        self.assertEqual(set(anchors), captured)

    def test_the_page_exists_and_is_listed_in_the_summary(self) -> None:
        # mdBook neither builds nor serves a page its summary leaves out.
        self.assertTrue(PAGE.is_file(), f"no page at {PAGE}")
        self.assertIn("[Tutorial](tutorial.md)", SUMMARY.read_text(encoding="utf-8"))

    def test_the_page_includes_every_step(self) -> None:
        self.assertTrue(PAGE.is_file(), f"no page at {PAGE}")
        self.assertTrue(STEPS.is_file(), f"no steps file at {STEPS}")
        page = PAGE.read_text(encoding="utf-8")
        for anchor in _anchors():
            with self.subTest(step=anchor):
                self.assertIn(f"{{{{#include ../examples/tutorial/steps.sh:{anchor}}}}}", page)


if __name__ == "__main__":
    unittest.main()
