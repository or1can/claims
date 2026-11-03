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

Amended again after a full read of every advisory finding on or1can/ratect
(#156): 937 read, 889 true, and 94% of the lines printed again on the next
run. Recording a commit SHA broke on rebase and squash, and in that pass
fixes landed after the reading, so they would have expired the marks just
written. One finding per call meant 889 calls, each re-running the checks.
And on `HEAD`, a diff-scoped check reports nothing for a sentence an
audit read. The rules below replace those.

Amended by `decisions/0011-append-only-is-a-property-of-the-file.md`
(#187): a subject the project marks append-only, `CHANGELOG.md` by
default, is compared by git blob id. A mark on it survives an append and
expires on any change or removal of a line.

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
- A mark is keyed by file path, mode, and a hash of the finding's
  **unit**, never by line number. Each markable mode has a defined unit:
  the sentence holding the cited line (`claim-words`, `temporal-words`,
  `judgment-agent`), the heading anchor (`stale-claims`), the surviving
  line plus the retracted run its message quotes (`restatement`), the
  doc-comment run (`spliced-docs`). Text is hashed as normalised words
  (the normalisation `restatement` uses), so rewrapping keeps a mark and
  changing one word drops it. A mode with no defined unit can't be marked.
- Every mark records a content hash of each subject its unit names,
  resolved the way `stale-claims` resolves them, and how many copies of its
  unit the file held. It quiets at most that many, so a copy added later
  is reported until it is marked too.
- A mark expires when its unit's hash no longer matches, when any recorded
  subject's content differs or the file is gone, or when the unit now names
  a subject the mark did not record. No commit is recorded, so rebasing,
  squashing and the order in which fixes land don't matter: a mark is
  valid while what it was read against is byte-identical. A unit that
  names no subject expires only on its wording, so its mark covers the
  wording, not the truth. A check's own version never expires a mark.
- `claims mark-checked` writes marks, looking each finding up in a run
  over the same `--diff-range` a normal run takes (default `HEAD`), so an
  audit marks against its own range. It takes one entry per line from a
  file or stdin, `<file>:<line> <mode> <note>`, and runs the checks once
  per batch. Every entry needs its own note saying what was verified. One
  bad entry fails the whole batch and nothing is written. There is no form
  that marks findings without a note each. `--by "<name>"` optionally
  records who read them; nothing reads that field yet. Editing or removing
  an entry by hand stays allowed; an entry with no note is invalid.
- Whoever reads the finding writes the mark, and that can be an agent. A
  `judgment-agent` verdict never writes one by itself, but the agent that
  asked for the verdict may mark the finding.
- Marks apply to advisory findings only. Checking a gate finding doesn't
  fix what it reports.
- A mark whose unit no longer exists in its file is an orphan, and is reported as an advisory finding. A mark
  that only matches no finding in this run is not, since a diff-scoped
  check reports nothing about a unit the diff left alone.
- The summary line counts the findings that marks kept quiet, so a quiet
  run is never mistaken for a clean pass.

## Alternatives considered

- **Inline markers** (`<!-- checked -->`). They move with the text, but
  they clutter the prose, and a marker without a hash can't tell that the
  sentence under it changed.
- **A baseline that silences everything present today.** It records
  nothing about whether anyone read a finding, which is the failure this
  decision exists to fix.
- **Recording the commit a mark was checked at.** A rebase or squash
  takes that commit out of history, and a fix landing after the reading
  would expire marks on what had just been verified.
- **One finding per call.** A full audit needs hundreds of calls, each
  re-running every check.
- **Expiring a sentence mark by age or commit count.** Any such number is
  arbitrary, and it expires a mark whose claim nothing has touched.
- **`judgment-agent` writing marks from a "confirmed" verdict.** A wrong
  verdict would silence a claim nobody read. On ratect, 52 of 55 verdicts
  were a full subagent run to say "still true", so the cost is already
  spent elsewhere. The agent that asked for the verdict marks instead.

## Consequences

- A project commits one more file, and its history shows what was checked
  and when.
- Marks pay off in repeated wide-range audits, and in the PRs that
  follow one. The or1can/ratect measurement (#156) bears this out. With
  marks, the re-run would have printed about 60 lines instead of 1,123,
  and the PR that applied the audit's fixes about 60 instead of 159, 97
  of which had been read and found true hours before.
- An `exclude` is still the tool for prose that should never be read;
  a mark is for prose that was read.
