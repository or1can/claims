# 0006. A root `claims.toml` opts a repository in to the commit hook

## Status

Accepted. Ticket #118.

## Context

The plugin's `PreToolUse` hook is registered by a Claude Code install,
and that install's settings follow the session, not the repository the
session happens to be committing to. A session started in a project that
installed `claims` keeps the hook when its working directory moves to
another repository, or when it commits elsewhere with `git -C`.

The hook used to decide every such commit as if it belonged to an
installed project. With no `claims.toml`, `load_config` returns `{}`, the
hook's own `[hook] enabled` defaults to true, and every check runs on its
defaults. In a repository that never adopted `claims`, `executable-claims`
then reports that it found no verify markers, which is a gate finding, so
the commit was denied in a repository that had made no decision at all.

The same `cwd`-as-root reading also missed a real configuration: a
session sitting in a subdirectory looked for `claims.toml` there, not at
the root, and swept only that subtree.

## Decision

A repository opts in to the commit hook by having a `claims.toml` at its
root. An empty file is valid and means every check on its defaults. A
commit to a repository with no such file gets `{}`: no check runs and
nothing is reported.

Each `git commit` in a command is decided in the repository it targets:
the top level `git rev-parse --show-toplevel` reports from `cwd` with that
invocation's `-C` paths applied in order. A command committing to more
than one repository is decided per repository and denied if any one
denies it. A target outside a git repository gets `{}`.

The opt-in applies to the hook only. `python3 -m claims.cli` and the
`check-claims` skill are explicit requests, so they keep running anywhere
on defaults, and `load_config` keeps returning `{}` for a missing file.
Whether the file exists is a separate question, `has_config`, that only
the hook asks.

## Alternatives considered

- **Opt in through the plugin's own settings scope.** Rejected: the
  scope is exactly what follows the session rather than the repository,
  which is the defect.
- **Opt out instead, with `[hook] enabled = false`.** Rejected: it needs
  a file in every repository a session might touch, including ones that
  have never heard of `claims`.
- **Soften `executable-claims`' "no verify markers" gate when there is no
  config.** Rejected: that finding is correct for a repository that has
  opted in, and every other check would still run uninvited.

## Consequences

- A consuming project with no `claims.toml` loses its gate on upgrade
  until it adds one. This is a minor version bump, and the changelog
  entry says so first.
- A commit run after a `cd`, or through `--git-dir`/`--work-tree`, is
  still decided in `cwd`'s repository: only `-C` is followed.
