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

"""Per-project config loading.

A project's config lives at `<repo_root>/claims.toml`. Each top-level table
is one check's own section, read by name at `run()` time — see
`runner.run`.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

CONFIG_FILENAME = "claims.toml"


class ConfigError(Exception):
    """Raised when `claims.toml` exists but can't be parsed."""


def load_config(repo_root: Path) -> dict[str, dict[str, object]]:
    config_path = repo_root / CONFIG_FILENAME
    if not config_path.is_file():
        return {}
    with config_path.open("rb") as f:
        try:
            return tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ConfigError(f"{config_path}: {e}") from e
