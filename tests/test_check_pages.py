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

"""Every registered check is documented, on the site and in the README.

Driven from the check modules themselves (`every_check_name`), not a list
kept here, so a check added to `claims/checks/` without a page, a summary
entry or a README line fails CI rather than shipping undocumented. The
same shape as `tests/test_config_review.py`'s completeness test against
the config-review maps: a hand-maintained per-check surface, held to the
registry.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from support import every_check_name

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"


class CheckPageCoverageTests(unittest.TestCase):
    def test_every_registered_check_has_a_page(self) -> None:
        for name in sorted(every_check_name()):
            with self.subTest(check=name):
                self.assertTrue((DOCS_DIR / "checks" / f"{name}.md").is_file())

    def test_every_registered_check_has_a_summary_entry(self) -> None:
        # A page mdBook's summary does not list is not built or served, so
        # the file existing is not enough.
        summary = (DOCS_DIR / "SUMMARY.md").read_text(encoding="utf-8")
        for name in sorted(every_check_name()):
            with self.subTest(check=name):
                self.assertIn(f"[{name}](checks/{name}.md)", summary)

    def test_every_registered_check_has_a_readme_index_line(self) -> None:
        # The README is an index of the pages, read on GitHub where an
        # in-repo relative link resolves.
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for name in sorted(every_check_name()):
            with self.subTest(check=name):
                self.assertIn(f"[{name}](docs/checks/{name}.md)", readme)


if __name__ == "__main__":
    unittest.main()
