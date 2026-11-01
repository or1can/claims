# 0010. A checked mark expires on its own

## Status

Accepted. Issue #156; builds on
`decisions/0009-stale-claims-is-diff-scoped.md`.

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
  it. For `stale-claims` the sentence is the section's heading anchor, and
  the mark also records the commit at which the section was checked.
- A `stale-claims` mark expires once any of the section's subjects has a
  commit after the recorded one, so checking a section counts as touching
  it. Any other mark expires only when its hash changes. A check's own
  version never expires a mark.
- `claims mark-checked <file>:<line> <mode> [--note "..."]` writes a mark.
  Editing or removing an entry by hand stays allowed.
- Marks apply to advisory findings only. Checking a gate finding doesn't
  fix what it reports.
- A mark that matches no current finding is itself reported, as an
  advisory finding.
- The summary line counts the findings that marks kept quiet, so a quiet
  run is never mistaken for a clean pass.

## Alternatives considered

- **Inline markers** (`<!-- checked -->`). They move with the text, but
  they clutter the prose, and a marker without a hash can't tell that the
  sentence under it changed.
- **A baseline that silences everything present today.** It records
  nothing about whether anyone read a finding, which is the failure this
  decision exists to fix.
- **`judgment-agent` writing marks from a "confirmed" verdict.** Left out
  for now. A wrong verdict would silence a claim nobody read. A later
  change can add it behind the same command.

## Consequences

- A project commits one more file, and its history shows what was checked
  and when.
- An `exclude` is still the tool for prose that should never be read;
  a mark is for prose that was read.
