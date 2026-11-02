# 0010. A checked mark expires on its own

## Status

Accepted. Issue #156; builds on
`decisions/0009-stale-claims-is-diff-scoped.md`.

Amended by a risk review before anything was built. In the first version
a sentence mark expired only on its wording, so it could hide a claim
whose code had changed, and a later copy of a marked sentence was
silenced unread. An orphan was a mark matching no current finding, which
under diff-scoped checks is nearly every mark on every commit. The rules
below replace those.

## Context

The advisory checks exist so that a claim gets read. On a real project
they produce hundreds of findings even after the noise fixes (#151–#155),
because every correct "only", "never" or "every" in the tree stays a
match for good. A finding someone has already read looks exactly like
one nobody has, so the read ones bury the rest.

## Decision

Someone can record a **checked mark** against an advisory finding. The
finding stays quiet until something it depends on changes, and then it
comes back without anyone lifting the mark.

- Marks live in a committed sidecar file, `claims.checked.toml`, beside
  `claims.toml`. None go inline in the prose.
- A mark is keyed by file path, mode, and a hash of the sentence's
  normalised words (the normalisation `restatement` uses). It is never
  keyed by line number. Rewrapping keeps the mark; changing one word drops
  it. For `stale-claims` the sentence is the section's heading anchor.
- Every mark records the commit at which it was checked, and how many
  copies of its sentence the file held then. It quiets at most that many,
  so a copy added later is reported until it is marked too.
- A mark expires when its hash no longer matches, or when any subject it
  names has a commit after the recorded one. For a `stale-claims` mark the
  subjects are the section's; for a sentence mark they are the subjects
  the sentence names, resolved the way `stale-claims` resolves them.
  Checking therefore counts as a touch. A sentence that names no subject
  expires only on its wording: its mark covers the wording, not the truth.
  A check's own version never expires a mark.
- `claims mark-checked <file>:<line> <mode> --note "..."` writes one mark
  per call. The note, saying what was verified, is required, and there is
  no bulk form. Editing or removing an entry by hand stays allowed; an
  entry with no note is invalid.
- Marks apply to advisory findings only. Checking a gate finding doesn't
  fix what it reports.
- A mark whose sentence (by hash) or heading (by anchor) no longer exists
  in its file is an orphan, and is reported as an advisory finding. A mark
  that only matches no finding in this run is not, since a diff-scoped
  check reports nothing about a sentence the diff left alone.
- The summary line counts the findings that marks kept quiet, so a quiet
  run is never mistaken for a clean pass.

## Alternatives considered

- **Inline markers** (`<!-- checked -->`). They move with the text, but
  they clutter the prose, and a marker without a hash can't tell that the
  sentence under it changed.
- **A baseline that silences everything present today.** It records
  nothing about whether anyone read a finding, which is the failure this
  decision exists to fix.
- **Expiring a sentence mark by age or commit count.** Any such number is
  arbitrary, and it expires a mark whose claim nothing has touched.
- **`judgment-agent` writing marks from a "confirmed" verdict.** Left out
  for now. A wrong verdict would silence a claim nobody read. A later
  change can add it behind the same command.

## Consequences

- A project commits one more file, and its history shows what was checked
  and when.
- Marks pay off in repeated wide-range audits. An ordinary commit only
  reports what its author just wrote or what its subjects just changed,
  and there is nothing to mark there. Whether that is worth building is
  decided after a re-measurement on or1can/ratect (#156).
- An `exclude` is still the tool for prose that should never be read;
  a mark is for prose that was read.
