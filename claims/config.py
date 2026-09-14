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

import fnmatch
import tomllib
from collections.abc import Mapping, Sequence
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


def string_list_config(config: Mapping[str, object], key: str) -> Sequence[str]:
    """A check's own list-of-strings `key`, from its `config` section —
    shared by every check offering a `key = ["...", ...]` option, so each
    doesn't carry its own copy of the same coercion. Glob-neutral: some
    callers match each entry as an `fnmatch` pattern (`exclude`,
    `stale-claims`'s `module_reference_scope`), others as a literal prefix
    (`executable-claims`'s `permitted_prefixes`) — this only produces the
    list, never assumes how a caller matches against it.
    """

    patterns = config.get(key, [])
    # A project meaning to name one path (`key = "docs/HISTORY.md"`) is a
    # one-character typo away from `["docs/HISTORY.md"]`; treated as a bare
    # list of characters instead, matching against single-char patterns
    # would silently match nothing (or everything) rather than the
    # intended path.
    if isinstance(patterns, str):
        return [patterns]
    return list(patterns)  # type: ignore[arg-type]


def exclude_patterns(config: Mapping[str, object]) -> Sequence[str]:
    """A check's own `exclude` glob list, from its `config` section
    (spec.md's path-exclusion mechanism)."""

    return string_list_config(config, "exclude")


def path_matches(path: str, patterns: Sequence[str]) -> bool:
    """Whether `path` (a repo-relative POSIX path) matches any of `patterns`.

    Named for the match itself, not `exclude`/`scope` — a project's own
    glob list can be either (an `exclude` blocklist, `stale-claims`'s
    `module_reference_scope` allowlist); the caller decides which a match
    means, this only answers "does it match".

    `fnmatchcase`, not `fnmatch` — a git-tracked path is canonically
    case-sensitive, and `fnmatch`'s own case-folding is platform-dependent
    (`os.path.normcase`), which would otherwise make the same `claims.toml`
    match on macOS/Windows and not on Linux.
    """

    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def numeric_config(
    config: Mapping[str, object],
    name: str,
    key: str,
    default: int | float,
    *,
    allow_float: bool,
) -> int | float:
    """A check's own numeric `key` from its `claims.toml` section —
    `default` when unset. Shared by every check offering a typed numeric
    option (a timeout, a threshold), so each doesn't carry its own copy of
    the same `bool`-excluding validation.

    `bool` is rejected explicitly even though it's an `int` subclass in
    Python — `timeout = true` silently passing as `1` would be a confusing
    way to hit a 1-second timeout, not a deliberate choice.
    """

    value = config.get(key, default)
    allowed: tuple[type, ...] = (int, float) if allow_float else (int,)
    if isinstance(value, bool) or not isinstance(value, allowed):
        kind = "a number" if allow_float else "an integer"
        raise ConfigError(f"[{name}] {key} must be {kind}, got {value!r}")
    return value
