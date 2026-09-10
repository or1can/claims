# 28 — `runner.run()` has no per-check exception isolation

**What to build:** `claims/runner.py`'s `run()` calls every registered
check in a plain loop with no `try`/`except`:

```python
for name, check in _registry.items():
    check_config = config.get(name, {})
    findings.extend(check(repo_root, diff_range, check_config))
```

A check that raises — a malformed check-specific config value, a `git
diff` against an unborn `HEAD`, or any other edge case a check's own
author didn't handle — propagates straight out of `run()` and crashes the
whole CLI invocation, including every gate check that would otherwise
have passed and blocked (or cleared) the commit correctly. This
contradicts an advisory check's "never fails the run" promise at the
runner level, not just within each check's own internal logic (several
checks — see `check_citations.py`'s `_UnusableRepository` handling —
already convert their own edge cases into a gate Finding rather than
raising, precisely to avoid this).

This needs a real specification, not a one-line try/except, because the
reporting shape matters: does a crashed check surface as a gate Finding
(blocking, "this check couldn't run, investigate")? An advisory-only
warning? Does `RunResult` need a new field distinguishing "ran and found
nothing" from "crashed"? Decide this before implementing — see this
repo's own change-loop convention (spec → red → code → green → prose,
`CLAUDE.md`).

**Blocked by:** none.

**Status:** resolved

- [x] State the reporting shape for a crashed check as a one-sentence
      specification before implementing (what `RunResult`/`Finding` looks
      like when one check raises).
- [x] A check that raises no longer crashes `run()` — every other
      registered check still runs and its findings are still reported.
- [x] A regression test registers a deliberately-raising check alongside a
      normal one and asserts the normal check's findings still come back.
- [x] The crashed check's failure is visible in the result somehow — not
      silently swallowed, matching this repo's own "must measure and
      publish what it misses" principle.

## Answer

Spec: a check that raises in `run()` is caught per-check and turned into
one gate `Finding` (`file="."`, `line=0`, `mode=<check name>`) appended to
the result, instead of crashing the whole run — every other registered
check still runs normally.

This reuses the existing gate-finding path unchanged: both `cli.py` and
`hook.py` already gate on `f.gate` across `result.findings`, so a
synthesized crash finding is handled identically to any other gate
finding — no changes needed to either entry point, and no new
`RunResult` field. Matches `check_citations.py`'s own
`_UnusableRepository`-to-gate-finding precedent, generalized from one
check's own known failure mode to any exception from any check.

Added `_crash_finding` and a `try`/`except Exception` around each check
invocation in `claims/runner.py`'s `run()`. `except Exception` (not
`BaseException`) so `SystemExit`/`KeyboardInterrupt` still propagate.

Two regression tests in `tests/test_runner.py`: a raising check
alongside a normal one still returns the normal check's findings; a
raising check on its own produces a gate finding naming it and
containing the exception message.

Verified: full suite (`python3 -m unittest discover -s tests -p
'test_*.py'`) — 134 passed. `uv run pyright claims tests` — 0 errors, 0
warnings, 0 informations. `/code-review` run on the diff — no findings.
