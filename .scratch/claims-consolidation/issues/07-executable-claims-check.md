# 07 — Port executable-claims check (gate)

**What to build:** a marker-based executable-claims check — a
`<!-- verify: cmd -->` marker above a fenced block runs `cmd` through a
shell and diffs its output (and exit code) against the block — registered
against the core runner as a **gate** check.

**Blocked by:** 06.

**Status:** resolved

- [x] A true claim (command output matches the block, exit code zero) passes.
- [x] A false claim (output mismatch, or non-zero exit code even when text
      matches) fails.
- [x] A sweep that finds zero markers, or a marker with a malformed block,
      is reported as a failure — never a silent "0 checked, 0 failures"
      clean pass.
- [x] The command runs through a shell (not `shlex.split`), so a marker
      needing a pipe (`| tail -1`) works.
- [x] Demonstrated end-to-end via the CLI from ticket 06 against a fixture
      repo with a true marker, a false marker, and a malformed marker.

## Answer

`claims/checks/executable_claims.py` — `NAME = "executable-claims"`,
`check(repo_root, diff_range, config) -> list[Finding]`, self-registered as
a gate check via `register_check(NAME, check)` at import time. Ported the
marker/fence parsing (`_blocks`, `_dedent`, `_trim`) from `verify-docs.py`
(Apache-2.0 prior art per spec.md), adapted for this ticket's two new
requirements the source tool didn't have: runs each command via
`subprocess.run(command, shell=True, ...)` instead of `shlex.split`, and
fails on a non-zero exit code independently of whether the output text
matches.

Not diff-scoped — `diff_range` is accepted (to match the shared `CheckFn`
shape) but unused; the check sweeps every tracked `*.md` file via
`git ls-files`, matching the source tool and the spec's check inventory
(only `restatement`/`claim-words` are specified as diff-scoped).

A zero-marker sweep and a malformed marker (a `verify:` marker not directly
above a fenced block, blank lines allowed) each produce their own gate
`Finding` rather than a silent "0 checked" pass; a repo with malformed
markers but no well-formed ones does not also get a redundant synthetic
"zero markers" finding on top.

`claims/checks/__init__.py` added as the registration point future check
tickets (08–13) will each add one import line to; `claims/cli.py` now
imports it so `claims.cli.main` sees the check registered — the only
change to ticket 06's files this ticket needed.

Tests: `tests/test_executable_claims.py`, ported from `test_verify_docs.py`
(same licensing basis) — true claim, output-mismatch false claim, matching-
text-but-nonzero-exit false claim, malformed marker, zero-marker sweep, a
shell-pipe marker (proving `shell=True` over `shlex.split`), transcript
prompt-line stripping, and one CLI end-to-end test against a fixture repo
with a true/false/malformed marker each. All go through the shared
`run(repo_root, diff_range, config)` seam (registering the check per test
via `RegistryClearingTestCase`) per spec.md's Testing Decisions, rather than
calling `check(...)` directly — `_blocks`/`_dedent`/`_trim` stay untested in
isolation either way. 24 tests total across the suite (`python3 -m
unittest discover -s tests -p 'test_*.py'`), all green.

Post-review (`/code-review` against this ticket): kept the `seen` dedup
guard the Standards pass flagged as defending an "impossible scenario" —
this repo's own `CLAUDE.md` is a tracked symlink to `AGENTS.md`
(confirmed via `git ls-files -s`), so the guard is live, not speculative;
added the one-line comment explaining why so it reads that way. Pulled the
four repeated `Finding(..., mode=NAME, gate=True)` call sites into a
`_finding(file, line, message)` helper (Duplicated Code / Data Clumps).
Switched the direct-`check()`-call tests to go through `run(...)` instead,
matching spec.md's stated seam.
