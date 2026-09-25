# 0003. A retirement marker that doubles as ordinary syntax isn't one

## Status

Accepted. Ticket #52. See also 0005.

## Context

`claim-words` established this codebase's house style for retiring a
sentence: a sentence a record-like file quotes to explain what was wrong
with it is exempt from the sweep when it is a Markdown blockquote, wrapped
whole in italics, or opens with the fixed lead-in "Previously said:". Any
one of the three suppresses it; an unmarked quotation still fires, on the
theory that an unmarked quotation is indistinguishable from the claim
still being made.

That style was written for, and only ever exercised against, the file set
`claim-words` sweeps: specs, ADRs, changelogs — the *record-like* files a
project opts in via `files`. In that set a blockquote genuinely does mean
"here is what we used to say".

Ticket #52 adds `temporal-words`, which reuses `claim-words`' sentence
splitting, diff scoping, advisory severity and opt-in `files` key, but
deliberately inverts the file scope. Its whole reason for being a separate
check rather than a fourth `claim-words` mode is that a changelog and
release notes are exactly where temporal wording is *correct*, so they
belong in `claim-words`' scope and must stay out of this one. What is left
is reference prose — the pages describing what a binary does.

In reference prose `>` is a callout. It marks a claim the author wants
read *first*, not one they have retired.

Measured against or1can/ratect at `9316c03^`, the commit before
or1can/ratect#185's present-tense sweep: 62 blockquote lines outside fenced
code across five files, every one a callout asserting current behaviour.
Inheriting the house style whole would have silently dropped two real
findings from that tree — one of the four version-number defects, which
sits in a `> **Status.** From 0.3.0 ...` callout, and a blockquoted `now`
beside three backticked citations.

The general shape: a marker only marks retirement where it means nothing
else. Two of the three do. The blockquote does not, once the file scope
changes.

## Decision

`temporal-words` honours the italics-wrapped and "Previously said:"
markers, and does not honour the blockquote marker.

"The retired-quote exemption" is therefore no longer a single thing this
codebase has one of. It is a per-check set, and each check that has one
states in its own module docstring which markers it honours and why —
the same way each check already documents what it misses.

A check adding its own exemption set decides each marker against its own
`files` scope, not against `claim-words`' precedent. The question is
whether the marker is unambiguous *in the prose that check actually
reads*.

## Alternatives considered

- **Inherit the house style whole**, accepting the dropped findings.
  Rejected on the measurement above: the loss is not a rare edge, it is
  25% of the version-mode defects in the only corpus we have swept.
- **Keep the blockquote marker, but only when the blockquote also carries
  one of the other two.** Preserves a single shared exemption set, at the
  cost of a rule no author would infer from reading a blockquoted
  retirement in a sibling file and copying it. Rejected as more surprising
  than a per-check set that each docstring states outright.
- **Distinguish callout from retirement by heuristic** — a bold lead-in
  (`> **Status.**`), or an opening the rest of the paragraph answers.
  Rejected: this is guessing at authorial intent from typography, and the
  two shapes are not reliably distinguishable. The same reasoning
  `claim-words` already applies to an unmarked quotation applies here.
- **Make the exemption set a `claims.toml` key.** Speculative
  configurability for a single call site, and it would push the judgment
  this ADR records onto every consuming project.

## Consequences

- A genuinely retired sentence quoted as a blockquote in a
  `temporal-words` file now produces a finding. Accepted: the check is
  advisory, so the cost is one finding dismissed, and an author who wants
  it suppressed has two markers that still work.
- The two checks' exemption sets differ, so prose naming "the retired-quote
  exemption" without saying whose is now ambiguous, and each check's
  docstring carries its own set.
- `claim-words` itself is unchanged. This ADR does not narrow an existing
  check's exemptions; it declines to widen a new check's.
