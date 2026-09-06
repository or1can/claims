"""The shared seam every check and every entry point (CLI, hook, skill) calls.

A check is a pure function `(repo_root, diff_range, config) -> list[Finding]`.
Checks register themselves via `register_check`; the runner never hardcodes
a check list.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

CheckFn = Callable[[Path, str, Mapping[str, object]], Sequence["Finding"]]


@dataclass(frozen=True)
class Finding:
    """One thing a check found.

    `file`/`line` cite where the finding applies. `mode` names the matching
    strategy for checks that have more than one (e.g. n-gram vs whole-line);
    checks with only one strategy may leave it as the check's own name.
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


def run(
    repo_root: Path, diff_range: str, config: Mapping[str, Mapping[str, object]]
) -> RunResult:
    """Run every registered check and collect their findings.

    `repo_root` and `diff_range` are passed through to every check
    unchanged. Each check receives only its own section of `config`
    (keyed by the check's registered name), never the whole project config.
    """

    findings: list[Finding] = []
    for name, check in _registry.items():
        check_config = config.get(name, {})
        findings.extend(check(repo_root, diff_range, check_config))
    return RunResult(checks_run=tuple(_registry), findings=tuple(findings))
