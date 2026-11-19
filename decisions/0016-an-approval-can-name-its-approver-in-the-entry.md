# 0016. An approval can name its approver in the entry

## Status

Accepted. Issue #253; amends
`decisions/0015-an-approval-holds-for-content-not-for-a-commit.md`.

Amended by `decisions/0017-an-approval-is-folded-into-the-commit-that-wrote-the-mark.md`
(#255): this repository folds approvals with `fold-approvals`, which
supersedes the `approve-marks` and `git commit --fixup` route its
Consequences give.

## Context

ADR 0015 left who approved to the project's own convention, and
suggested a line in the folded commit's message naming the approver.
That line has to be written by hand on every fold, it needs `git commit
--fixup=amend:` rather than a plain `--fixup` to survive the squash, and
it sits apart from the entries it vouches for.

Each entry already has a `by` key: an optional string `mark-checked
--by` writes, that no check acts on and that serves only as a record. Nothing
could set it on approval, though. Re-marking with `mark-checked --by`
records the subjects as they are on disk now, which the reviewer may not
have read, and editing `by` by hand means working out again which entries
`approve-marks` approved.

## Decision

`approve-marks REV --by <name>` writes `<name>` as the `by` of every
entry it approves.

- **The content check is unchanged.** Which entries are approved is
  decided on the entries as they are before anything is rewritten, so
  an entry whose `by` differs from its entry at `REV` is still left
  `changed since REV`. The new `by` is written only as part of the approval.
- **Replace, don't append.** `--by` replaces any existing `by` outright,
  and adds one to an entry that had none. `claims` imposes no format on
  the value: a bare name, or `"<reader>, approved by <name>"`, is the
  project's choice.
- **No claim of identity.** As ADR 0015 says, `claims` guarantees
  content only. `--by` records what the person running the command says,
  the same as `mark-checked --by`.
- Entries left pending keep their `by`, and without `--by` the command
  behaves exactly as before.

This supersedes two parts of ADR 0015: its "No code changes", and its
suggestion of a commit-message line naming the approver when an
approval is folded. A folded approval names its approver with `--by`,
so a plain `git commit --fixup=<commit>` and an autosquash rebase carry
it, and `git show <commit>` on the folded commit shows the text, the reading and who vouches
for it together.

## Alternatives considered

- **Keep the commit-message line.** It works only with
  `--fixup=amend:`, is easy to forget, and is dropped by any later
  squash or reword.
- **A new `approved_by` key beside `by`.** It would keep the reader and
  the approver apart, but adds a key to the file format for something a
  project can already say in `by`'s free-form value. ADR 0015 also
  rejected recording an approval in a new key (`approved_at`).

## Consequences

- `approve-marks` gains an optional `--by NAME`; the file format is
  unchanged.
- This repository folds each approval with `approve-marks <commit> --by
  <name>` and a plain `git commit --fixup=<commit> --
  claims.checked.toml`, with no message line naming the approver.
