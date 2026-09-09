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

**Status:** ready-for-agent

- [ ] A human (or agent) with no prior context can follow the doc alone,
      in a real project, to get the plugin installed and both the skill and
      hook live — verified by actually doing it once, not just written from
      the manifest.
- [ ] States the pin-and-explicit-update-step story from ticket 03's
      decision, not just "install it."
- [ ] Documents the `[hook] enabled = false` toggle in `claims.toml`
      (`claims/hook.py`) that disables the automatic gate without
      uninstalling the plugin, by its actual key name.
- [ ] `claims.toml`'s shape and defaults are documented with at least one
      worked example (e.g. `restatement`'s `extensions` list).
