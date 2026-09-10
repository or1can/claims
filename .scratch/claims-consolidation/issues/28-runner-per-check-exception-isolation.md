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

**Status:** ready-for-agent

- [ ] State the reporting shape for a crashed check as a one-sentence
      specification before implementing (what `RunResult`/`Finding` looks
      like when one check raises).
- [ ] A check that raises no longer crashes `run()` — every other
      registered check still runs and its findings are still reported.
- [ ] A regression test registers a deliberately-raising check alongside a
      normal one and asserts the normal check's findings still come back.
- [ ] The crashed check's failure is visible in the result somehow — not
      silently swallowed, matching this repo's own "must measure and
      publish what it misses" principle.
