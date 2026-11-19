# 0017. An approval is folded into the commit that wrote the mark

## Status

Accepted. Issue #255; amends
`decisions/0015-an-approval-holds-for-content-not-for-a-commit.md`.

## Context

ADR 0015 lets a project fold an approval into the commit that holds the
marks, and leaves the mechanics to the project. This repository's own
route was to run `approve-marks` at the tip of the branch, commit the
result as a `fixup!` and autosquash it. That approves against the tip,
which is wrong for a branch whose commits each wrote marks: a mark
written in C1, re-marked in C2 and reverted to C1's reading in C3
matches C1 at the tip, and gets approved there without anyone having
read C1.

A rebase that runs `approve-marks <original sha>` after each pick and
amends `claims.checked.toml` into the rewritten commit approves each
commit's own marks against that commit's own tree. Done by hand it is a
recipe of several steps per commit, and a later commit that re-marks an
entry an earlier step approved stops the rebase with a textual conflict
in `claims.checked.toml`.

## Decision

An approval is of a mark **as written in its commit, read against that
commit's tree**. A mark written in C1, re-marked in C2 and re-marked
again in C3 is three approvals, never one inferred from the tip. An
approval is only ever made against a commit the reviewer read, never
against a tree produced while folding.

`claims` gains its first command that rewrites history,
`fold-approvals BASE --approve C ... --by NAME [--apply]`:

- **Opt-in.** Neither the commit hook nor CI runs it.
- **Preview by default.** Without `--apply` it lists each commit's own
  pending marks (`pending-marks --own`) and the `fixup!` commits that
  target it, and changes nothing.
- **Refuses** a dirty working tree, a rebase in progress, a detached
  `HEAD`, a pending entry already at `BASE`, a merge, `squash!` or
  `amend!` commit in the range, a `fixup!` targeting a commit outside
  the range, a range with nothing pending, and a repository attribute
  that would override the fold's merge driver.
- **One rebase.** With `--apply`, one autosquash rebase over
  `BASE..HEAD`. After each named commit and its fixups, it approves
  against the original SHA of that commit, then of each fixup, in order,
  and amends `claims.checked.toml` into the rewritten commit. Only the
  group's own marks are approved: an entry inherited from a commit
  nobody named stays pending.
- **A merge driver for the fold only.** While the rebase runs,
  `claims.checked.toml` merges three-way by entry identity (file, mode,
  unit), and where both sides changed an entry the commit being
  replayed wins. That is right only inside the fold, where the other
  side is the same entry with an approval added. The driver is switched
  on with `-c` options for that one rebase, so ordinary merges and
  rebases never see it.
- **A check afterwards.** The new tip's tree must equal the old tip's,
  except that `claims.checked.toml` may only lose `review = "pending"`
  lines and have `by` lines replaced or added, each in an entry it
  approves. Only the tip is checked, so a difference in an
  intermediate commit that a later commit undoes goes unseen. Anything else resets the
  branch to the old tip and exits non-zero.
- **Never pushes.** It prints the old tip and the
  `git push --force-with-lease=<branch>:<old sha>` to run.

## Alternatives considered

- **A documented recipe.** Every step is one a person or an agent can
  skip or mistype, and the re-mark conflict has no resolution a recipe
  can state safely.
- **Approving at the tip and folding by autosquash.** This repository's
  previous route. It approves trees nobody read.
- **Approving against the rewritten tree.** It compares the file with
  itself and approves everything.
- **A committed `.gitattributes` merge driver.** Every consuming project
  would have to set it up, and it would apply its "replayed commit wins"
  rule to ordinary merges, where it is wrong.

## Consequences

- ADR 0015's "how the approval shows in history is the project's
  choice" still holds; the fold is the route this repository takes, and
  the one `claims` supports with a command.
- Folding rewrites history, so it needs a force-push with a lease, and
  is run where someone can approve the rebase.
- A merge driver for ordinary branch merges stays deferred (`TODO.md`).
