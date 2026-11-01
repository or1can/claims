# 0009. `stale-claims` is diff-scoped

## Status

Accepted. Issue #155.

## Context

`stale-claims` ranked every section of tracked Markdown on every run,
whatever the diff touched. On or1can/ratect that was 183 findings on every
commit. A docs-only change to seven ADR status lines printed the same 183,
which were 178 of its 208 findings. Nothing a commit did, short of editing
the flagged prose, changed that output. So the hook never printed less
than 183 lines, and a new finding from any check landed somewhere inside
them.

A check is a function of `(repo_root, diff_range, config)`. The commit
hook and the CLI both call it with `HEAD`, so a check cannot tell which
of them is running it.

## Decision

`stale-claims` is a diff-scoped check. A section is ranked only when at
least one of its subjects is a file the diff range added, modified,
deleted, or renamed from or to. The score is unchanged, and so is the
order among the sections in scope.

A whole-tree audit is a CLI run over a wide range: a release tag or the
first commit `..HEAD`.

## Alternatives considered

- **Diff-scoped at the hook, whole-tree on demand.** Every check would
  have to be told how it was invoked, a new runner contract for one
  check's sake. It would also make the same range give different
  answers depending on who asked.
- **Keep whole-tree and cap the output** (`top = N`, `min_percent`). That
  shortens the list but still prints the same sections on every commit,
  whatever the commit did. Left in `TODO.md` in case a wide-range audit
  turns out too long to read.

## Consequences

- A section whose subjects nobody touches is never reported again, until
  a range that touches one of them is checked. A stale claim about a
  quiet file sits silent between audits. That is the price of an output
  that tracks the commit.
- `docs/concepts.md`'s "Diff-scoped and whole-tree" section, the
  `stale-claims` page, and anything else that calls the check whole-tree
  have to say otherwise.
- #156's "checked counts as a touch" mark builds on this. Once a section
  is marked checked, it comes back when a subject changes after the
  recorded commit.
