# 12 — Port check-citations check (gate)

**What to build:** a check finding a backticked name that cites a symbol the
project once declared (via full commit history) but no longer does.
Registered as a **gate** check.

**Blocked by:** 06.

**Status:** resolved

- [x] A citation to a symbol that was removed after being declared is
      flagged.
- [x] A citation to a symbol that still exists is not flagged.
- [x] An explicit "was: <name>" marker exempts a deliberately historical
      reference.
- [x] Run against a shallow clone (insufficient history to answer honestly)
      fails distinctly rather than reporting a false clean pass.

## Answer

Built as `claims/checks/check_citations.py`, registered in
`claims/checks/__init__.py`. Ported from Project B's `scripts/check-citations`
(Apache-2.0/relicensed prior art, same author) — the only surveyed source
tool with this check; `ratect` has no equivalent (tool-survey.md). Scope
matches the source tool exactly: tracked `*.md` and comments in tracked
`*.swift`. The Swift declaration regex (`SWIFT_DECL_RE`) is imported from
`spliced_docs` rather than redefined, avoiding the exact "two independently-
written answers to 'what does this repository declare' drift apart" failure
Project B's own `tools/claims.py` names as its reason for existing.

Registered as a **gate** check (spec.md's check inventory), unlike this
repo's other, advisory ports: a rename either left a citation behind or it
did not.

A shallow clone — or any other git failure while reading full history —
raises an internal `_UnusableRepository`, caught by `check()` and turned
into a single gate `Finding` (`file="."`, `line=0`) rather than a crash or
a silent, false-clean pass, matching `executable-claims`' existing "say so,
don't just report zero" shape.

Tests: `tests/test_check_citations.py` (12 cases) against fixture git repos
— a removed-symbol citation flagged, a still-existing citation not flagged,
a `<!-- was: name -->` marker exempting a citation (and its one-line-only
carry), a Swift-comment citation, a test-target-name citation not flagged,
a shallow clone (built via a real `git clone --depth 1`) and a non-git
directory each producing one gate finding rather than a crash or an empty
list, plus the CLI's exit-code contract. 84 tests total across the suite,
all green.

Post-review (`/code-review`, 8 parallel finder agents): three real,
reproduced bugs fixed before landing —

- `_git`'s subprocess call never checked its return code, so any git
  failure (not just a shallow clone — a corrupted repo, an unsupported git
  version, a plain non-git directory) returned an empty string and was
  silently read as "full history, nothing ever declared," producing a
  false-clean pass — the exact failure mode this check's own docstring
  says it exists to refuse, just not guarded against outside the one
  shallow-clone case it explicitly checked for. Fixed by having `_git`
  raise `_UnusableRepository` on a non-zero exit, caught by `check()`
  alongside the shallow-clone case.
- `_declared_now` read every tracked `*.swift` file with no symlink guard,
  unlike `check()`'s own citation-scanning loop 40 lines below it (which
  has one) — a tracked dangling symlink crashed the check with an
  unhandled `FileNotFoundError` before that guarded loop was ever reached.
  Fixed by factoring both call sites onto one `_read_tracked` helper.
- The `was:` exemption matched the bare substring `was:` anywhere in a
  line's citable text, not the documented `<!-- was: name -->` /
  `// was: name` marker syntax — an ordinary sentence using the word
  ("the old name was: `loadWidget`") silently exempted a genuinely dead
  citation. This is inherited verbatim from Project B's own script, which
  has the identical gap, but since this check gates a commit (unlike that
  script's advisory-in-practice usage there), a silent false-negative here
  is worse than in the source tool. Fixed by anchoring the marker to an
  HTML comment in Markdown and to a whole from-scratch comment in Swift,
  via a new `_exempt_names` helper.

The review's remaining findings (an uncached full-history `git log -p` walk
on every invocation, a locally-reimplemented `_git` subprocess wrapper
mirroring `stale_claims.py`'s own private one rather than a shared
`claims/git.py` helper, `_target_names` scanning every tracked file rather
than only Swift-adjacent ones, duplicate findings when one dead name is
cited twice on one line) were left as-is: each mirrors an existing pattern
already accepted elsewhere in this codebase (every check module has its
own private git-subprocess helper; `_target_names` is ported verbatim from
Project B), or is a cost/verbosity tradeoff rather than a correctness gap,
and none was asked for by this ticket's acceptance criteria.
