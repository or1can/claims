# 0018. The reader and the approver are recorded apart

## Status

Accepted. Issue #259; amends
`decisions/0016-an-approval-can-name-its-approver-in-the-entry.md`.

## Context

ADR 0016 had `approve-marks --by` replace an entry's `by`, and rejected
a separate `approved_by` key because a project could already say both in
`by`'s free-form value. That held while the project did its own reading
and so wrote `by` itself. It stops holding once the plugin ships an agent
that does the reading: the reader is then the plugin's agent, named with
its model, and a later session needs that name to tell whether a mark
was read in full, and by what, without reading the section again. A
person approving needs it too, to know the reading happened.

Replacing `by` loses it. In this repository, 43 of the 61 entries in
`claims.checked.toml` had `by` replaced with the approver's name by the
time this was written; who read them is no longer in the file.

## Decision

`by` names the **reader**, and only the reader. Approval names the
approver in a new optional key, `approved_by`, and leaves `by` as it was.

- `approve-marks --by <name>` and `fold-approvals --by <name>` write
  `approved_by = "<name>"` on each entry they approve. Which entries are
  approved is still decided before anything is written, as ADR 0016 says.
- Nothing acts on either key; both are records.
- An existing entry is not migrated. A `by` that ADR 0016's replacement
  wrote stays as it is: it is a true record of what was written, and the
  reader it replaced can't be recovered.

This supersedes ADR 0016's "Replace, don't append" and its rejection of
`approved_by`. The rest of ADR 0016 stands.

## Alternatives considered

- **Append to `by`** (`"<reader>, approved by <name>"`). One key, but a
  value with structure that a tool wanting the reader would have to
  parse.
- **Keep replacing.** The reader is then on record only while a mark is
  pending, which is exactly when it matters least for reuse.

## Consequences

- `claims.checked.toml` gains an optional `approved_by` string key. A
  file without it loads as before.
- `pending-marks` and the `fold-approvals` preview print each mark's
  `by`, so the reader is in view when a person approves.
