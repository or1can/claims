# Installing `claims` in a consuming project

Direct git-URL plugin, no marketplace listing — see
`.scratch/claims-consolidation/issues/03-distribution-mechanism.md`'s Answer
for why. `.claude-plugin/marketplace.json` in this repo is a
self-referencing, single-plugin listing (`"source": "./"`); a consuming
project points `claude`'s marketplace registry straight at this repo's git
URL rather than a central listing.

## Install

From inside the consuming project:

```sh
claude plugin marketplace add https://github.com/or1can/claims.git --scope project
claude plugin install claims@claims --scope project
```

The first command registers this repo as a marketplace named `claims`
(`marketplace.json`'s own `name`); the second installs the one plugin it
lists, also named `claims`, hence `claims@claims`. Both the skill and the
`PreToolUse` hook come live from this one install — nothing else to wire up.

`--scope project` writes both declarations into that project's own
`.claude/settings.json`, so the dependency is explicit and travels with the
repo rather than living only in your machine's global config — the same
thing a second developer cloning the project would need. Both flags default
to `user` (global, this machine only) if omitted; that's a reasonable choice
for a quick personal try, but avoid it if this repo (or any other project on
the same machine) ever registers its own marketplace also named `claims` —
the CLI has no way to alias a marketplace to a different local name than the
one its own `marketplace.json` declares, so a second `claims` source at the
same scope silently replaces the first rather than coexisting. This repo's
own dogfooding setup (a project-scoped `claims` marketplace pointing at
`directory: "."`, not this git URL) hit exactly that collision when a
global-scope entry was added alongside it.

Verify:

```sh
claude plugin details claims@claims
```

```
Component inventory
  Skills (1)  check-claims
  Hooks (1)  PreToolUse  (harness-only — no model context cost)
```

Confirmed by installing into a disposable project this way and checking
`claims:check-claims` and the `PreToolUse` gate were both live — not just
read off the manifest.

**Pinned at install, explicit update.** `claude plugin marketplace add`
resolves and pins the source at add time — an unreviewed upstream change to
this repo doesn't silently start gating a commit differently mid-project.
Pull in a newer version explicitly, when you choose to — same name and
scope as the install commands above, both required:

```sh
claude plugin update claims@claims --scope project
```

`claude plugin update claims` alone fails (`Plugin "claims" not found` —
it defaults to `user` scope, and the plugin above was installed at
`project`); `claude plugin update claims@claims` without `--scope project`
fails the same way (`... is not installed at scope user`). Confirmed by
running all three against a real `--scope project` install — only the
full form above succeeds.

## Disabling the automatic hook

Installing always gets you the on-demand `check-claims` skill; if a project
wants the automatic commit gate off without uninstalling the plugin
entirely, add to that project's `claims.toml`:

```toml
[hook]
enabled = false
```

`claims/hook.py` checks this key (`config.get("hook", {}).get("enabled",
True)`) before running anything — with it `false`, `git commit` is never
gated by this plugin, though the skill still works on demand.

## `claims.toml`

Optional, at the consuming project's repo root. No file at all means
`load_config` (`claims/config.py`) returns `{}` and every check runs with
its own defaults, defined in its own module under `claims/checks/` —
nothing to configure to get started. Where present, each top-level table is
one check's own config section, read by that check's name.

See `docs/configuration.md` for every check's config keys, their defaults,
and when to reach for each one — or that check's own module docstring
under `claims/checks/` directly, if this page and the code ever disagree.
