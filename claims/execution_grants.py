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

"""The shared local execution-grant mechanism (ticket #15, generalized in
#19 once a second execution-capable check existed).

`executable-claims` (#15) established the property: a check that executes
a command a project's own prose names must deny that execution by
default and require an exact-string grant in `claims.local.toml`'s own
section before running it — committed `claims.toml` can't be the trust
boundary (a PR can change it), and a `claims.local.toml` that's ever
*tracked* by git must have its grants ignored outright, since `.gitignore`
only stops it being added, not a version already committed. See
`claims/checks/executable_claims.py`'s own module docstring for the full
original security reasoning; it isn't repeated here.

#15's own brief implemented this inside `executable_claims.py` directly
rather than as a generic mechanism, deliberately — "extract a shared
pattern only when a second one exists." #19 (`check-cli-flags`) is that
second execution-capable check, so this module holds the mechanism once,
keyed by whichever check calls it, rather than a second bespoke copy.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from .config import LOCAL_CONFIG_FILENAME, load_local_config, string_list_config
from .git import tracked_files
from .runner import Finding

# `icase` so a same-named file tracked under a case-variant spelling
# (`Claims.Local.toml`) is still caught on a case-insensitive filesystem
# (macOS, Windows) — `git ls-files` itself matches a bare pathspec
# case-sensitively regardless of the filesystem, so without this an
# attacker's PR committing that variant would be invisible to
# `tracked_files` while `Path.open` (which *does* follow the filesystem's
# own case-folding) still reads and honors it. `top` anchors to the repo
# root the same way the bare filename already implicitly did, kept
# explicit alongside `icase` rather than relying on that implicit
# behavior to still hold once a pathspec magic prefix is added.
_LOCAL_CONFIG_PATHSPEC = f":(icase,top){LOCAL_CONFIG_FILENAME}"


def toml_string(value: str) -> str:
    """`value` as a TOML basic (double-quoted) string literal — escaping
    only what a basic string requires for this purpose, backslash and the
    double quote itself, since a command routinely contains a single
    quote (`shlex.quote`'s own escaping) that a TOML literal (single-quoted)
    string can't represent at all.
    """

    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _grants(
    local_config: Mapping[str, object], check_name: str
) -> tuple[frozenset[str], frozenset[str]]:
    """`(allowed, denied)` exact-command-string sets from `claims.local.toml`'s
    own `[<check_name>]` section. Both empty when the section, or the file
    itself, is absent — see `local_grants`: absent means every command
    gates, not that every command is implicitly allowed.
    """

    section = local_config.get(check_name, {})
    if not isinstance(section, Mapping):
        return frozenset(), frozenset()
    return (
        frozenset(string_list_config(section, "allowed")),
        frozenset(string_list_config(section, "denied")),
    )


def _tracked_local_config_finding(check_name: str) -> Finding:
    return Finding(
        file=LOCAL_CONFIG_FILENAME,
        line=0,
        message=(
            f"{LOCAL_CONFIG_FILENAME} is tracked by git, so its "
            "content is attacker-controllable via any PR — its grants "
            "are ignored. If you didn't add this file yourself, delete "
            "it; do not just untrack it, since `git rm --cached` alone "
            "leaves its content on disk and any later change could "
            "still make it tracked again. If it is yours, review its "
            "content first, then `git rm --cached "
            f"{LOCAL_CONFIG_FILENAME}` to keep it local-only."
        ),
        mode=check_name,
        gate=True,
    )


def local_grants(
    repo_root: Path, check_name: str
) -> tuple[frozenset[str], frozenset[str], Finding | None]:
    """`(allowed, denied, warning)` for `check_name`'s own section of this
    repo's `claims.local.toml` — identical behavior regardless of which
    execution-capable check calls this.

    `.gitignore` only stops git from ever *adding* a matching path — it
    does nothing once that path is already tracked, e.g. committed by an
    attacker's own PR, alongside a planted claim, specifically to defeat
    this gate. So a `claims.local.toml` that's tracked at all is exactly
    the committed, PR-tamperable trust boundary this mechanism exists to
    stop relying on, and its grants must not be honored: checked directly
    against git's own index (`tracked_files`), not inferred from
    `.gitignore` alone. Failing closed here means both sets come back
    empty (every command then gates, same as no file existing at all) —
    not that a tracked file's `denied` entries stay honored while only
    `allowed` is dropped, which would still let a tracked file suppress
    findings.
    """

    if tracked_files(repo_root, _LOCAL_CONFIG_PATHSPEC):
        return frozenset(), frozenset(), _tracked_local_config_finding(check_name)
    allowed, denied = _grants(load_local_config(repo_root), check_name)
    return allowed, denied, None
