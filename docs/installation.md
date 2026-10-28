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
install gives the project the `check-claims` skill, the `judgment-agent`
subagent the skill invokes, and a reminder when the commit gate is not
installed.

The commit gate itself is a git `pre-commit` hook, installed separately as
the [next section](#the-git-pre-commit-hook) describes, so it gates every
commit, not only those Claude Code makes. It gates a commit only in a
repository with a `claims.toml` at its root, and an empty one is enough.
Create it to turn the gate on:

```sh
touch claims.toml
```

Without it the hook does nothing, so a repository that has not adopted
`claims` is not gated.

When a Claude Code session starts in a repository with a root
`claims.toml`, or changes directory into one, and no installed hook there
runs `claims`, the plugin says so: the agent is told the gate is not
active, and a one-line message tells you the same. It counts the hook as
installed when `claims` appears anywhere in `.pre-commit-config.yaml`,
`lefthook.yml`, `lefthook.yaml`, or a file in the repository's git hooks
directory, `core.hooksPath` included. After a change of directory, only
you are told, since Claude Code passes nothing on to the agent at that
point, and each repository is mentioned once per session. The reminder
never blocks anything.

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

Verify with `claude plugin details claims@claims`, which lists the
`check-claims` skill and the plugin's `SessionStart` and `CwdChanged`
hooks. The `judgment-agent` subagent loads as `claims:judgment-agent`,
and the `check-claims` skill invokes it once per candidate.

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

Captured from a throwaway project, both forms run after the
project-scoped install.

## The git `pre-commit` hook

The commit gate is a git `pre-commit` hook, so git runs it on every
commit to the repository, whether Claude Code, a person in a terminal or
any other tool makes it, and in whichever repository the commit lands.
For each commit:

- no root `claims.toml`, or `[hook] enabled = false` in it: nothing runs,
  and the commit goes ahead;
- a check switched off with its own `enabled = false` is left out;
- a gate finding, a `claims.toml` that does not parse, or no check
  registered at all: the findings or the reason are printed, and the
  commit is blocked;
- advisory findings only: they are printed, and the commit goes ahead.

An error inside `claims` itself prints a warning and lets the commit go
ahead, so a broken install does not block every commit.

The hook is a Python package with no third-party dependency, and needs
Python 3.11 or later. Its command is `claims-pre-commit`, which takes no
arguments and runs in the repository git calls it from. Each release is
tagged `v<version>` in this repository, and every setup below pins one.

pre-commit and `uvx` each run the hook in an environment of their own,
put first on `PATH`, and a command granted in `claims.local.toml` runs
with that `PATH` too. `python3` in a granted command is then the hook's
own Python, without the project's dependencies, so a claim about a Python
command's output can fail under the git hook where it passes through the
command line.

### pre-commit

With [pre-commit](https://pre-commit.com), add the hook to the project's
`.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/or1can/claims
    rev: <tag>
    hooks:
      - id: claims
```

Then `pre-commit install`, as for any other hook. pre-commit builds its
own environment for the hook, so nothing else needs installing.

### lefthook, husky, or a plain git hook

The other setups run the command through
[`uvx`](https://docs.astral.sh/uv/guides/tools/), which fetches the tagged
release into a cached environment of its own. With lefthook, in
`lefthook.yml`:

```yaml
pre-commit:
  commands:
    claims:
      run: uvx --from git+https://github.com/or1can/claims@<tag> claims-pre-commit
```

With husky, in `.husky/pre-commit`:

```sh
uvx --from git+https://github.com/or1can/claims@<tag> claims-pre-commit
```

As a plain git hook, in `.git/hooks/pre-commit`, made executable:

```sh
#!/bin/sh
exec uvx --from git+https://github.com/or1can/claims@<tag> claims-pre-commit
```

`pip install git+https://github.com/or1can/claims@<tag>` installs the same
`claims-pre-commit` command, for a setup that calls it from an existing
environment instead.

### Skipping the hook

`git commit --no-verify` skips every git `pre-commit` hook, this one
included. To stop Claude Code from using it, add a deny rule to the
project's `.claude/settings.json`:

```json
{
  "permissions": {
    "deny": ["Bash(git commit *--no-verify*)"]
  }
}
```

The rule matches the flag anywhere after `git commit`. It does not match
the short form `-n`, or a commit made any way other than a plain `git
commit` command, so it stops the obvious route rather than every one.

## The command line

The same checks are also a plain command line, `python3 -m claims.cli`,
for a CI step or a one-off run:

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

The commit hook and the CLI differ in two respects. The hook runs only in
a repository with a root `claims.toml`, and the CLI runs anywhere, with
every check on its defaults where the file is missing. The hook also
honours the switches that take a check, or the gate as a whole, out of the
commit-time decision, and the CLI ignores both, so a check silenced at
commit time is still reported here. Those switches are on
[Configuring `claims`](configuring.md).

The CLI runs from a checkout of this repository, pointed at with
`PYTHONPATH`:

```yaml
# a CI job step, e.g. GitHub Actions
- uses: actions/checkout@v7
  with:
    repository: or1can/claims
    ref: <tag>
    path: claims
- run: PYTHONPATH=claims python3 -m claims.cli --repo-root .
```

**What differs from the full Claude Code experience.** Outside Claude
Code, through either the git hook or the CLI, each mechanical check runs
as it does at commit time, with the same gate and advisory split. What
needs a model to interpret what the mechanical half sets up does not
happen here:

- **`judgment-agent`'s candidates stay candidates.** The check computes
  which claims cite a subject the diff added or removed and reports each
  as an advisory finding. The verdict on each is a separate step, the
  `claims:judgment-agent` subagent, which the `check-claims` skill invokes
  and neither the git hook nor the CLI does. Run this way, the candidate
  lines are printed and left, to read against the cited code yourself; see
  [judgment-agent](checks/judgment-agent.md).
- **The skill's on-demand `claims.toml` review does not run.** Whether a
  project's own configuration is doing anything, a stale `exclude` glob
  matching no file, say, is reasoned prose the `check-claims` skill
  produces on request. It is not a finding, was not part of the CLI's
  output to begin with, and nothing here replaces it.

## `claims.toml`

At the consuming project's repository root, and required for the commit
hook: without it the hook runs no check. An empty file opts in
with each check on its own defaults, so there is nothing more to configure
to get started. The `check-claims` skill and the CLI run with or without it. Each
top-level table is a single check's own configuration section, named for
the check.

A check's own keys are documented with that check. The settings no single
check owns, switching the commit gate off, silencing a check at commit
time, and the git-ignored `claims.local.toml` that governs what a check may
execute, are on [Configuring `claims`](configuring.md).

## Next

[Concepts](concepts.md) defines the vocabulary the rest of the site uses:
gate versus advisory, mode, candidate versus verdict, and what makes a
claim live or dated.
