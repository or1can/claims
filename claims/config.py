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
