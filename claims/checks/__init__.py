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

"""Registers every built-in check against `claims.runner` on import.

Importing this package is what makes a check visible to `run()` — each
submodule calls `register_check` at import time. Entry points (CLI, hook,
skill) must import this package before calling `run()`.
"""

from __future__ import annotations

from . import check_citations  # noqa: F401
from . import check_links  # noqa: F401
from . import claim_words  # noqa: F401
from . import executable_claims  # noqa: F401
from . import restatement  # noqa: F401
from . import spliced_docs  # noqa: F401
from . import stale_claims  # noqa: F401
