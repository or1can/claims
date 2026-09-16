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

"""Mechanical helper for `check-claims`' on-demand `claims.toml` review
(ticket #22, `claims/skill/SKILL.md`'s "Reviewing whether config actually
fits" step).

For every glob- or extension-shaped value in a project's `claims.toml`,
computes whether it currently matches anything in the tracked tree —
exact `path_matches`/suffix matching against real `tracked_files()`
output, never an approximation via generic text search. This module
produces structured facts only: whether a zero-match value is a typo, a
staleness signal, or a plausible deliberate, forward-looking choice (a
project adding `.rs` to `restatement.extensions` before its first Rust
file lands) is a judgment call for the on-demand skill's own reasoning
step, not something this helper decides.
"""

from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .config import path_matches, string_list_config
from .git import tracked_files

# Every check's own glob-shaped config key, matched against the tracked
# tree the same way that check itself matches it (`path_matches`, i.e.
# `fnmatch`). Deliberately not every key in every check's section: e.g.
# `executable-claims`'s own `permitted_prefixes` is a literal
# command-string prefix, not a file glob, and `spliced-docs`'s `modes`
# names a fixed enum — neither has a "matches nothing in the tree" fact to
# compute at all, so including them would only ever report a false zero.
GLOB_CONFIG_KEYS: Mapping[str, Sequence[str]] = {
    "executable-claims": ("exclude",),
    "restatement": ("exclude",),
    "check-links": ("exclude",),
    "check-file-refs": ("exclude",),
    "claim-words": ("files",),
    "stale-claims": ("module_reference_scope",),
}

# `restatement`'s own `extensions`, and `check-file-refs`' own `extensions`
# (ticket #16, same additive-to-a-built-in-set shape): a dotted suffix
# compared via `str.endswith`, mirroring each check's own matching — not a
# glob pattern, so kept out of `GLOB_CONFIG_KEYS` rather than fed through
# `path_matches`, which would treat `.rs` as a literal path to equal, not
# a suffix to match against.
EXTENSION_CONFIG_KEYS: Mapping[str, Sequence[str]] = {
    "restatement": ("extensions",),
    "check-file-refs": ("extensions",),
}

# Every other registered check's own config section carries nothing
# glob/extension-shaped at all (`check-citations`/`judgment-agent` read no
# config; `spliced-docs`'s `modes` names a fixed enum; `check-config-defaults`'
# own section is itself a setting-name -> file:line mapping, not a glob or
# extension list). Listed explicitly, not left as "everything else" —
# `test_config_review.py`'s own completeness test checks every registered
# check name appears in exactly one of the three sets, so a future check
# adding a path-shaped key without updating this module fails loud (a red
# test) instead of the check simply never being reviewed by this helper.
NO_PATH_SHAPED_CONFIG = frozenset(
    {"check-citations", "spliced-docs", "judgment-agent", "check-config-defaults"}
)


@dataclass(frozen=True)
class ConfigValueMatch:
    """One configured glob/extension `value`, under `check`'s own `key`,
    and which tracked files (if any) it currently matches.

    `matched_files == ()` is exactly the fact this review step exists to
    surface — not itself a verdict. Whether that's a typo, staleness, or a
    plausible deliberate choice is left to the caller to judge.

    `error` is set instead of `matched_files` being trusted when the
    configured value itself couldn't be read as a list of strings (e.g.
    `exclude = 5`) — this helper runs interactively, outside `runner.run`'s
    own try/except-wrapped, per-check crash isolation, so one malformed
    value must not raise and take every other check's facts down with it.
    """

    check: str
    key: str
    value: str
    matched_files: tuple[str, ...]
    error: str | None = None


def _repo_toplevel(repo_root: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()) if result.returncode == 0 else None


def _read_values(section: Mapping[str, object], key: str) -> tuple[list[str], str | None]:
    """`section[key]` as a list of strings, or `([], error)` if it can't
    be read as one — including a list whose own elements aren't all
    strings (`exclude = [5]`): `string_list_config` only coerces a bare
    string, it doesn't validate elements, so an element-level type error
    would otherwise only surface later, inside the matching loop this
    function's caller runs *outside* this try/except.
    """

    try:
        values = list(string_list_config(section, key))
    except Exception as exc:  # noqa: BLE001 - reported as a fact, not raised
        return [], f"{type(exc).__name__}: {exc}"
    non_strings = [v for v in values if not isinstance(v, str)]
    if non_strings:
        return [], f"not every entry is a string: {non_strings!r}"
    return values, None


def config_value_matches(
    repo_root: Path, config: Mapping[str, Mapping[str, object]]
) -> list[ConfigValueMatch]:
    """One `ConfigValueMatch` per glob/extension-shaped value present in
    `config`, across every check `GLOB_CONFIG_KEYS`/`EXTENSION_CONFIG_KEYS`
    name — computed once against `repo_root`'s real tracked tree. A
    section under a check name neither map knows (including one that
    isn't a registered check at all — ticket #21 covers *that* mistake
    separately) is silently skipped here, not raised on: this helper's own
    job is "does this value match anything," not "is this config valid."

    Raises `ValueError` if `repo_root` isn't a git repository, or isn't
    that repository's own top level: `tracked_files` runs `git ls-files`
    scoped to git's own current working directory, so from a subdirectory
    it silently returns that subdirectory's own tracked files, re-based to
    it — a root-anchored glob then compares against paths it could never
    match, and every configured value would misreport as matching
    nothing. Raising here converts that from a plausible-looking wrong
    answer into a loud one, since every fact this module produces depends
    on `repo_root` actually being the tree the whole tracked tree measures
    against.
    """

    toplevel = _repo_toplevel(repo_root)
    if toplevel is None or toplevel.resolve() != repo_root.resolve():
        raise ValueError(
            f"{repo_root} is not a git repository's own top level "
            f"({'not a git repository' if toplevel is None else f'top level is {toplevel}'}) "
            "— config_value_matches must be called with the repo root itself, "
            "not a subdirectory, or every match would silently be computed "
            "against the wrong, narrower set of tracked files"
        )

    tracked = tracked_files(repo_root)
    results: list[ConfigValueMatch] = []

    for check, keys in GLOB_CONFIG_KEYS.items():
        section = config.get(check, {})
        if not isinstance(section, Mapping):
            continue
        for key in keys:
            values, error = _read_values(section, key)
            if error is not None:
                results.append(ConfigValueMatch(check, key, repr(section.get(key)), (), error))
                continue
            for pattern in values:
                matched = tuple(f for f in tracked if path_matches(f, [pattern]))
                results.append(ConfigValueMatch(check, key, pattern, matched))

    for check, keys in EXTENSION_CONFIG_KEYS.items():
        section = config.get(check, {})
        if not isinstance(section, Mapping):
            continue
        for key in keys:
            values, error = _read_values(section, key)
            if error is not None:
                results.append(ConfigValueMatch(check, key, repr(section.get(key)), (), error))
                continue
            for extension in values:
                matched = tuple(f for f in tracked if f.endswith(extension))
                results.append(ConfigValueMatch(check, key, extension, matched))

    return results
