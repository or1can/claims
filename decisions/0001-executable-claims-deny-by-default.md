# 0001. `executable-claims` denies execution by default, gated on a local grant

## Status

Accepted.

## Context

`executable-claims` runs the command named in any `<!-- verify: -->`
marker it finds, anywhere in the tracked tree, on every invocation — the
automatic `PreToolUse` hook on every `git commit`, the on-demand
`check-claims` skill, and any CI invocation. Until this decision, the only
gate on *which* commands could run was a fixed content blocklist (chaining,
redirection, substitution, `sed`/`awk`/`grep`) plus an optional,
project-configured `permitted_prefixes` list in `claims.toml`.

Both of those are committed config — a PR can change them. So can a
maintainer checking out an untrusted branch for any reason (review, an
unrelated fix, a rebase) end up running a planted command: the branch
carries both a `<!-- verify: -->` marker and, if needed, the
`permitted_prefixes` entry that lets it through, and the automatic hook
fires on the very next unrelated `git commit`, regardless of whether that
commit touches the planted file at all. Filed as ticket #15, discovered
while adopting the plugin in `ratect` — see that ticket for the full
original write-up, including the `verify-docs.py` prior art this check
inherited from, whose own docstring called this exact capability
"deliberately opt-in, and deliberately not in CI yet."

Two directions were on the table: diff-scoping the sweep (so a planted
marker sitting in a file nobody's diff touches wouldn't fire on an
unrelated commit), or a separate opt-out lever for this one check inside
the automatic hook. Neither closes the actual gap: diff-scoping still runs
a planted marker the moment *any* commit touches its file, including one
the maintainer didn't author (e.g. an unrelated formatting pass across the
tree); a hook-level opt-out only protects the automatic-commit surface,
leaving the on-demand skill and any CI invocation exposed to the same
committed-config trust problem.

## Decision

Before `executable-claims` runs any command that already clears the fixed
blocklist and `permitted_prefixes`, it looks the command up by **exact,
verbatim string** in a second, git-ignored, per-machine file,
`claims.local.toml`, under its own `[executable-claims]` section:

- Listed under `denied` → skipped, reported as an advisory (non-gate)
  finding — a deliberately-declined marker stays visible, not silent.
- Listed under `allowed` → runs and is verified exactly as before.
- Listed under neither (the default, including for a command that's new or
  has changed even slightly since it was last granted) → gate finding,
  naming the exact command and the exact TOML to add to resolve it.

This lives inside `executable_claims.check()` itself, not bolted onto the
`PreToolUse` hook — the same function every invocation surface (hook,
skill, CI) calls, so nothing can run a marker's command just by invoking
the check a different way. `permitted_prefixes` and `claims.toml`'s
`exclude` are unchanged in what they do; they still narrow the blocklist,
but no longer substitute for this grant.

`.gitignore` only stops git from ever *adding* a path matching
`claims.local.toml` — it does nothing once that path is already tracked,
so an attacker's PR committing its own `claims.local.toml` alongside a
planted marker would otherwise defeat this entire decision. `check()`
checks the file's tracked status directly against git's index before
trusting anything in it: a tracked `claims.local.toml` has its grants
ignored outright (fail closed, the same as no file existing at all), with
its own gate finding naming the problem so it doesn't fail silently.

The grant key is the command's exact string, not a hash or pattern over
it, and not scoped to the script path it might invoke: simplest to reason
about, and matches how a human actually re-reads a marker before deciding
to trust it — a one-character change is a different decision, not a
variant of a trusted one.

Consequence, not a regression to fix: a fresh CI checkout has no local
file at all, so `executable-claims` stops auto-running there under this
change. Confirmed this project's own CI doesn't invoke the `claims`
checks today.

## Consequences

- A project adopting `executable-claims` for the first time, or any
  existing project the moment this ships, sees every live marker gate
  until a human explicitly grants or denies each one — a one-time,
  per-marker cost, and a real (not cosmetic) minor version bump for
  `claims` itself, since it changes what a consuming project must set up
  to keep its commits passing.
- `SECURITY.md`'s "Scope worth knowing about" points here rather than
  re-explaining the reasoning inline.
- **Update (ticket #19):** the mechanism (grant lookup, the tracked-grant-file
  guard) moved from `executable_claims.py` into `claims/execution_grants.py`
  once `check-cli-flags` became `claims`' second execution-capable check —
  the trigger ticket #15's own original agent brief named for generalizing
  ("extract a shared pattern only when a second one exists," a decision
  deliberately deferred at the time this ADR was written). Behavior is
  unchanged; each check still keys its own grants under its own section
  name in `claims.local.toml`.

## Residual gap (accepted, not solved here)

A granted command string can stay exactly the same while a script it
invokes by path changes independently — granting
`python3 tools/warm-cache.py`<!-- example --> once doesn't re-verify `tools/warm-cache.py`<!-- example -->'s
own contents on every later run. Pinning or hashing the invoked script's
content was considered and deliberately deferred: it's a meaningfully
larger mechanism (content-addressed grants, invalidation on script change)
for a gap that's narrower than the one this ADR closes — the attacker now
needs a trusted command to *already* name a path they can also modify,
rather than merely committing any marker at all.

## Deferred future directions

- An interactive "ask" grant flow for live, interactive Claude Code
  sessions — doesn't map cleanly onto a non-interactive `PreToolUse` hook
  or CI context, so out of scope for this round.
- An opt-in CI mode for security-relevant checks, now that a fresh CI
  checkout has no local grants by default.
- Supply-chain hardening of `claims`' own contribution process (branch
  protection, required review, CODEOWNERS) — not yet needed with one
  maintainer and no external PRs; revisit once either changes.
- A CLI or skill affordance for granting/denying (e.g. `claims allow ...`)
  instead of hand-editing `claims.local.toml` — the gate finding's own
  message is the only "tooling" this round ships.
