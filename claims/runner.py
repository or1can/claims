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

from .config import CONFIG_FILENAME, LOCAL_CONFIG_FILENAME, ConfigError, load_local_config

CheckFn = Callable[[Path, str, Mapping[str, object]], Sequence["Finding"]]


@dataclass(frozen=True)
class Finding:
    """One thing a check found.

    `file`/`line` cite where the finding applies. `mode` names the matching
    strategy for checks that have more than one (e.g. n-gram vs whole-line);
    checks with only one strategy may leave it as the check's own name. A
    finding with no originating check at all — `_crash_finding` uses the
    crashed check's own name, `_unrecognized_table_findings` (ticket #21)
    uses the fixed name `"config"`, since no config table can collide
    with it — is the one exception to "names a check."
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
        return format_findings([self])[0]


def format_findings(findings: Sequence[Finding]) -> list[str]:
    """One printed line per distinct `(file, line, message, gate)`, naming
    every mode that reported it, in first-seen order (ticket #153). A
    sentence several modes match would otherwise print once per mode. The
    CLI and the commit hook both print through this, and so does a lone
    finding's own `str`."""

    groups: dict[tuple[str, int, str, bool], list[Finding]] = {}
    for f in findings:
        groups.setdefault((f.file, f.line, f.message, f.gate), []).append(f)
    lines = []
    for group in groups.values():
        first = group[0]
        modes = ", ".join(dict.fromkeys(f.mode for f in group))
        marker = "GATE" if first.gate else "advisory"
        lines.append(f"[{marker}] {first.citation} ({modes}) {first.message}")
    return lines


@dataclass(frozen=True)
class RunResult:
    checks_run: tuple[str, ...]
    findings: tuple[Finding, ...]
    # Advisory findings a checked mark kept out of `findings` (ADR 0010).
    quiet: tuple[Finding, ...] = ()
    # The part of `quiet` a partial mark keeps quiet.
    quiet_partly: tuple[Finding, ...] = ()


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


# `claims.toml`'s top-level tables that aren't a registered check's own
# name: `[hook]` (`docs/configuring.md`'s "Switching the commit hook off")
# and `[subjects]` (ADR 0011). Any other unrecognized table is a project's
# config silently doing nothing (ticket #21).
_KNOWN_NON_CHECK_TABLES = frozenset({"hook", "subjects"})

# The keys `[subjects]` takes: it belongs to no check, so no check's own
# reading of it would notice a misspelt one.
_SUBJECTS_KEYS = frozenset({"append_only", "navigation"})

# The keys `[hook]` takes, read by `claims.gate`'s commit-time decision
# under these names. The gate reads only the keys it knows, so a misspelt
# one would otherwise silently do nothing (#210).
HOOK_ENABLED = "enabled"
HOOK_FAIL_ON_UNMARKED = "fail_on_unmarked"
HOOK_KEYS = (HOOK_ENABLED, HOOK_FAIL_ON_UNMARKED)

# `claims.local.toml`'s counterpart: `[nudge]`, one person's opt-out from
# the missing-hook nudge in one clone (ticket #132) — see `claims.nudge`.
_KNOWN_LOCAL_NON_CHECK_TABLES = frozenset({"nudge"})


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
    config: Mapping[str, Mapping[str, object]],
    registered_names: Sequence[str],
    filename: str,
    known_non_check_tables: frozenset[str],
) -> list[Finding]:
    """One gate finding, cited against `filename`, per top-level table of
    `config` that names neither a registered check nor one of
    `known_non_check_tables` — a project's entry under a table like that
    silently configures nothing today (`{}` is what `config.get(name, {})`
    gets every check whose name it doesn't match), which looks like a
    working opt-out right up until it isn't.

    Run over both `claims.toml` (ticket #21) and `claims.local.toml`
    (ticket #86), where a mistyped grant table grants nothing just as
    silently. The local file's accepted set is every registered check
    name, not only the checks that read local grants today: which checks
    those are is recorded only inside their own bodies (their
    `local_grants` call), so a hardcoded subset here would drift the
    moment a check started or stopped reading grants. `[hook]` is not
    accepted there — the hook reads `claims.toml` only — and `[nudge]`
    is accepted there alone, since the nudge's opt-out is per person.

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
        if table in registered_names or table in known_non_check_tables:
            continue
        message = f"[{table}] is not a registered check name"
        if known_non_check_tables:
            message += " or " + ", ".join(f"[{t}]" for t in sorted(known_non_check_tables))
        suggestion = normalized_registered.get(_normalize_table_name(table))
        if suggestion is not None:
            message += f" — did you mean [{suggestion}]?"
        findings.append(
            Finding(file=filename, line=0, message=message, mode="config", gate=True)
        )
    return findings


def _unrecognized_subjects_key_findings(
    config: Mapping[str, Mapping[str, object]],
) -> list[Finding]:
    """One gate finding per key of `[subjects]` it doesn't take, cited
    against `claims.toml` as an unrecognized table is. A `[subjects]` that
    isn't a table is `load_config`'s to refuse, so none is reported here."""

    subjects = config.get("subjects", {})
    if not isinstance(subjects, Mapping):
        return []
    return [
        Finding(
            file=CONFIG_FILENAME,
            line=0,
            message=f"[subjects] {key} is not a recognized key — [subjects] takes append_only, navigation",
            mode="config",
            gate=True,
        )
        for key in subjects
        if key not in _SUBJECTS_KEYS
    ]


def _unrecognized_hook_key_findings(
    config: Mapping[str, Mapping[str, object]],
) -> list[Finding]:
    """`_unrecognized_subjects_key_findings`'s counterpart for `[hook]`
    (#210): run here, not by the gate, so a CLI run reports a typo even
    while `[hook] enabled = false` has the hook off. A `[hook]` that isn't
    a table is the gate's to refuse, so none is reported here."""

    hook = config.get("hook", {})
    if not isinstance(hook, Mapping):
        return []
    return [
        Finding(
            file=CONFIG_FILENAME,
            line=0,
            message=f"[hook] {key} is not a recognized key — [hook] takes {', '.join(HOOK_KEYS)}",
            mode="config",
            gate=True,
        )
        for key in hook
        if key not in HOOK_KEYS
    ]


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
    ticket #21): a table naming neither a registered check, `[hook]` nor
    `[subjects]` gets its own gate finding rather than silently resolving
    to an empty section for a check that doesn't exist, and so does a key
    `[subjects]` or `[hook]` doesn't take. `repo_root`'s own
    `claims.local.toml` gets the same check (ticket #86). A local file
    that doesn't parse is skipped here rather than raised: each check that
    reads it turns that `ConfigError` into its own crash finding when it
    runs.

    After every check, `claims.checked.toml`'s marks are applied
    (`claims.checked`): an advisory finding a current mark covers moves to
    `RunResult.quiet` (and `quiet_partly` too, for a partial mark), and a
    mark whose unit is gone is reported. A sidecar that doesn't parse is
    one gate finding, so it blocks a commit the way an invalid
    `claims.toml` does.
    """

    registered = tuple(_registry)
    findings: list[Finding] = _unrecognized_table_findings(
        config, registered, CONFIG_FILENAME, _KNOWN_NON_CHECK_TABLES
    )
    findings.extend(_unrecognized_subjects_key_findings(config))
    findings.extend(_unrecognized_hook_key_findings(config))
    try:
        local_config = load_local_config(repo_root)
    except ConfigError:
        local_config = {}
    findings.extend(
        _unrecognized_table_findings(
            local_config, registered, LOCAL_CONFIG_FILENAME, _KNOWN_LOCAL_NON_CHECK_TABLES
        )
    )
    for name, check in _registry.items():
        check_config = config.get(name, {})
        try:
            findings.extend(check(repo_root, diff_range, check_config))
        except Exception as exc:
            findings.append(_crash_finding(name, exc))

    # Imported here: `checked` builds `Finding`s, so imports this module.
    from .checked import CHECKED_FILENAME, apply_marks

    quiet: list[Finding] = []
    partly: list[Finding] = []
    try:
        findings, quiet, partly = apply_marks(repo_root, findings, config)
    except ConfigError as e:
        findings.append(
            Finding(file=CHECKED_FILENAME, line=0, message=f"is invalid: {e}", mode="config", gate=True)
        )
    except Exception as exc:
        # As for a check: one crash finding, every other finding kept.
        findings.append(_crash_finding("checked-marks", exc))
    return RunResult(
        checks_run=tuple(_registry),
        findings=tuple(findings),
        quiet=tuple(quiet),
        quiet_partly=tuple(partly),
    )
