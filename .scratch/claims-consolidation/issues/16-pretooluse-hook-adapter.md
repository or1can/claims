# 16 — PreToolUse hook adapter

**What to build:** a Claude Code `PreToolUse` hook matched on
`Bash(git commit *)` that calls the core runner, blocks the commit on a
gate-check failure (`permissionDecision: deny`, with the reason visible to
the agent), and surfaces advisory findings via `additionalContext` without
blocking. A per-project config toggle disables the hook without requiring
the plugin to be uninstalled.

**Blocked by:** 06.

**Status:** resolved

- [x] Given a fixture gate-check failure, the hook's JSON output denies the
      tool call with a human-readable reason.
- [x] Given only advisory findings, the hook's JSON output allows the commit
      and attaches the findings as `additionalContext`.
- [x] Given the config toggle set to disabled, the hook is a no-op
      regardless of what the checks would have found.
- [x] Verified via fixture stdin/stdout JSON matching Claude Code's hook
      contract — no live Claude Code session required.

## Answer

`claims/hook.py` — `decide(repo_root) -> dict` builds the hook-output JSON;
`main(stdin, stdout)` reads the `PreToolUse` payload (`payload["cwd"]`) and
writes it, matching ticket 06's CLI adapter shape. Matching on
`Bash(git commit *)` itself is a plugin-manifest `if`/matcher concern
(ticket 18), not this script's job — confirmed via ticket 01's primary-source
research (`code.claude.com/docs/en/hooks`: the `if` field on a `PreToolUse`
hook entry matches tool *arguments* via permission-rule syntax, e.g.
`"if": "Bash(git commit *)"`), so `hook.py` is a thin caller of `run()` the
same way `cli.py` is, with no command-string parsing of its own.

Decision logic: `claims.toml`'s `[hook]` table's `enabled` key (default
`true`) is checked first — disabled short-circuits to `{}` before `run()` is
even called, satisfying "no-op regardless of what the checks would have
found." Then, mirroring ticket 06's CLI precedent exactly (0-checks-registered
is a failure, never a silent pass; a gate finding denies; an advisory-only
finding allows-with-context): `hookSpecificOutput.permissionDecision: "deny"`
with `permissionDecisionReason` set to every finding (gate *and* advisory,
so denying on one gate finding doesn't hide sibling advisory findings) when
any gate finding is present or the registry is empty; `"allow"` with
`additionalContext` set to every finding when only advisory findings exist;
`{}` otherwise. A malformed `claims.toml` also denies (with the parse error
as the reason) rather than raising past `main()` uncaught, which would leave
no valid JSON on stdout — this is system-boundary validation per this repo's
own working principles, not a scenario the ticket's checklist enumerates.

7 tests in `tests/test_hook.py`, fixture stdin/stdout JSON only — no live
Claude Code session. All 118 project tests green; `pyright` clean.

Post-`/code-review` (round 1, both axes): fixed the hook's zero-checks-
registered path (it fell through to a silent `{}` allow — a real fail-open
the CLI's own "0 checked ≠ clean pass" precedent already guards against) and
folded advisory findings into the deny reason alongside gate findings. Also
extracted the `[GATE|advisory] file:line (mode) message` formatting `cli.py`
and `hook.py` had each written out independently into `Finding.__str__` on
`runner.py`, landed as a separate gardening commit — no behavior change, so
no new red for that part.

Post-`/code-review` (round 2, both axes, run against the full ticket diff
after round 1's fixes): two real findings, both fixed. First,
`main()`'s stdin/`payload["cwd"]` parsing was unguarded while the adjacent
`claims.toml` parsing right next to it was already caught — the same
"crash leaves no valid JSON on stdout" failure mode the `ConfigError`
handling exists to avoid, just not applied symmetrically; now `main()`
catches `json.JSONDecodeError`/`KeyError` and denies with a reason, same as
the config path, with a new test. Second — and more serious — the first
round's feature commit (`23a84a2`, since rewritten as `0d670b8`) was
red in isolation: `hook.py`'s `_summarize` had already been switched to call
`str(f)` in that commit, but `Finding.__str__` wasn't added until the
*next* commit, so checking out the feature commit alone failed 3 of 7
tests — an atomicity bug in how the two commits were split, not a defect in
the shipped `HEAD` state. Fixed by rewriting both (still-unpushed) commits:
the feature commit keeps `hook.py`'s original inline formatting and is
independently green (verified by stashing the gardening files and rerunning
the suite before committing); the gardening commit now carries `hook.py`'s
switch to `str(f)` alongside `Finding.__str__` and `cli.py`'s reuse of it,
where it belongs. The round-1 Answer's "9 tests" claim was also just wrong
(actual count, then and now: 7) — corrected in place rather than compounding
the error with a round-2 caveat.
