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

## Using it outside Claude Code

The automatic gate only fires through Claude Code's own `PreToolUse`
hook — a human running `git commit` from a plain terminal, or a CI job,
never triggers it at all; nothing here is a push-time or CI check by
itself (see the top-level `README.md`'s own "What it isn't"). `claims.cli`
is the same underlying runner (`claims/hook.py` and `claims/cli.py` both
just call `claims/runner.py`'s `run()`), so it works equally well as a
plain git pre-commit hook or a CI step — the same exit code (`0`/`1`) a
shell script or CI job already expects.

`claims` isn't pip-installable (`pyproject.toml`'s own `package = false`)
and the Claude Code plugin cache it normally runs from
(`CLAUDE_PLUGIN_ROOT`, set only by Claude Code itself when invoking the
hook — see `claims/hooks.json`) is a per-user, undocumented install
location that won't exist at all on a CI runner. Outside Claude Code, get
a checkout of this repo some other way instead — a pinned clone step in
CI, a git submodule, or a sibling checkout for a local pre-commit hook —
and point `PYTHONPATH` at it directly:

```sh
# .git/hooks/pre-commit (executable)
#!/bin/sh
PYTHONPATH=/path/to/claims python3 -m claims.cli --repo-root .
```

```yaml
# a CI job step, e.g. GitHub Actions
- uses: actions/checkout@v4
  with:
    repository: or1can/claims
    ref: <pinned tag or commit>
    path: claims
- run: PYTHONPATH=claims python3 -m claims.cli --repo-root .
```

**What's different from the full Claude Code experience:** every
mechanical check still runs exactly as it does at commit time — the same
`run()` seam, the same gate/advisory split, the same exit code. Two
things don't, because both need an LLM to actually interpret what the
mechanical half only sets up:

- **`judgment-agent`'s own candidates never become verdicts.**
  `claims/checks/judgment_agent.py` only ever computes the *candidate
  list* — a diff-touched subject with a claim about it — and reports each
  one as an advisory finding; the actual true/false judgment is a
  separate step, the `claims:judgment-agent` subagent, that only the
  `check-claims` skill invokes (`claims/skill/SKILL.md`). Run this way,
  those candidates still show up in the output, but as raw, un-judged
  data points to read yourself — nothing resolves them into an answer.
- **The skill's own on-demand `claims.toml` review doesn't run at all.**
  Whether a project's own config values (a stale `exclude` glob matching
  nothing, say) are actually doing anything is reasoned prose the
  `check-claims` skill produces on explicit ask — not a `Finding`, so it
  was never part of `run()`'s own output to begin with, and nothing here
  replaces it.

## `claims.toml`

Optional, at the consuming project's repo root. No file at all means
`load_config` (`claims/config.py`) returns `{}` and every check runs with
its own defaults, defined in its own module under `claims/checks/` —
nothing to configure to get started. Where present, each top-level table is
one check's own config section, read by that check's name.

A check's own keys are documented with that check. The settings no single
check owns — switching the commit gate off, silencing one check at commit
time, and the git-ignored `claims.local.toml` that governs what a check may
execute — are on [Configuring `claims`](configuring.md).

## Next

[Concepts](concepts.md) defines the vocabulary the rest of the site uses:
gate versus advisory, mode, candidate versus verdict, and what makes a
file record-like.
