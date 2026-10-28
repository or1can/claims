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

"""The commit-time decision for one repository, which the git
`pre-commit` command (`claims.pre_commit`) turns into its exit code and
stderr without deciding anything itself.

A repository opts in with a root `claims.toml`
(`decisions/0006-claims-toml-opts-in-to-the-commit-hook.md`): without one
there is nothing to decide and no check runs.

Besides `[hook] enabled = false`, which switches the whole decision off,
a single check can be silenced from this decision alone via its own
`enabled = false` (`_disabled_checks`, ticket #44) — e.g.
`[stale-claims]\nenabled = false`.
Both flags only ever affect this commit-time decision: `python3 -m
claims.cli` and the `check-claims` skill both call `run()` directly and
never read `[hook]` or a check's own `enabled` key at all, so a check
silenced here is still fully visible on demand through either of those.
A check's own `enabled` key sitting alongside its other config (`exclude`,
`module_reference_scope`, ...) isn't itself an unrecognized table (ticket
#21's own gate) — it's a key inside an already-recognized table, a
different, unrelated check.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from . import checks  # noqa: F401
from .config import ConfigError, has_config, load_config
from .runner import Finding, run


@dataclass(frozen=True)
class Decision:
    """What a commit hook reports: `message` to show, and whether it
    blocks the commit (`block`) or only advises."""

    block: bool
    message: str


def _summarize(findings: tuple[Finding, ...]) -> str:
    return "\n".join(str(f) for f in findings)


def _disabled_checks(
    config: Mapping[str, object], registered: Sequence[str]
) -> frozenset[str]:
    """Every name in `registered` whose own `claims.toml` section reads
    `enabled = false` (ticket #44) — hook-scoped, alongside the existing
    plugin-wide `[hook] enabled`: this only silences that one check's own
    findings from *this* commit-time decision, never from `python3 -m
    claims.cli`/the `check-claims` skill, both of which call `run()`
    directly and never consult either flag.

    Restricted to `registered` (`RunResult.checks_run`, not `config`'s own
    keys) for two reasons at once: a top-level `claims.toml` value isn't
    guaranteed to even be a table (`config.py`'s own `_load_toml` return
    type is a lie past the top level — a bare `enabled = false` with no
    `[section]` at all is a real, unvalidated `bool`, not a `Mapping`,
    and would otherwise crash this function, letting the commit land
    completely unchecked); and an
    unrecognized name here — `"config"`, the fixed `mode`
    `_unrecognized_table_findings` reports its own findings under, or any
    other typo — must never silence anything, since `[config] enabled =
    false` would otherwise silence the exact gate finding meant to warn
    about a `claims.toml` mistake, including that very one (ticket #21).
    """

    return frozenset(
        name
        for name, section in config.items()
        if name != "hook"
        and name in registered
        and isinstance(section, Mapping)
        and not section.get("enabled", True)
    )


def _finding_check(finding: Finding, names: frozenset[str]) -> str | None:
    """Which of `names` produced `finding`, or `None` if it isn't any of
    them — `Finding.mode` is usually a check's own registered name, but a
    check reporting more than one matching strategy (`restatement`'s own
    `-ngram`/`-whole-line` split, and similarly for `claim-words`,
    `spliced-docs`, `judgment-agent`) instead uses `{name}-suffix`, a
    convention every current multi-mode check follows but nothing in
    `Finding`'s own contract guarantees. Checked here, not by adding a
    `check` field to `Finding` itself: that would need updating every
    existing test asserting a hand-built `Finding(...)` against a real
    check's own output, for one commit-time filter.
    """

    for name in names:
        if finding.mode == name or finding.mode.startswith(f"{name}-"):
            return name
    return None


def decide_repo(repo_root: Path) -> Decision | None:
    """The decision for a commit to the repository at `repo_root`, or
    `None` when there is nothing to report: it hasn't opted in with a root
    `claims.toml`, has switched the hook off, or has no finding left once
    disabled checks are filtered out."""

    if not has_config(repo_root):
        return None

    try:
        config = load_config(repo_root)
    except ConfigError as e:
        return Decision(block=True, message=f"claims.toml is invalid: {e}")

    if not config.get("hook", {}).get("enabled", True):
        return None

    result = run(repo_root, "HEAD", config)

    if not result.checks_run:
        return Decision(
            block=True,
            message="0 checked — no checks registered (failure, not a clean pass)",
        )

    disabled = _disabled_checks(config, result.checks_run)
    findings = tuple(
        f for f in result.findings if _finding_check(f, disabled) is None
    )

    if not findings:
        return None
    return Decision(block=any(f.gate for f in findings), message=_summarize(findings))
