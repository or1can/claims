# Installing `claims` in a consuming project

Direct git-URL plugin, no marketplace listing — see
`.scratch/claims-consolidation/issues/03-distribution-mechanism.md`'s Answer
for why. `.claude-plugin/marketplace.json` in this repo is a
self-referencing, single-plugin listing (`"source": "./"`); a consuming
project points `claude`'s marketplace registry straight at this repo's git
URL rather than a central listing.

## Install

From inside the consuming project (or with `--scope user` to make it
available everywhere):

```sh
claude plugin marketplace add https://github.com/or1can/claims.git
claude plugin install claims@claims
```

The first command registers this repo as a marketplace named `claims`
(`marketplace.json`'s own `name`); the second installs the one plugin it
lists, also named `claims`, hence `claims@claims`. Both the skill and the
`PreToolUse` hook come live from this one install — nothing else to wire up:

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
Pull in a newer version explicitly, when you choose to:

```sh
claude plugin update claims
```

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

For example, `restatement` scans a default set of file extensions
(Markdown, Swift, Python, Shell, YAML); a Rust project adding `.rs` to that
set, rather than replacing it, would write:

```toml
[restatement]
extensions = [".rs"]
```

See each check's module docstring under `claims/checks/` for what config
keys, if any, it reads.
