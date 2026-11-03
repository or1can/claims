# 0011. Append-only is a property of the file

## Status

Accepted. Issue #187; amends how
`decisions/0009-stale-claims-is-diff-scoped.md`'s churn and
`decisions/0010-checked-marks-expire-on-their-own.md`'s subject hashes
treat such a file.

## Context

A changelog grows on almost every pull request, and two places read that
growth as its content changing. `stale-claims` counts each append as
churn, so a section naming `CHANGELOG.md` as a convention ranks as
heavily moved though nothing it says has changed. And a checked mark
hashes each subject whole, so a mark on such a section expires on the
next PR. On or1can/ratect, 26 of the 43 marks that expired over one
release expired on `CHANGELOG.md` alone.

`historical` already names "an append-only record" for the checks that
take it. But it is per check, and it answers a different question: how a
line *in* the file is judged. Here the question is whether growth of the
file, as something a claim names, counts as change. Checked marks belong
to no one check, and two checks' `historical` lists can legitimately
differ.

## Decision

Append-only is a property of the file, set once for the project:

```toml
[subjects]
append_only = ["RELEASES.md"]
```

`CHANGELOG.md` is append-only built in, and the list adds to it. A bare
string is a one-element list. `[subjects]` is the second top-level table
that names no check, after `[hook]`.

Where an append-only file is a subject:

- **`stale-claims`** doesn't count a commit whose diff for the file removes
  no lines. Such a commit drops out of both the commits since the
  section's last touch and the file's total history. An insertion
  anywhere, including at the top under `[Unreleased]`, is an append. A
  commit that changes or removes a line counts as before, and so does
  cutting a release, which renames a heading.
- **A checked mark** records the file's git blob id. While the current
  content matches, the mark holds. When it differs, the recorded blob is
  read from the object store. If the diff from it to today removes no
  lines, the mark holds; otherwise the mark expires. A blob the store
  doesn't hold, such as one written against uncommitted content in
  another clone, expires the mark.

## Alternatives considered

- **The union of every check's `historical` list.** No new configuration,
  but adding a file to `check-links`' list would silently change
  `stale-claims` rankings and mark expiry. Two checks' lists can rightly
  differ.
- **A `historical` key on `stale-claims`, with marks reading the list of
  the marked finding's check.** A `claim-words` mark naming the changelog
  would still expire, since `claim-words` has no such key.
- **Never letting an append-only file expire a mark.** Simpler, but a
  real edit to a shipped entry would then pass silently.
- **Counting the commits that removed lines.** That ties marks to commit
  history again, which ADR 0010 moved away from because of rebase and
  squash.

## Consequences

- A project lists `CHANGELOG.md` in `historical` and has it append-only
  by default. The two settings say different things about the same file.
- The unrecognized-table gate, configuration review and
  `docs/configuring.md` each learn a second non-check table.
- A mark against an append-only file depends on the object store holding
  the recorded blob. A mark written against committed content almost
  always meets that.
