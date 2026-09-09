# 25 — Dogfooding: this repo gates its own commits with its own checks

**What to build:** this repo doesn't currently run its own tool on itself —
no `claims.toml`, no `.claude/settings.json` entry enabling the plugin, no
`PreToolUse` hook wired here. Every check ticket 07–13 built has only ever
been exercised against fixtures and, for ticket 19, `ratect`'s tree — never
against the prose making the claims *in this repo*, which is exactly the
kind of claim-dense repo (`doc-integrity-tooling.md`, `AGENTS.md`, `spec.md`,
22 ticket files) this tool exists for.

Wire the same mechanism ticket 03/18 built for a consuming project, applied
reflexively: this repo installs itself (`.claude-plugin/marketplace.json`
already self-references with `"source": "./"`, per ticket 18's Answer — the
open question is the concrete local-install command/config that makes
*this* repo's own `.claude/settings.json` enable it, which ticket 19's
`--plugin-dir` session-scoped load approximated but didn't make persistent).
Once enabled, the `PreToolUse` hook gates this repo's own commits exactly as
it would `ratect`'s.

Running the full check suite against this repo's own tree for the first time
is very likely to surface real findings — `stale-claims` and `restatement`
in particular, given how much cross-referencing prose this project has
accumulated across `AGENTS.md`, the `.scratch/` tickets, and the checks'
own docstrings. Triaging those findings (fix the claim, or note why a hit is
a legitimate double-appearance) is part of this ticket, not a follow-up —
an advisory finding left unlooked-at is the exact failure mode
`doc-integrity-tooling.md` §1 catalogs.

**Blocked by:** 18.

**Status:** ready-for-agent

- [ ] `.claude/settings.json` (or the correct local mechanism, once ticket
      24 nails down what that is) enables this plugin for this repo itself,
      persistently — not just for one `--plugin-dir` session.
- [ ] A real `git commit` in this repo triggers the `PreToolUse` hook and is
      blocked (or passes) based on this repo's own gate checks —
      demonstrated, not assumed from the manifest.
- [ ] `claims.toml` exists here (even if empty) rather than relying on
      defaults implicitly, so this repo's own config surface is exercised
      too.
- [ ] The first full run's findings are triaged to zero unaddressed gate
      failures — each advisory finding either fixed or has a stated reason
      it's a legitimate hit, not silently ignored.
- [ ] Full test suite and `pyright claims tests` stay clean throughout.
