# 0007. Git, not command parsing, decides when a commit happens

## Status

Accepted. Issue #128, under #125. Supersedes #122.

Amended by #135, since not every host shows the user a hook's
`systemMessage`: the agent is now also asked to relay the nudge. See the
paragraph under Decision that opens "The user's channel".

## Context

The plugin gated commits through a Claude Code `PreToolUse` hook on
`Bash`. Claude Code hands that hook a command string, not a commit, so the
hook had to decide from the string whether a `git commit` was about to
run, and in which repository. It tokenized the command with `shlex`,
followed `-C`, looked inside `bash -c`, `eval` and git aliases, and relied
on the manifest's `if` filters to skip everything else.

That kept failing, in both directions (#122, #125). Commits it could not
see landed unchecked: an un-spaced `&&`, a `cd` before the commit, a
script, any shell or wrapper it did not know. Widening the filters to
catch more found commits that were not there. And a hook that runs before
the command runs checks a tree `git add` earlier in the same command has
not yet staged.

Git's own `pre-commit` hook has none of these problems. Git runs it once
per commit, in the repository being committed to, after staging, whatever
started the commit. Since #127 `claims` installs as one, making the same
per-repository decision (`claims.gate`).

## Decision

Git decides when a commit happens. The commit gate is the git
`pre-commit` hook, and the plugin registers no `PreToolUse` hook and
parses no command.

What the plugin does instead is say when the gate is missing. Its
`SessionStart`, `CwdChanged` and `UserPromptSubmit` hooks look at the
repository the session is in. When it has a root `claims.toml` but nothing
that looks like an installed hook running `claims`, they say that the gate
is not active and where the installation docs are (`claims.nudge`).

At session start both the agent and the user are told, every time, since
a resume, `/clear` or compaction starts the agent's context over and
whatever it was told earlier is gone. After a change of directory
`CwdChanged` would tell the user at once, but only the user: Claude Code
reads a `CwdChanged` hook's `systemMessage` and discards any context meant
for the agent. And Claude Code does not fire a plugin's `CwdChanged` hook
at all unless a settings file registers one too
(anthropics/claude-code#105625), so `UserPromptSubmit` stands in: at the
next prompt it tells the agent, and the user if `CwdChanged` has not.
Each of them is told about a repository once per session, outside
`SessionStart`, which also forgets what the agent was told about any other
repository. A repository found with its hook installed, or the gate
switched off, counts as told until the next `SessionStart`. So after the
first prompt in a repository, a prompt costs one Python start, one `git
rev-parse` and a read of the record. A commit made in the same turn as
the `cd` lands unchecked; the nudge comes only with the next prompt.

The user's channel, `systemMessage`, is not shown in every host. A
terminal shows it; an SDK-hosted client such as Zed through `claude-acp`
does not, and Claude Code's hook documentation says a `CwdChanged`
`systemMessage` does not reach the SDK message stream. There the agent
would know the gate is off and the user would not. So whenever the agent
is told, it is also asked to tell the user once, briefly, with the
installation link. `systemMessage` stays, as the channel that does not
depend on the agent where it is shown, and the host is not detected:
`CLAUDE_CODE_ENTRYPOINT` is not a documented contract. In a terminal the
user may hear it twice, once from the hook and once from the agent, a
duplicate accepted over a silent miss.

The test for an installed hook is deliberately loose, `claims` anywhere
in a file in the effective hooks directory, or in a hook manager's
configuration (`.pre-commit-config.yaml`, lefthook's under any name it
reads, `.husky/pre-commit`) once that directory holds a `pre-commit`
hook, so it recognises an install in whatever shape a hook manager
writes it. The configuration alone is not enough: committed without the
manager's install step, it is the fresh clone the nudge is for. A
repository that switched the gate off with `[hook] enabled = false` is
not nudged. A nudge in a repository whose hook does run `claims` would
teach its readers to ignore the nudge everywhere, where a stray mention
suppressing one leaves only the silence there was before. The nudge
never blocks anything, and fails open.

## Alternatives considered

- **Keep parsing, narrowed by `if` filters (#122).** Rejected: every
  filter traded missed commits for false positives, and no filter fixes
  checks running before `git add` has staged.
- **Split the command on shell operators with `shlex` first.** Prototyped
  and rejected: it fixes un-spaced operators, but it is still a
  hand-written shell parser with the other gaps above.
- **Inject `core.hooksPath` into the session through `CLAUDE_ENV_FILE`
  (#125's original proposal).** Rejected: pointing git at the plugin's
  hooks directory hides every hook the repository already has, unless the
  plugin chains to the repository's own hook for every hook name git
  defines. That adds a process to every git operation, breaks whenever git
  adds a hook name, and silently bypasses the repository's own hooks if
  the chaining fails. It also leaves commits from Windows PowerShell
  ungated.

## Consequences

- Commits made by hand and in CI are gated too, not only those Claude
  Code makes.
- A fresh clone is not gated until its hook is installed. The nudge
  covers that inside Claude Code; outside it, nothing does.
- `git commit --no-verify` skips the gate. That is an accepted gap, narrowed
  as far as Claude Code goes by a documented `permissions.deny` rule
  rather than by parsing for the flag.
- ADR 0006's opt-in rule stands: only a repository with a root
  `claims.toml` is gated. Its consequence that only `-C` is followed no
  longer applies, since git runs the hook in whichever repository it is
  committing to. A commit through `git -C`, with no change of directory,
  is gated but not nudged.
