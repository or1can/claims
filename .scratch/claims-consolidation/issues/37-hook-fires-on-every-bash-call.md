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

**Status:** resolved

- [x] The hook does not run at all — not even `load_config`/`run` — for a
      Bash command that isn't `git commit`. Reads
      `payload["tool_input"]["command"]` (or whatever the real event field
      is; confirm against the current hook-event schema rather than
      assuming the field name) and short-circuits before touching the
      runner.
- [x] A regression test drives `hook.main()` (or `decide()`) with a
      non-`git-commit` Bash command and asserts no checks ran — not just
      that the output happens to be `{}`, since a clean pass and "never
      ran" currently look identical from the caller's side.
- [x] `hooks.json`'s `if` key either becomes real (if Claude Code's hook
      schema is confirmed to support command-level filtering some other
      documented way) or is removed in favour of the in-Python check,
      so the manifest doesn't keep asserting a filter the code doesn't
      perform.
- [x] Re-verify the `git commit` case still gates correctly after the
      change — this must not trade "fires on everything" for "fires on
      nothing."

## Answer

**The ticket's own premise was half right, half wrong** — caught only
after the fix was mostly built, by re-verifying against the live primary
source instead of trusting the ticket's "confirmed root cause" at face
value. `hook.py`'s `main()` genuinely never read the invoked command
(true, and the actual bug) — but `if` **is** a real, documented,
currently-supported Claude Code hook field (code.claude.com/docs/en/
hooks), applying identically to plugin-declared hooks, with a worked
example (`"if": "Bash(rm *)"`) nearly identical to what this ticket
removed. What actually explains the observed "fires on everything": the
docs' own Bash-matching table shows a pattern naming *more than the bare
command name* (`Bash(git commit *)`, two words) makes Claude Code run the
hook anyway on any command containing a `$()`/backtick/`$var`
substitution — which agent-authored commands (heredocs, command
substitutions) hit constantly. A single-word pattern (`Bash(git *)`)
doesn't have this failure mode.

**Fix, once this was found: a hybrid, not a full rewrite.** `hooks.json`
keeps `"if": "Bash(git *)"` — coarse, single-word, so Claude Code's own
tested Bash-matching (which correctly handles `&&`/`;`/leading
assignments/`$()` far better than a hand-rolled parser could) filters out
anything with no git command at all. `claims/hook.py`'s `_is_git_commit`/
`_git_subcommand` — the Python-side tokenizer already built and hardened
through five `/code-review` rounds before this was found — does the
finer "is it specifically a commit" narrowing on top, now needed only for
commands the manifest has already confirmed involve `git`.

**What the five review rounds actually hardened, kept regardless of the
`if` discovery:**
1. The ticket's own bug: `main()` reading `payload["cwd"]` only, never
   the command.
2. `_git_subcommand` requires `commit` in git's own subcommand position
   (skipping global options, including their own value token) — not "any
   `commit` token anywhere after `git`", which false-triggers on `git tag
   -m commit`, `git branch commit`, `git log --grep commit`.
3. `_git_subcommand`'s "is `git` the actual invoked program" check —
   dropped after round 4's own finding that it broke multi-line and
   backgrounded (`&`) real commits by requiring segment-position-0, in
   favor of scanning every `git` token in the whole tokenized command.
   Deliberately re-biased toward recall over precision here: a false
   positive (`grep git commit file.txt`) costs one harmless extra check
   run; a false negative lets a commit land completely unchecked — this
   file's whole reason for existing.
4. The global-options-value list (`_VALUE_TAKING_GIT_OPTIONS`) —
   corrected against `git help git`'s real OPTIONS section and verified
   empirically (`--config-env` does take a separate-token value;
   `--exec-path` does not, despite looking like it should).
5. `main()`'s payload parsing hardened against non-string commands,
   `tool_input: null`, and a non-object top-level payload — all crashed
   before, all now deny gracefully.

**Accepted, documented residual gaps** (see `_is_git_commit`'s own
docstring): a compact, no-space operator (`cd /tmp&&git commit`) merges
into an adjacent token and is missed — fixing it needs pre-splitting the
raw command string on operator characters, which needs to respect
quoting to avoid corrupting a legitimate `"a|b"`-shaped argument,
reintroducing the exact parsing hazard `claims/git.py`'s diff-parser
exists to avoid. Idiomatic shell style (this plugin's own commits
included) always spaces these; judged rare enough not to chase further.

Verified: full suite (`python3 -m unittest discover -s tests -p
'test_*.py'`) — 170 passed. `uv run pyright claims tests` — 0 errors, 0
warnings, 0 informations. `claude plugin validate .` — passes (one
pre-existing `author`-missing warning). `/code-review` run six times
across this ticket: five rounds each found one genuine, distinct gap (a
false negative, a false positive class, another false negative, the
`if`-field premise itself, and two payload-parsing crashes), all
addressed above; the sixth found only that this ticket file itself
wasn't yet closed.
