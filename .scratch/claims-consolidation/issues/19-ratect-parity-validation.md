# 19 — Ratect parity validation (adoption readiness)

**What to build:** run the consolidated executable-claims, stale-claims,
restatement, and spliced-docs checks — the four `ratect` already has as
standalone scripts — against `ratect`'s own repository history, and compare
findings against the four original scripts, with particular attention to
the historical failure instances already documented in this repo's
`doc-integrity-tooling.md` (the never-existed `--cleanup` flag, the "MCP
server" claim, the `docker network inspect` interface-name claim, and
similar). This is the acceptance gate for `ratect` retiring its own four
scripts in favour of this plugin — not a general release gate for every
consuming project.

**Blocked by:** 07, 08, 09, 11, 18.

**Status:** ready-for-agent

- [ ] The consolidated checks, run against `ratect`'s history at the commits
      where each documented historical failure was introduced, catch what
      the original scripts caught.
- [ ] Any finding produced by the original scripts but not reproduced by the
      consolidated checks (or vice versa) is explained explicitly — not left
      as an unremarked difference.
- [ ] The comparison is published as a result (which checks matched, which
      diverged and why) rather than asserted as a bare "it works."
- [ ] `ratect` installing this plugin (via ticket 18's mechanism) and running
      it once against its own current tree produces no unexpected gate
      failures.
