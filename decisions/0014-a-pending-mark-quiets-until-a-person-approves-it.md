# 0014. A pending mark quiets its finding until a person approves it

## Status

Accepted. Issue #245; amends
`decisions/0010-checked-marks-expire-on-their-own.md` and
`decisions/0012-a-ci-run-can-fail-on-unmarked-findings.md`.

Amended by `decisions/0015-an-approval-holds-for-content-not-for-a-commit.md`
(#247): an approval holds for the entry's content, not for the commit
`REV`. A rewrite that leaves approved entries identical needs no
re-approval, and the approval may be folded into the commit holding the
marks rather than being a commit of its own.

## Context

A project where agents write checked marks needs a mark to say whether a
person has reviewed it yet. or1can/ratect did this by convention: an
agent wrote `--by "…, pending review by <maintainer>"`, carried on, and
the maintainer approved later (or1can/ratect#905). Nothing in `claims`
read those words, so ratect kept a script that copied `claims`' private
mark parsing to list pending marks and to rewrite them once approved.
Getting that copy to agree with `claims` took most of a review
(or1can/ratect#917), and any other project wanting the same flow would
have had to copy the same internals.

Approving by re-running `mark-checked` doesn't work: it re-records each
mark's subjects from disk at approval time, so the mark would claim
approval for content the reviewer may never have read.

## Decision

A mark can be **pending**: written without a person's review, recorded
as `review = "pending"` on its `[[mark]]` entry. An entry without the
key is reviewed, so every existing file stays valid, and any other value
makes the file invalid. `review` is independent of `extent`.

- `mark-checked --pending` writes pending marks. A plain `mark-checked`
  over a pending entry replaces it as reviewed: a fresh reading with
  fresh subjects. `claims` doesn't try to tell who ran it.
- A pending mark keeps its finding quiet, and expires, exactly as a
  reviewed one does, so an agent that marks is never blocked waiting for
  a person. The commit hook never blocks on one, `[hook]
  fail_on_unmarked` included, and neither does `--fail-on-unmarked`. The
  summary line counts the findings pending marks keep quiet, and the
  pending marks a range added, so they stay visible.
- `pending-marks [--at REV]` lists every pending entry, expired and
  orphaned ones included, and exits `1` while any exist. It runs no
  checks, so CI can run it as a step of its own.
- `approve-marks REV` approves each entry pending in the working tree
  that was pending, with every other key identical, in the file as
  committed at `REV`: the reviewer read `REV`, so only what is unchanged
  since then is approved. It writes through the same writer as
  `mark-checked` and leaves the commit to the person. A mark reviewed at
  `REV` and pending now stays pending, since what the reviewer saw was a
  different entry.

Mark parsing and writing stay private.

## Alternatives considered

- **A public API for reading and editing marks.** Smaller here, but each
  project would re-implement the approval rule, the part that has to be
  right, and keep its own lifecycle in scripts.
- **A pending mark that doesn't quiet its finding.** Then an agent's
  mark changes nothing until a person approves it, and a project failing
  on unmarked findings blocks every agent's change on a person. The
  separate counts and `pending-marks` give the reviewer what a shown
  finding would, without the block.
- **A flag on the main run that fails on pending marks.** It would run
  every check to answer a question the sidecar alone answers, and tie
  the review state to a diff range it doesn't depend on. A command of
  its own reads one file and can run anywhere, `--at` a commit included.

## Consequences

- An agent that follows the plugin's skill marks with `--pending` unless
  a person says the reading is theirs, so a reviewer finds every mark an
  agent wrote with `pending-marks`.
- A project that runs `pending-marks` in CI can't merge until a person
  has approved, and approving is a commit of its own on the branch.
  ADR 0015 qualifies this: the approval may instead be folded into the
  commit holding the marks.
- Who approved is recorded by git history, not in the file. ADR 0015
  qualifies this: `claims` doesn't record who approved, so that rests on
  the project's own convention, such as a commit message naming them.
