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

"""The shared seam every check and every entry point (CLI, hook, skill) calls.

A check is a pure function `(repo_root, diff_range, config) -> list[Finding]`.
Checks register themselves via `register_check`; the runner never hardcodes
a check list.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .config import CONFIG_FILENAME

CheckFn = Callable[[Path, str, Mapping[str, object]], Sequence["Finding"]]


@dataclass(frozen=True)
class Finding:
    """One thing a check found.

    `file`/`line` cite where the finding applies. `mode` names the matching
    strategy for checks that have more than one (e.g. n-gram vs whole-line);
    checks with only one strategy may leave it as the check's own name. A
    finding with no originating check at all — `_crash_finding` uses the
    crashed check's own name, `_unrecognized_table_findings` (ticket #21)
    uses the fixed name `"config"`, since no `claims.toml` table can
    collide with it — is the one exception to "names a check."
    `gate` is True when this finding's check type should block a commit.
    """

    file: str
    line: int
    message: str
    mode: str
    gate: bool

    @property
    def citation(self) -> str:
        return f"{self.file}:{self.line}"

    def __str__(self) -> str:
        marker = "GATE" if self.gate else "advisory"
        return f"[{marker}] {self.citation} ({self.mode}) {self.message}"


@dataclass(frozen=True)
class RunResult:
    checks_run: tuple[str, ...]
    findings: tuple[Finding, ...]


_registry: dict[str, CheckFn] = {}


def register_check(name: str, fn: CheckFn) -> None:
    """Register `fn` under `name`.

    Raises if `name` is already registered — two checks silently sharing a
    name would mean one of them never runs.
    """

    if name in _registry:
        raise ValueError(f"check {name!r} is already registered")
    _registry[name] = fn


def clear_registry() -> None:
    """Test-only: drop all registered checks."""

    _registry.clear()


def _crash_finding(name: str, exc: Exception) -> Finding:
    return Finding(
        file=".",
        line=0,
        message=f"check {name!r} crashed: {type(exc).__name__}: {exc}",
        mode=name,
        gate=True,
    )


# `claims.toml`'s one legitimate top-level table that isn't a registered
# check's own name — see `docs/installation.md`'s "Disabling the automatic
# hook" section. Any other unrecognized table is a project's config
# silently doing nothing (ticket #21), not a second exception to add here.
_KNOWN_NON_CHECK_TABLES = frozenset({"hook"})


def _normalize_table_name(name: str) -> str:
    """`name` with underscores folded to the hyphens every registered check
    name actually uses — the one typo shape common enough to name a likely
    intended check for (`[executable_claims]` for `[executable-claims]`),
    not a general fuzzy match. Case is deliberately left alone: a
    case-only typo (`[Executable-Claims]`) is still caught (it's simply
    not a registered name) but gets no suggestion, the same as any other
    typo shape this function doesn't specifically recognize.
    """

    return name.replace("_", "-")


def _unrecognized_table_findings(
    config: Mapping[str, Mapping[str, object]], registered_names: Sequence[str]
) -> list[Finding]:
    """One gate finding per top-level `claims.toml` table that names
    neither a registered check nor `_KNOWN_NON_CHECK_TABLES` — a project's
    entry under a table like that silently configures nothing today (`{}`
    is what `config.get(name, {})` gets every check whose name it doesn't
    match), which looks like a working opt-out right up until it isn't.
    Scoped to `claims.toml` specifically: `claims.local.toml` (this
    check's own git-ignored grant file, ticket #15) isn't validated here —
    a mistyped table there is a separate, currently-unclosed gap.

    Checked against the registry's *live* names, not a hardcoded list, so
    this never drifts out of sync with whatever checks actually exist —
    including a project's own `claims.toml` naming a check that exists
    upstream but not yet in this machine's installed `claims` copy, which
    reads as "not a registered check name" here too; that's accurate for
    what's actually running, even though the fix in that case is
    upgrading the plugin, not editing the table name.
    """

    normalized_registered = {_normalize_table_name(n): n for n in registered_names}
    findings: list[Finding] = []
    for table in config:
        if table in registered_names or table in _KNOWN_NON_CHECK_TABLES:
            continue
        message = f"[{table}] is not a registered check name or [hook]"
        suggestion = normalized_registered.get(_normalize_table_name(table))
        if suggestion is not None:
            message += f" — did you mean [{suggestion}]?"
        findings.append(
            Finding(file=CONFIG_FILENAME, line=0, message=message, mode="config", gate=True)
        )
    return findings


def run(
    repo_root: Path, diff_range: str, config: Mapping[str, Mapping[str, object]]
) -> RunResult:
    """Run every registered check and collect their findings.

    `repo_root` and `diff_range` are passed through to every check
    unchanged. Each check receives only its own section of `config`
    (keyed by the check's registered name), never the whole project config.

    A check that raises doesn't crash the run: it's caught here and turned
    into one gate finding naming the check and the exception, so every
    other registered check still runs and the crash is reported rather
    than silently swallowed.

    Before any check runs, `config`'s own top-level table names are
    checked against the live registry (`_unrecognized_table_findings`,
    ticket #21): a table naming neither a registered check nor `[hook]`
    gets its own gate finding rather than silently resolving to an empty
    section for a check that doesn't exist.
    """

    findings: list[Finding] = list(_unrecognized_table_findings(config, tuple(_registry)))
    for name, check in _registry.items():
        check_config = config.get(name, {})
        try:
            findings.extend(check(repo_root, diff_range, check_config))
        except Exception as exc:
            findings.append(_crash_finding(name, exc))
    return RunResult(checks_run=tuple(_registry), findings=tuple(findings))
