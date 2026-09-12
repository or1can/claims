# 37 — `PreToolUse` hook runs the full sweep on every Bash call, not just `git commit`

**What to build:** `claims/hooks.json` registers `"matcher": "Bash"` — every
Bash tool call — and narrows it with an `"if": "Bash(git commit *)"` key on
the individual hook entry. That `if` key is not a real Claude Code hook
schema field; Claude Code's own hook matching only supports the `matcher`
on tool name, nothing that filters by the invoked command's own arguments
before running the hook's command. `claims/hook.py`'s `main()` reads only
`payload["cwd"]` from the `PreToolUse` event JSON — it never reads
`payload["tool_input"]["command"]` or anything else that would let it tell
a `git commit` apart from any other Bash call. So `decide()` — a full
`run(repo_root, "HEAD", config)`, every registered check — executes
unconditionally before *every* Bash tool call in a session with this
plugin enabled, not just before a commit.

This is the same failure class as ticket 35 and ticket 22 elsewhere in
this project's own history: a claim about the mechanism —
`hooks.json`'s own description says *"PreToolUse gate on git
commit"* — that the code does not actually enforce. Confirmed directly,
not assumed: an unrelated Bash command (writing a scratch file, nothing
resembling `git commit`) triggered the full sweep's `additionalContext`
output in a session with the plugin enabled.

**Why this matters beyond wasted cycles.** `executable-claims` re-executes
every marked command in the repo, including a consuming project's slower
markers (a project's real `AGENTS.md` names one that starts a subprocess
server and drives it over stdio). Paying that on *every* Bash call, rather
than once before a commit, means a session doing ordinary work repeatedly
re-runs the project's slowest test as an invisible side effect of tool
calls that have nothing to do with committing — and running several
overlapping full sweeps concurrently (one hook-triggered sweep started
before a manually-run instance of the same slow command had finished) is
a far more plausible source of an intermittent, hard-to-explain failure
in a consuming project's own test than anything in that project's code —
this ticket exists because exactly that shape of flake got chased for a
good while in one before this was found.

**Blocked by:** none.

**Status:** ready-for-agent

- [ ] The hook does not run at all — not even `load_config`/`run` — for a
      Bash command that isn't `git commit`. Reads
      `payload["tool_input"]["command"]` (or whatever the real event field
      is; confirm against the current hook-event schema rather than
      assuming the field name) and short-circuits before touching the
      runner.
- [ ] A regression test drives `hook.main()` (or `decide()`) with a
      non-`git-commit` Bash command and asserts no checks ran — not just
      that the output happens to be `{}`, since a clean pass and "never
      ran" currently look identical from the caller's side.
- [ ] `hooks.json`'s `if` key either becomes real (if Claude Code's hook
      schema is confirmed to support command-level filtering some other
      documented way) or is removed in favour of the in-Python check,
      so the manifest doesn't keep asserting a filter the code doesn't
      perform.
- [ ] Re-verify the `git commit` case still gates correctly after the
      change — this must not trade "fires on everything" for "fires on
      nothing."
