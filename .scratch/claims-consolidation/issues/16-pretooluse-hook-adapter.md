# 16 — PreToolUse hook adapter

**What to build:** a Claude Code `PreToolUse` hook matched on
`Bash(git commit *)` that calls the core runner, blocks the commit on a
gate-check failure (`permissionDecision: deny`, with the reason visible to
the agent), and surfaces advisory findings via `additionalContext` without
blocking. A per-project config toggle disables the hook without requiring
the plugin to be uninstalled.

**Blocked by:** 06.

**Status:** ready-for-agent

- [ ] Given a fixture gate-check failure, the hook's JSON output denies the
      tool call with a human-readable reason.
- [ ] Given only advisory findings, the hook's JSON output allows the commit
      and attaches the findings as `additionalContext`.
- [ ] Given the config toggle set to disabled, the hook is a no-op
      regardless of what the checks would have found.
- [ ] Verified via fixture stdin/stdout JSON matching Claude Code's hook
      contract — no live Claude Code session required.
