# 17 — On-demand skill wrapper

**What to build:** an installable Claude Code skill that, when invoked,
enumerates whatever checks are currently registered against the core runner
and runs them against the calling project — the on-demand entry point
alongside the automatic hook from ticket 16.

**Blocked by:** 06.

**Status:** resolved

- [x] Invoking the skill against a fixture repo runs every currently
      registered check and reports their findings in one pass.
- [x] Invoking the skill with zero checks registered reports that honestly
      (matching the core runner's "0 checked" failure semantics) rather
      than a silent pass.
- [x] The skill grows in coverage automatically as later tickets register
      more checks — no code change required in the skill itself to pick up
      a newly-registered check.

## Answer

Built as `claims/skill/SKILL.md` — mirroring ticket 15's precedent
(`claims/subagent/judgment_agent.md`, mirroring `claims/checks/`'s layout)
over a root-level `.claude/skills/` or `skills/` path that risks colliding
with ticket 18's eventual plugin layout. Surfaced to the user before
building, taken as recommended.

No new Python code: ticket 06 already built `claims/cli.py` as a thin
caller of `run()` matching this exact shape (repo-root + diff-range in,
every finding printed, "0 checked" reported as a failure, non-zero exit on
a gate finding), so the skill's whole job is to invoke that CLI and report
its output verbatim rather than duplicate its logic — the same "CLI, hook,
skill are all thin callers of one shape, no separate logic duplicated per
entry point" principle ticket 16's hook adapter already follows. All three
checklist items are properties of `claims.cli`, already covered by
`tests/test_cli.py` (`test_zero_checks_registered_fails_never_a_silent_
clean_pass`, and `checks/__init__.py`'s import-time self-registration for
the "grows automatically" item) — this ticket adds no behavior of its own
to test. No red: this ticket changes no runtime behavior, only adds a
skill definition documenting how to invoke behavior that already exists
and is already tested.

Matching `Bash(git commit *)`-style plugin-manifest wiring (how a consuming
project actually discovers and enables this skill) stays ticket 18's job,
same as ticket 16 deferred its own matcher wiring — this ticket only needed
the skill's own content.

119 pre-existing tests still green; `pyright` clean. No files besides the
skill definition and this ticket changed.

Post-`/code-review` (both axes): Standards found one real bug — the
frontmatter `description` originally named each registered check by hand
(`executable-claims, stale-claims, ...`), a list that already omitted
`judgment-agent` (registered since ticket 14, before this diff existed) and
directly contradicted the body's own "this skill never lists which checks
exist" claim just below it. Fixed by dropping the hand-maintained list from
the description entirely, so the body's claim is actually true. Spec found
nothing: all three checklist items map onto `claims.cli`/`checks/__init__.py`
behavior already covered by `tests/test_cli.py`, no ticket-18 territory
touched.
