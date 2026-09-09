# 24 — Installation instructions

**What to build:** the steps a consuming project follows to actually install
this plugin. Nothing states them today: `claims/skill/SKILL.md` (ticket 17)
is written for *after* install — it assumes `${CLAUDE_PLUGIN_ROOT}` already
resolves — and ticket 18's Answer records that its own two structural
checklist items ("a separate scratch project can register this repo as a
plugin source... once enabled, both skill and hook are live") were verified
structurally (`tests/test_plugin_manifest.py`) but never walked end-to-end
as steps a human follows. Ticket 19 later did walk a live install (a
`claude -p --plugin-dir` session, for its own verification purposes) and hit
a real bug (`plugin.json`'s `agents` field) doing it — evidence this path
had never actually been exercised by a human either, only assumed.

Should cover, concretely, for `ratect`-shaped and other consuming projects:
the git-URL marketplace mechanism ticket 03 decided (no marketplace listing,
pinned at install, explicit update step) — actual commands, not just the
mechanism's name; that the hook is automatic once enabled (fires on
`Bash(git commit *)`, per `claims/hooks.json`) and the skill is on-demand;
the config toggle ticket 03 named for disabling the hook without
uninstalling — confirmed to exist, `claims/hook.py`:
`config.get("hook", {}).get("enabled", True)`, i.e. a `[hook]\nenabled =
false` section in `claims.toml` — document that key by name; and
`claims.toml`'s optional per-check config sections (`claims/config.py`),
stating plainly that an absent file means every check runs with its
defaults.

**Blocked by:** 18.

**Status:** resolved

- [x] A human (or agent) with no prior context can follow the doc alone,
      in a real project, to get the plugin installed and both the skill and
      hook live — verified by actually doing it once, not just written from
      the manifest.
- [x] States the pin-and-explicit-update-step story from ticket 03's
      decision, not just "install it."
- [x] Documents the `[hook] enabled = false` toggle in `claims.toml`
      (`claims/hook.py`) that disables the automatic gate without
      uninstalling the plugin, by its actual key name.
- [x] `claims.toml`'s shape and defaults are documented with at least one
      worked example (e.g. `restatement`'s `extensions` list).

## Answer

Added `docs/installation.md`, linked from README's (ticket 23) previously
dead-ended "Installing" paragraph. Documents `claude plugin marketplace add
<git-url> && claude plugin install claims@claims` (`--scope user` for a
global install) as the actual commands behind ticket 03's decision, `claude
plugin update claims` for the explicit-update half of that same decision,
the `[hook]\nenabled = false` `claims.toml` toggle `claims/hook.py` reads,
and `claims.toml`'s shape (absent file = every check's defaults, one
top-level table per check) with `restatement`'s `extensions` list as the
worked example, per the ticket's own suggestion.

**Verified by actually doing it**, not written from the manifest alone: a
disposable scratch project, `claude plugin marketplace add
/Users/kevin/git/or1can/claims --scope project` (a local path stands in for
the git URL pre-publish — same manifest-driven mechanism, ticket 03's Answer
confirms pinning is the installer's own behaviour, not something either URL
form changes) followed by `claude plugin install claims@claims --scope
project -y`. `claude plugin details claims@claims` confirmed both `Skills
(1) check-claims` and `Hooks (1) PreToolUse` live from that one install,
matching `.claude/settings.json`'s resulting `extraKnownMarketplaces`/
`enabledPlugins` shape exactly as documented. Repeated at `--scope user` to
rule out a project-scope-only effect. A direct call to `claims.hook.decide()`
against the scratch project with `[hook]\nenabled = false` in its
`claims.toml` returned `{}` (no-op), confirming the toggle actually
short-circuits the hook, not just that the key is read. Both the
marketplace and the plugin were removed afterward at both scopes; `git
status`/`~/.claude/settings.json` confirmed the real global config was back
to its pre-test state, and the scratch project deleted — this repo's own
checkout was never touched.

**One tangent, not followed up.** `claude plugin details claims@claims`
reported `Agents (0)` at both scopes, against `plugin.json`'s one declared
agent — looked like a real gap until a nested `claude -p` session in the
same scratch project was asked to list its available subagent types and
`claims:judgment-agent` was there, invokable, matching ticket 19's earlier
finding. `details`' agent count is Claude Code's own CLI, not this repo;
not this repo's bug to carry, and the thing this ticket actually needs
proven — the subagent is live — already was.
