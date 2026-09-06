# 17 — On-demand skill wrapper

**What to build:** an installable Claude Code skill that, when invoked,
enumerates whatever checks are currently registered against the core runner
and runs them against the calling project — the on-demand entry point
alongside the automatic hook from ticket 16.

**Blocked by:** 06.

**Status:** ready-for-agent

- [ ] Invoking the skill against a fixture repo runs every currently
      registered check and reports their findings in one pass.
- [ ] Invoking the skill with zero checks registered reports that honestly
      (matching the core runner's "0 checked" failure semantics) rather
      than a silent pass.
- [ ] The skill grows in coverage automatically as later tickets register
      more checks — no code change required in the skill itself to pick up
      a newly-registered check.
