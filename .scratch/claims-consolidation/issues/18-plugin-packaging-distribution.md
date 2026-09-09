# 18 — Plugin packaging + distribution

**What to build:** package the skill (17), subagent (15), and hook (16) as
one installable Claude Code plugin, distributed as a direct git-URL source
(no marketplace), pinned at install with an explicit update step.

**Blocked by:** 16, 17.

**Status:** resolved

- [x] A separate scratch project can register this repo as a plugin source
      via a direct git-URL entry (no marketplace listing) and enable it.
- [x] Once enabled, both the on-demand skill and the automatic hook are live
      in that scratch project without further manual configuration.
- [x] The install is pinned to a specific commit/tag, not tracking the
      source's latest state automatically.
- [x] Every language adapter present at this point ships bundled in the
      single install — nothing fetched separately.

## Answer

`.claude-plugin/plugin.json` (component manifest) + `.claude-plugin/marketplace.json`
(self-referencing single-plugin listing, `"source": "./"`) — the exact
structure caveman uses for a git-URL-only install with no central listing
(confirmed by inspecting this environment's own installed `caveman` plugin
cache, matching ticket 03's Answer). `plugin.json` points `skills`/`agents`
at the existing `claims/skill/` and `claims/subagent/` directories (ticket
17, 15's outputs, left in place rather than moved to the default `./skills/`,
`./agents/` root paths — plugin.json's component-path fields exist
specifically to support a non-default layout) and `hooks` at the new
`claims/hooks.json`.

**Wiring the hook's matcher, closing ticket 16's deferral.** Ticket 16's
Answer explicitly left `Bash(git commit *)` matching to "a plugin-manifest
`if`/matcher concern (ticket 18)". Verified the exact field (`code.claude.com/docs/en/hooks`,
fetched directly rather than assumed, since this repo's whole purpose is not
trusting unverified claims): a `PreToolUse` hook entry's `matcher` filters by
tool name only (`"Bash"`); a per-handler `if` field takes one permission-rule
string (`"Bash(git commit *)"`) to filter by the actual command. `claims/hooks.json`
sets both, with the handler command `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m claims.hook`
— `hook.py` already reads stdin/writes stdout with no args (ticket 16), so
this is a thin invocation, not a new adapter.

**Closing the skill's matching gap.** `claims/skill/SKILL.md` (ticket 17)
told the agent to run its command "from the plugin's root directory... wherever
the `claims` package was installed" — true once packaged, but nothing made
that automatic. Changed it to `PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m claims.cli ...`,
runnable from anywhere, using the same `${CLAUDE_PLUGIN_ROOT}` substitution
Claude Code's own plugin-structure documentation confirms is available inside
skill prose, not just hook/MCP JSON.

**Pinning.** Not built here — it's a property of Claude Code's own installer,
confirmed by inspecting this environment's plugin cache directly:
`~/.claude/plugins/cache/caveman/caveman/613d7f0402fb/` is named by the
resolved commit SHA at install time, regardless of whether the marketplace
entry names a ref. Matches ticket 03's Answer; nothing in this plugin's own
manifest needs to encode it.

**Bundling.** Every adapter that exists today (all of `claims/checks/`, the
subagent, the hook) ships from this one repo/plugin; there's no fetch-on-demand
path anywhere in `plugin.json`.

Post-`/code-review` (Spec axis): `claims/hooks.json` was originally shipped
unwrapped (`{"PreToolUse": [...]}` at the top level) — the shape a
`.claude/settings.json` hook block uses, not a plugin's `hooks/hooks.json`.
Caught by the review, confirmed against a real installed plugin rather than
another doc snippet: `~/.claude/plugins/cache/claude-plugins-official/security-guidance/2.0.7/hooks/hooks.json`
(currently enabled in this environment) wraps its events in a top-level
`"hooks"` key, with an optional sibling `"description"`. Fixed to match;
`test_plugin_manifest.py`'s hooks assertion now indexes through
`hooks_file["hooks"]["PreToolUse"]`, so it fails outright if this regresses
to the flat form. The review's other finding — that `plugin.json`'s `skills`
field isn't real, skills being auto-discovery-only — doesn't hold up: this
session is running inside `mattpocock-skills:implement`, discovered via that
exact plugin's `plugin.json` `"skills"` array pointing at a non-default
nested path (`./skills/engineering/implement`), which is live proof the
field is real and honoured.

**Testing.** No live Claude Code session installs a plugin in this run, so the
first two checklist items above are verified structurally, not behaviourally —
that behavioural proof, against a real consuming project (`ratect`), is
ticket 19's job, blocked on this one landing. What's verified here, in
`tests/test_plugin_manifest.py` (6 new tests): both manifests are valid JSON,
name each other consistently, every path `plugin.json` references exists,
the skill/agent directories contain the expected files, and `hooks.json`'s
`matcher`/`if`/`command` are exactly what's claimed above. All 125 project
tests green (`PYTHONPATH=. python3 <file> -v` per file — no `pytest` binary
available in this environment; `conftest.py`'s `sys.path` insert is a
pytest-only mechanism, so direct invocation needs `PYTHONPATH=.` in its
place); `pyright claims tests` clean.

Gardening (separate commit): `tests/test_restatement.py` was missing its
`if __name__ == "__main__": unittest.main()` block — every sibling test file
has one, this one silently ran zero tests when invoked directly as a script
(pytest's own discovery doesn't need the block, so this only bit the
direct-script path exercised above while pytest was unavailable). Added the
missing `unittest` import and entrypoint; its 9 tests now run and pass either
way.
