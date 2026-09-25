# 0005. Claims are live or dated; "record-like" is retired

## Status

Accepted. Ticket #77.

## Context

"Record-like" did two incompatible jobs. `docs/concepts.md` and
`CONTEXT.md` defined a record-like file as one whose sentences are
assertions worth holding to account, then named a specification, an
architecture decision record and a changelog as the examples. An ADR and
a changelog are the opposite: they are records precisely because their
sentences are frozen at a date and not meant to be re-verified.

#55 measured the consequence. Over `HEAD~15`, `decisions/*.md` and
`CHANGELOG.md` supplied 77 of 99 `claim-words` findings from a list built
around them, essentially none actionable, and this repo's own
`claims.toml` excludes both. The published `claim-words` page still
recommended exactly those two classes, and its worked example designated
a decision record.

The word's everyday pull is toward "dated", and that pull is what put the
wrong recommendation on the published site.

## Decision

"Record-like" is retired outright, not redefined. Two claim-level terms,
qualifying **Claim** in `CONTEXT.md`, replace it:

- A **live claim** is meant to be re-verified against the tree as it
  stands.
- A **dated claim** was true at its writing and is not meant to be
  re-read against today's tree.

The axis is "is this claim meant to be re-verified against the tree as it
stands?", rather than a live/frozen binary over files, because it also
explains `TODO.md`: its claims are live, and its temporal phrasing is
nonetheless correct.

Both glossary entries carry `_Avoid_: Record-like`, so the tombstone
stays where the next writer reaching for the word will find it.

A **retired quote** is redefined to stand on its own — a sentence quoted
in order to say what was wrong with it, rather than to assert it — and is
anchored to no file class. Tying it to one is what let ADR 0003's premise
drift out from under it.

`files` keeps its mechanics. What changes is what designation is
documented to mean: it approximates a per-claim property at file
granularity, so a file carrying both kinds is designated on which kind
predominates. `claim-words`' recommendation gives that re-verification
test and treats a changelog and a decision record as worked instances
that fail it, rather than as a rule, so a project whose ADRs are
consequence-heavy can reach a different answer for its own tree.

## Alternatives considered

- **Keep "record-like", redefined to mean dated.** Rejected: it inverts
  `claim-words`' entire prose surface, and would make ADR 0003's frozen
  sentence mean the opposite of what it says. A term that reads as
  retired vocabulary is far safer than one that actively misleads.
- **Keep "record-like", redefined to mean live**, fixing only its
  examples. The cheapest option, and rejected: it keeps a word whose
  connotation pulls toward "dated", which is the pull that produced this
  defect once already on the published site.
- **Section-level awareness**, so an ADR's Consequences are swept and its
  motivation is not. Out of scope: the check cannot key on document
  structure. The live/dated vocabulary is named at the claim level
  deliberately, so that work has a term to land under later.
- **File-level glossary entries** rather than claim-level ones. Rejected
  as reproducing this defect's own shape: a file-level term standing in
  for a sentence-level property.

## Consequences

- ADR 0003 is neither superseded nor amended; its decision stands, and a
  reader needs it intact to understand why the two checks' marker sets
  differ. A premise in its Context has stopped describing the world:
  "specs, ADRs, changelogs — the *record-like* files a project opts in
  via `files`" no longer describes `claim-words`' recommended scope, which
  is now the opposite set. Its prose stays frozen; its Status line gains
  a forward pointer here, as metadata, so a reader of 0003 can discover
  that the premise moved.
- That premise was also 0003's justification for `claim-words` honouring
  the blockquote marker, and the argument that took the marker from
  `temporal-words` now points at `claim-words` too. The marker is kept:
  narrowing an existing check's exemptions breaks any project relying on
  it, and one blockquote line across `claim-words`' whole designated set
  in this repo is not a measurement to act on.
- `claim-words`' matching, modes, word lists and severity are unchanged.
  Behaviour is identical before and after this decision.
