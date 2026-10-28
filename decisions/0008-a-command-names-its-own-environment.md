# 0008. A command names its own environment

## Status

Accepted. Follows #128.

## Context

`executable-claims` runs a granted command and compares its output with
the block under the marker. Where the command runs depends on how `claims`
was started. From a checkout or a project's own environment, `python3` is
whatever the person's `PATH` gives them. Through pre-commit or `uvx`, the
git hook runs in an environment of its own, put first on `PATH`, so a
bare `python3` is that environment's, with `claims` installed and nothing
else. A claim about a Python script's output can then pass on the command
line and fail under the hook, or the reverse.

Asking which environment a command meant is the same kind of question
ADR 0007 took away from `claims`: whether a command string is a commit.
In both cases the answer belongs to a tool that already knows it.

## Decision

`claims` runs a granted command exactly as written, with the `PATH` it was
started with. A command that needs a particular environment names it:
`uv run -q python …`, `.venv/bin/python …`, `poetry run python …`, or
whatever the project's own tooling provides. Then the claim runs against
the dependencies the project declares, such as its `pyproject.toml` and
lockfile, wherever the check runs.

With `uv run`, `-q` is part of the convention. A hook environment can set
`VIRTUAL_ENV`, and uv then warns on stderr that it is ignoring it in
favour of the project's `.venv`. Stderr is compared with stdout, so the
warning would read as drift.

This repository's own claim follows the rule, and so can run under any
hook setup, pre-commit included.

## Alternatives considered

- **Strip the hook's own environment from `PATH` before running a
  command.** Rejected: `claims` would have to tell its own environment
  apart from the project's, which are the same environment when `claims`
  is installed into the project's venv. That is guessing what a command
  meant from where it runs, the complexity ADR 0007 removed in another
  guise.
- **Recommend only hook setups that leave `PATH` alone**, such as a
  `uv tool install`ed `claims-pre-commit`. Rejected: the version then
  lives on each machine instead of in the repository, and the claim still
  depends on whatever `python3` that machine resolves.

## Consequences

- A claim states its environment, so a reader knows what produced the
  output, not only the check.
- A bare `python3`, `pytest` or `pip` in a granted command is a claim
  about the person's ambient environment. Under a hook it may fail with
  output the person never sees on their own command line.
- pre-commit with a pinned `rev:` works for projects whose commands name
  their environment, which keeps the version in the repository.
- Nothing warns about a bare interpreter yet. An advisory finding for one
  would be a separate change.
