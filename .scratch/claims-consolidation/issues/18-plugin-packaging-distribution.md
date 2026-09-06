# 18 — Plugin packaging + distribution

**What to build:** package the skill (17), subagent (15), and hook (16) as
one installable Claude Code plugin, distributed as a direct git-URL source
(no marketplace), pinned at install with an explicit update step.

**Blocked by:** 16, 17.

**Status:** ready-for-agent

- [ ] A separate scratch project can register this repo as a plugin source
      via a direct git-URL entry (no marketplace listing) and enable it.
- [ ] Once enabled, both the on-demand skill and the automatic hook are live
      in that scratch project without further manual configuration.
- [ ] The install is pinned to a specific commit/tag, not tracking the
      source's latest state automatically.
- [ ] Every language adapter present at this point ships bundled in the
      single install — nothing fetched separately.
