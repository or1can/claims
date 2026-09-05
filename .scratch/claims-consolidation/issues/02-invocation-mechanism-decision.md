Blocked by: 01

Type: grilling
Status: open

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
