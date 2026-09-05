Type: research
Status: resolved

## Question

Survey how invocation/auto-trigger of a Claude Code skill+subagent can
actually work across the target ecosystem, so ticket 02 can decide between
them with facts rather than guesses:

- A git hook (pre-commit/pre-push) that shells out and blocks the commit —
  output has to be interpreted by something; is a human reading raw exit
  status/stdout the only option, or can the hook feed findings back into an
  agent turn (e.g. by writing a file the agent reads next turn, or invoking
  the agent directly)?
- Claude Code's own hook events (PreToolUse, PostToolUse, SessionStart, etc.)
  — which of these fire around a `git commit` tool call, and what can they
  pass back into the conversation vs. just allow/block?
- Pure on-demand invocation (slash command / explicit skill call / subagent
  call) — no auto-trigger at all, relies on the agent choosing to run it.

For each mechanism: what triggers it, what it can see (staged diff? working
tree? commit message?), what it can feed back to an agent session, and what a
consuming repo would need to set up once to enable it.

Report with citations (file:line or doc reference) for every claim about what
a mechanism can/can't do — no "should work" without a source checked.

## Answer

Full findings, every claim cited to a primary source (git-scm `githooks(5)`,
Claude Code's hooks/settings docs, a live reproduction of a git hook firing
under an agent's own `Bash` tool call, and this environment's own caveman
plugin as a working `SessionStart`/`UserPromptSubmit` example): commit
`405cd1c` on branch `research/invocation-mechanism-survey`, file
`.scratch/claims-consolidation/issues/01-invocation-mechanism-survey-findings.md`
(`git show research/invocation-mechanism-survey:.scratch/claims-consolidation/issues/01-invocation-mechanism-survey-findings.md`).

Gist: none of the four repos has any hook wired today — genuinely open
ground. All three mechanisms are real, with different feedback shapes: a git
hook's output *does* reach a live agent turn, but only when the agent itself
ran the `git commit`/`git push` (verified live), only as raw stderr+exit
code, and only after a manual per-clone install step (git doesn't version
`.git/hooks/`). A Claude Code hook event (`PreToolUse` matched on
`Bash(git commit *)`, or `PostToolUse` after) reaches the agent natively via
`additionalContext`/`permissionDecisionReason`, with a per-clone-free setup
(commit `.claude/settings.json`, or ship as a plugin — matching how the
locally-installed caveman plugin wires its own hooks). Pure on-demand has no
auto-trigger, cheapest install, richest feedback. None of this forces ticket
02's choice, but "on-demand, agent-invoked to start" (already in map.md) is
compatible with layering either hook mechanism on top later.

**Caveat:** the branch findings file itself names the private source repos
and their absolute local paths verbatim (it was written before the
no-names/no-links decision below). This ticket's Answer above is the scrubbed
summary — safe to keep. The branch is throwaway and must not be merged into
main as-is; if its full detail is ever wanted on main, it needs the same
anonymisation pass prior-art-notes.md and tool-survey.md already got.
