Blocked by: 01

Type: grilling
Status: resolved

## Question

Given [ticket 01](01-invocation-mechanism-survey.md)'s findings on what each
invocation mechanism can actually do, decide which mechanism(s) the unified
skill/agent supports at launch: on-demand only, hook-triggers-agent,
hook-blocks-commit-with-human-readable-output, or some mix — and whether the
choice differs per consuming repo.

Success criterion carried over from the map's destination: "minimise
code-review failure demand" — the mechanism should catch a stale/unexecuted
claim before it's pushed, not just before it's merged. CI/PR-gate is already
ruled out (see map's Out of scope) because by the time CI runs, the commit has
already happened.

## Answer

Launch mechanism: **on-demand skill/subagent, plus a Claude Code `PreToolUse`
hook matched on `Bash(git commit *)`.** The hook is the earliest catch point
of the three surveyed in ticket 01 and reaches the agent natively
(`permissionDecisionReason`/`additionalContext`), not just a human terminal.
On-demand invocation remains available regardless, as a fallback and for
anyone who wants to run the checks mid-work rather than only at commit time.

Gate vs. advise: **split by check type, not uniform.** A check that already
gates deterministically (executable-claims) blocks the commit
(`permissionDecision: deny`); every candidate-list/advisory check (stale-claims,
echoed-claims/split-claims, claim-words, spliced-docs) surfaces its findings
via `additionalContext` and never blocks — matching this repo's existing
"candidate lists exit 0, deciders need tests" principle
(doc-integrity-tooling.md §5, principle 6; see also prior-art-notes.md §2's
advisory-vs-gate convention) rather than introducing a new rule for this
mechanism specifically.

Per-project variance: **the mechanism is uniform across consuming projects**
— the same `PreToolUse`-hook-plus-on-demand-skill shape ships everywhere;
only the underlying language-specific check scripts vary (the map's existing
"language-agnostic core + adapters" fog item), not the invocation layer. A
project can still choose not to enable the hook at all and stay on-demand-only
— that's a per-project opt-in on top of a uniform offering, not a different
mechanism.

Scope: **commit-time only for launch**, no `git push` checkpoint. Simplicity
first — add a push-time backup only if evidence later shows commits slipping
through uncaught.

Not decided here, deferred to [ticket 03](03-distribution-mechanism.md): how
a consuming project actually gets the `PreToolUse` hook wired (commit a
project `.claude/settings.json` vs. ship as a plugin manifest) — that's a
distribution-mechanism question, not an invocation-mechanism one.
