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

"""The `check-env-vars` check (ticket #18): a backticked environment-variable
name, held to the files a project says define its environment.
`docs/checks/check-env-vars.md` is the account of what it reads, which
keys it takes and what it misses; this docstring is why the code is
shaped the way it is.

Its own check because `check-citations` only verifies backticked *symbol*
citations against declared Swift/Rust history — an env var name (a naming
convention, not a language-level declaration) is entirely outside its
vocabulary.

A candidate must be backticked, for the same reason as
`check-config-defaults` (#17): backticking is the cheap signal that
distinguishes a real named technical thing from ordinary emphasis-caps
prose ("NOTE", "TODO"). The underscore requirement in `ENV_VAR_SHAPE_RE`
is what rejects a short protocol acronym ("HTTP", "TLS") on its own. A
candidate inside a fenced code block is skipped — illustrative example
content, not a claim (`check_file_refs._fence_state`'s own precedent;
ticket #17's own copy of this check doesn't have this fix yet, see
`TODO.md`).

**Verification is existence, not value** — unlike #17, which needs a
per-setting mapping specifically to pin down where to compare a *value*,
this check only asks "does this name appear anywhere in a
project-configured scope of files." That scope key is `definition_files`
— deliberately **not** named `files` the way `claim-words` names its own
scope key: that name would mean the opposite thing here. `claim-words`'
`files` scopes *which prose is searched for candidates*; this check's
candidates always come from every tracked `*.md` file (narrowed only by
`exclude`) — `definition_files` scopes *which files count as a definition
a candidate is checked against*. Reusing `files` for that inverted
meaning risks exactly the silent misconfiguration this naming avoids: a
project meaning "also check my docs" that writes
`definition_files = ["docs/*.md"]` would instead make every mention in
those docs self-satisfying and quietly disable the check for them. It is
additive to a built-in default of `.env.example`, the same
default-plus-project-additions shape `restatement.extensions` and
`check-file-refs.extensions` already use. No per-variable registration: a
project names *files*, not variables, and any candidate is checked
against all of them. `exclude` is the same escape hatch
`check-links`/`check-file-refs` already give a project for a directory of
historical or illustrative prose.

**Matching is plain, word-boundary-safe text search** — no language-aware
parsing of what "uses an env var" looks like in any particular language.
A project wanting real usage-pattern awareness (`os.environ`,
`process.env`, ...) is out of scope for this check.

**An empty scope is genuinely inert, not a sweep of everything** — the
same opt-in-by-omission precedent `claim-words` already established.
Sweeping all tracked source unconditionally when nothing is configured
was considered and rejected: unlike `check-file-refs` (checking a
self-contained, unambiguous path), matching a bare token against all
source risks colliding with a same-named local variable, class attribute,
or unrelated constant that merely happens to share the name. "Empty" is
tracked by *how many scope files were found*, not by whether their
concatenated text happens to be non-empty — a tracked but empty
`.env.example` is one found scope file, a scope that defines nothing, so
every candidate is then a finding; not the same case as truly zero scope
files existing.

No command is ever executed here — pure file-read and text search,
keeping this out of #15's permission-gate scope (execution-based
verification is `cli_command`'s own territory, #19).

Findings are advisory, explicitly provisional. **Both directions of this
check's own error rate are real, not just one:** a genuinely-used var
consumed only via a build tool's own config, or constructed indirectly
rather than appearing as a literal token anywhere in the configured
scope, could go unfound through no fault of the claim itself (a false
negative) — but the reverse also happens in practice, not just in theory:
shape-only detection (no phrase anchor the way #17 requires one) means an
ordinary backticked `ALL_CAPS_WITH_UNDERSCORES` constant, enum value, or
regex name that was never meant to name an env var at all is an equally
valid candidate, and gets flagged the same way a real, missing env var
would if the configured scope doesn't happen to mention it too. Confirmed
empirically while dogfooding this exact check against this repo's own
historical `.scratch/` notes, which is exactly the class of prose
`exclude` exists to keep out of the sweep. Revisit detection precision,
not just recall, once real usage gives an actual rate to argue from — not
a permanent design choice either way.

**Note for whoever picks up #22** (on-demand config-fit review): a
project with no `definition_files` configured and no `.env.example`
tracked means this check is silently a no-op — legitimately, for a
project that simply doesn't use env vars, or accidentally, because the
scope was never configured. This check doesn't distinguish the two;
that judgment call is exactly what #22 exists to make on demand, not
something to special-case here.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from pathlib import Path

from ..config import exclude_patterns, path_matches, string_list_config
from ..git import tracked_files
from ..runner import Finding, register_check

NAME = "check-env-vars"

# Built-in default scope entry — a literal pattern, not a glob wildcard,
# so it only ever matches a tracked file actually named `.env.example` at
# the repo root. Additive with a project's own `definition_files` config,
# mirroring `restatement.extensions`/`check-file-refs.extensions`'s own
# default-plus-project-additions shape.
DEFAULT_SCOPE = (".env.example",)

BACKTICK_RE = re.compile(r"`([^`\n]+)`")
# At least one underscore is what excludes a short protocol acronym
# ("HTTP", "TLS") or a plain emphasis-caps word ("NOTE") from ever being a
# candidate — see the module docstring.
ENV_VAR_SHAPE_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")

FENCE_RE = re.compile(r"^\s*(`{3,})")


def _fence_state(lines: Sequence[str]) -> list[bool]:
    """Whether each of `lines` should be excluded from detection because
    it's a fenced code block's own delimiter line or content — same
    nesting rule and delimiter-line handling as
    `check_file_refs._fence_state`; see that function's own docstring for
    the full reasoning, not repeated here.
    """

    in_fence: list[bool] = []
    open_fence: int | None = None
    for line in lines:
        match = FENCE_RE.match(line)
        if match and (open_fence is None or len(match.group(1)) >= open_fence):
            open_fence = None if open_fence is not None else len(match.group(1))
            in_fence.append(True)
            continue
        in_fence.append(open_fence is not None)
    return in_fence


def _definition_scope_patterns(config: Mapping[str, object]) -> tuple[str, ...]:
    return DEFAULT_SCOPE + tuple(string_list_config(config, "definition_files"))


def _read(path: Path) -> str | None:
    """A file's text, or `None` for a symlink, missing file, or unreadable
    path — mirrors every sibling check's own guard.
    """

    if path.is_symlink() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _scope_text(repo_root: Path, patterns: tuple[str, ...]) -> str | None:
    """Every configured scope file's own text, concatenated once — read
    once per `check()` call and reused for every candidate found, rather
    than re-reading the scope per candidate. `None` when *no* scope file
    was found at all (the genuinely-inert case) — distinct from finding
    one or more scope files whose own text happens to be empty, which is
    a found, if currently-empty, scope, not an absent one.
    """

    texts: list[str] = []
    for rel in tracked_files(repo_root):
        if path_matches(rel, patterns):
            text = _read(repo_root / rel)
            if text is not None:
                texts.append(text)
    return "\n".join(texts) if texts else None


def _in_scope(name: str, scope_text: str) -> bool:
    return re.search(rf"\b{re.escape(name)}\b", scope_text) is not None


def _finding(rel: str, line_no: int, name: str) -> Finding:
    return Finding(
        file=rel,
        line=line_no,
        message=f"`{name}` is not defined or used anywhere in the configured scope",
        mode=NAME,
        gate=False,
    )


def check(repo_root: Path, diff_range: str, config: Mapping[str, object]) -> list[Finding]:
    scope_text = _scope_text(repo_root, _definition_scope_patterns(config))
    if scope_text is None:
        return []

    exclude = exclude_patterns(config)
    findings: list[Finding] = []
    for rel in sorted(tracked_files(repo_root, "*.md")):
        if path_matches(rel, exclude):
            continue
        text = _read(repo_root / rel)
        if text is None:
            continue
        lines = text.splitlines()
        in_fence = _fence_state(lines)
        for line_no, line in enumerate(lines, 1):
            if in_fence[line_no - 1]:
                continue
            for match in BACKTICK_RE.finditer(line):
                name = match.group(1)
                if not ENV_VAR_SHAPE_RE.match(name):
                    continue
                if _in_scope(name, scope_text):
                    continue
                findings.append(_finding(rel, line_no, name))

    return findings


register_check(NAME, check)
