# Installing `claims` in a consuming project

`claims` is a Claude Code plugin installed straight from this repository's
git URL. There is no central marketplace listing to go through, because the
repository carries its own: a `.claude-plugin/marketplace.json` that names
itself as a marketplace called `claims`, listing a single plugin, also
called `claims`, whose source is the repository root. A consuming project
registers the git URL as a marketplace and installs from it.

## Install

From inside the consuming project:

```sh
claude plugin marketplace add https://github.com/or1can/claims.git --scope project
claude plugin install claims@claims --scope project
```

The first command registers this repository as a marketplace named
`claims`, the name its own listing declares. The second installs the plugin
that listing holds, also named `claims`, hence `claims@claims`. That single
install gives the project the `check-claims` skill, the `PreToolUse` hook
that gates `git commit`, and the `judgment-agent` subagent the skill
invokes.

`--scope project` writes both declarations into the project's own
`.claude/settings.json`, so the dependency is explicit and travels with the
repository, and a second developer cloning it is offered the same install.
Both commands default to `user` scope, this machine's global config, when
the flag is omitted. That is fine for a quick personal try.

Whichever scope is used, the marketplace registry itself is machine-wide
and keyed by name, and the CLI has no way to register a marketplace under
a name its listing does not declare. A later `claude plugin marketplace
add` of a different source also named `claims`, from any project at any
scope, replaces the source for each project on that machine. A checkout of
this repository registered as a directory marketplace for its own
development is the common way to hit that.

Verify with:

```sh
claude plugin details claims@claims
```

```
claims 0.13.2
  Description: Checks documentation and agent-instruction claims against the code they describe.
  Source: claims@claims

Component inventory
  Skills (1)  check-claims
  Agents (0)
  Hooks (1)  PreToolUse  (harness-only — no model context cost)
  MCP servers (0)
  LSP servers (0)

Projected token cost
  Always-on:   ~81 tok   added to every session

Per-component (rounded)
  component     always-on  on-invoke
  check-claims        ~80      ~2.6k

  On-invoke cost is paid each time a skill or agent fires.
  Token counts are estimates and may differ from actual usage.
```

Captured from `claude plugin details claims@claims` in a throwaway
project, as the next command after the install commands above.

The inventory lists the skill and the hook, and counts no agent, though
the plugin manifest declares one. The `judgment-agent` subagent loads all
the same, as `claims:judgment-agent`, and the `check-claims` skill invokes
it once per candidate.

**Pinned at install, explicit update.** The install records the commit it
resolved, and the plugin keeps running that commit until the project
updates it. That is deliberate for a plugin that gates commits: an upstream
change to this repository does not start deciding a project's commits
differently until someone chose to pull it in. To update, name the plugin
and the scope it was installed at, both:

```sh
claude plugin update claims@claims --scope project
```

The shorter forms fail against a project-scoped install, because `update`
defaults to `user` scope:

```
$ claude plugin update claims
Checking for updates for plugin "claims" at user scope…
✘ Failed to update plugin "claims": Plugin "claims" is not installed at scope user
$ claude plugin update claims@claims
Checking for updates for plugin "claims@claims" at user scope…
✘ Failed to update plugin "claims@claims": Plugin "claims" is not installed at scope user
```

Captured from the same throwaway project as the inventory above, both
forms run after the project-scoped install.

## Using it outside Claude Code

The automatic gate fires through Claude Code's own `PreToolUse` hook
alone. A `git commit` run by a person in a plain terminal,
or by a CI job, is not gated by it, and the plugin is not a push-time or
CI check by itself. The same checks are also a plain command line,
`python3 -m claims.cli`, which the hook and the on-demand skill both sit
on top of, so it works as a git pre-commit hook or a CI step:

```sh
python3 -m claims.cli --repo-root <path> --diff-range <range>
```

`--repo-root` defaults to the current directory and `--diff-range` to
`HEAD`, the working tree against the last commit. The command prints each
finding, then a summary line of the form `N checked, M finding(s), G gate
failure(s)`, and exits with:

- `0` when no finding is a gate finding, advisory findings included;
- `1` on a gate finding, or when no check at all is registered, which is
  reported as a failure and not as a clean pass;
- `2` when `claims.toml` exists and does not parse.

The commit hook and the CLI differ in a single respect. The hook honours
the switches that take a check, or the gate as a whole, out of the
commit-time decision, and the CLI ignores both, so a check silenced at
commit time is still reported here. Those switches are on
[Configuring `claims`](configuring.md).

`claims` is not pip-installable: it is a plain package with no build
system, needing Python 3.11+ and no third-party package. Inside Claude Code
it runs from the plugin cache, a per-user location the hook reaches
through the `CLAUDE_PLUGIN_ROOT` variable Claude Code sets, and which does
not exist on a CI runner. Outside Claude Code, get a checkout of this
repository some other way, a pinned clone step in CI, a git submodule or a
sibling checkout for a local pre-commit hook, and point `PYTHONPATH` at
it:

```sh
# .git/hooks/pre-commit (executable)
#!/bin/sh
PYTHONPATH=/path/to/claims python3 -m claims.cli --repo-root .
```

```yaml
# a CI job step, e.g. GitHub Actions
- uses: actions/checkout@v7
  with:
    repository: or1can/claims
    ref: <pinned tag or commit>
    path: claims
- run: PYTHONPATH=claims python3 -m claims.cli --repo-root .
```

**What differs from the full Claude Code experience.** Each mechanical
check runs as it does at commit time: the same gate and advisory split,
the same exit code. What needs a model to interpret what the mechanical
half sets up does not happen here:

- **`judgment-agent`'s candidates stay candidates.** The check computes
  which claims cite a subject the diff added or removed and reports each
  as an advisory finding. The verdict on each is a separate step, the
  `claims:judgment-agent` subagent, which the `check-claims` skill invokes
  and the CLI does not. Run this way, the candidate lines are printed and
  left, to read against the cited code yourself; see
  [judgment-agent](checks/judgment-agent.md).
- **The skill's on-demand `claims.toml` review does not run.** Whether a
  project's own configuration is doing anything, a stale `exclude` glob
  matching no file, say, is reasoned prose the `check-claims` skill
  produces on request. It is not a finding, was not part of the CLI's
  output to begin with, and nothing here replaces it.

## `claims.toml`

Optional, at the consuming project's repository root. No file at all means
each check runs with its own defaults, so there is nothing to configure to
get started. Where present, each top-level table is a single check's own
configuration section, named for the check.

A check's own keys are documented with that check. The settings no single
check owns, switching the commit gate off, silencing a check at commit
time, and the git-ignored `claims.local.toml` that governs what a check may
execute, are on [Configuring `claims`](configuring.md).

## Next

[Concepts](concepts.md) defines the vocabulary the rest of the site uses:
gate versus advisory, mode, candidate versus verdict, and what makes a
claim live or dated.
