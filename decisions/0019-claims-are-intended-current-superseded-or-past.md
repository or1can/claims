# 0019. Claims are intended, current, superseded or past

## Status

Accepted. Issue #261; amends
`decisions/0005-live-and-dated-claims.md` and
`decisions/0010-checked-marks-expire-on-their-own.md`.

Amended by `decisions/0020-a-historical-reference-that-moved-is-a-markable-finding.md`
(#264), which replaces the Consequences bullet on `historical` and the
Decision's Scope list of modes. A `historical` reference that held at
its writing is now a markable finding rather than a pass, `restatement`
and `judgment-agent` take no `historical` key, and the reading agent
also reads `check-links-historical` and `check-file-refs-historical`.

## Context

A reader settles a claim by reading it against the tree as it stands. A
claim about a state meant to be, or one that has gone, can't be settled
that way, so the reading agent (#259) returns it `not checked`. A finding
made only of such claims can never be marked: `restatement` and
`claim-words` take no partial mark, so in a `fail_on_unmarked` mode it
blocks `Claims` on any PR that raises it. A finding that mixes them gets a
partial mark that misreports a full reading. Either comes back on every
change to its subjects and is read again to the same result.

Two examples from this repository:

- **Meant to be.** ADR 0005's Decision says the `claim-words` page "gives
  that re-verification test". The ADR was written in `a6de882` and the
  page change came in `df3826e`, later in the same PR (#81), so the claim
  was not true at its writing.
- **Gone.** ADR 0004's Consequences says "two files under `claims/` name
  a moved path", the state before its own move. Its mark is partial, with
  six claims not checked.

ADR 0005's split doesn't separate them. Its **dated claim** "was true at
its writing and is not meant to be re-read against today's tree", which is
false of the first example and leaves no way to read the second.

This is solved when every claim that one tree can settle, and that is not
about the tree as it stands, gets an outcome a mark can record (it holds,
it doesn't, or it is intended and not delivered yet), and the mark comes
back only when something that could change the outcome changes. A claim
no single tree settles stays `not checked`, as it is today: one citing a
commit or an issue, one about a span of history, or one about a
third-party tool's behaviour.

## Decision

A claim is one of four kinds, and the kind names the tree it is read
against.

- An **intended claim** states a decided state as though it holds, and
  is read against the tree as it stands for whether it has been
  delivered. It is never read at its writing, since a decision is
  delivered across a PR, not in the commit that records it.
- A **current claim** says what is, and is read against the tree as it
  stands. Documentation, a to-do entry ("X isn't done yet"), a rule for
  future changes and a conditional claim are current unless evidence says
  otherwise.
- A **superseded claim** was meant to hold and no longer is, superseded
  by a later replacement or by its withdrawal. It is read against the
  tree just before the change that superseded it, the last tree it was
  meant to hold in. A withdrawn claim never delivered reads `false`
  there, which is the honest outcome.
- A **past claim** says what was, as a record, and is read against the
  tree as it was at its writing, or just before it.

A claim typically moves from intended to current, and then to superseded
or past. An intended claim never delivered skips current.

They replace live and dated in `CONTEXT.md`. "Dated" is retired, since it
merged a claim meant to be with one about a state that has gone, and
"live" becomes "current". All four glossary entries carry `_Avoid_:
Record-like`, as live and dated did. "Retired" is not used for a kind: a
**retired quote** is something else.

From ADR 0005 this replaces the live and dated bullets, the sentence
calling `TODO.md`'s claims live, and the sentence on which glossary
entries carry the tombstone. The rest of ADR 0005 stands.

**Inferring the kind.** The reader infers it for each claim. A claim is
current unless the evidence shows otherwise, and the reader cites the
evidence. A doubtful kind is current: a current claim misread as past or
superseded is the costly mistake, since it is read at an old tree, holds
there, and its mark no longer expires with its subjects. That risk is
accepted, guarded by strict evidence and by approval showing each mark's
kind.

- **Intended**: placement in a decision record's Decision, or wording
  that decides ("will", "is decided").
- **Past**: where the claim sits (a shipped changelog entry, a decision
  record's Context or Alternatives), explicit wording ("was", "before
  this change"), or the record's Status calling its section history, as
  ADR 0004's does of its Consequences.
- **Superseded**: the record's Status, or the record it points to, saying
  that this claim, or its section, is replaced or withdrawn. "Amended by"
  alone is not evidence: amendments are mostly partial, so the reader
  reads the amending record for what it replaces, and a claim it doesn't
  name stays current.
- A record's Status, and a record it points to, are the only evidence
  from outside the claim's unit. Explicit evidence beats a default: a
  rule in a section its Status calls history is past.
- A `historical` setting is not evidence, since it means different things
  to different checks.

**Reading each kind.**

- A current claim is read as today.
- An intended claim that holds is delivered, and is current, whether on
  its first reading or a later one. One that doesn't is `false`, with
  kind intended: the reader can't tell "not delivered yet" from
  "delivered and since broken", so the session, which knows the PR's
  plan, decides whether to fix the code (or record a change of direction)
  or to mark it as not delivered, saying so in the note.
- A past or superseded claim is read in a copy of the tree its kind
  names, made by `claims`, so the reading agent never runs git. A claim
  comparing two states, such as "identical before and after", is read
  against both together.
- A past or superseded claim that doesn't hold at its tree goes to the
  session, as an intended one does: a record's prose is not rewritten.

**Marks.**

- A mark records a unit's kind; a mark without one is current.
- A unit takes its least settled kind: current if any claim in it is
  current; else intended if any is intended; else superseded if any is
  superseded; past only when every claim is past. Each claim's own kind
  goes in the note.
- A past or superseded mark expires when its unit's text changes, or the
  evidence its kind rests on, and not when a subject changes: read at a
  tree that doesn't move, nothing else can change the outcome. This
  amends ADR 0010, under which a mark expires when any recorded subject
  changes and when its unit names a subject it didn't record. A unit
  whose claims are partly `not checked` still takes a partial mark.
- When a mark expires, its kind and note go to the reader as context, and
  the kind is inferred afresh. An intended claim that still doesn't hold
  is still undelivered; one that now holds is current. A current claim
  that now reads `false` is a regression, unless the evidence now shows
  it superseded or past, when it is read as that kind.
- Approving pending marks shows each mark's kind.

**Scope.** Kinds apply to the modes the reading agent reads:
`stale-claims`, `spliced-docs`, `claim-words`, `temporal-words` and
`restatement`. `judgment-agent` has its own verdicts and is fed one
cited name at a time; it carries no kind. No check's matching changes: a
check can't tell a claim's kind, for the reason ADR 0005 gave against
section-level awareness. `files` and `historical` stay file-level
settings, and neither declares a kind.

## Alternatives considered

- **Keep live and dated, with intended and past as kinds of dated.**
  Keeps ADR 0005 whole, and a definition, "true at its writing", that is
  false of every intended claim.
- **Three kinds, with superseded claims as past.** Fewer terms, and
  "past" would then name two trees: a superseded decision was intended at
  its writing, so read there it is false.
- **A withdrawn claim settled by its withdrawal**, read against no tree.
  Accepts it on assertion, and leaves one kind that names no tree.
- **Declare the kind per file**, or inline. ADR 0005 rejected file-level
  terms for a sentence-level property, and one decision record carries
  every kind. Inline declarations clutter the prose, as ADR 0010 found for
  marks.
- **Accept intended and past claims on their framing**, with no kind on
  the mark and no older tree: a reading-agent rule alone. The smallest
  change, and a past claim's accuracy at its writing is then never read,
  which ADR 0002 already reads for references. An intended claim accepted
  as intent also hides a regression, since without the previous mark's
  kind nothing tells "not delivered" from "broken".
- **"Amended by" as evidence of a superseded claim.** Eight of the
  eighteen decision records before this one carry one, mostly for a
  partial amendment, so the standing claims of nearly half of them would
  be read as superseded: the costly mistake, made the default.
- **Read an intended claim at the commit that wrote it.** Fails on a
  decision delivered later in its PR.
- **Give the reading agent git.** Widens a tool list kept narrow on
  purpose, where a copy of the tree needs none.
- **A fourth verdict** for "not delivered". Every consumer of a verdict
  would handle a fourth value, where `false` with kind intended already
  says it, and the decision it calls for belongs to the session.

## Consequences

- ADR 0005 stands where it retires "record-like", redefines the retired
  quote and keeps the blockquote marker. ADR 0010 stands except for how a
  past or superseded mark expires. Both keep their prose and gain a
  Status pointer here.
- Under these rules ADR 0005's replaced sentences are superseded by this
  record and hold just before it; its `claim-words` sentence is not
  replaced, and is current and true. ADR 0004's Consequences are past, by
  its Status; those a tree can settle hold at their writing, and those
  citing a commit or an issue stay `not checked` under a partial mark.
- To-do entries, rules and conditional claims default to current. That
  default is provisional, to be revisited if marking real findings turns
  up a counterexample.
- A unit holding a current claim is current, so its mark comes back when
  that claim's subjects change, even where its other claims can't. That
  is the reading the current claim needs.
- A claim reworded as it changes kind becomes a new finding, and its old
  mark an orphan: the re-reading starts afresh, at current, and the move
  between kinds is seen only in the history of `claims.checked.toml`.
- A claim no single tree settles might be read at several and the
  readings combined. That is not the reading agent's job, and is left
  for later.
- `historical` is the file-level stand-in for a past claim's tree in the
  gate checks that can't see a kind, so a current claim in a `historical`
  file, such as a decision's link, still passes if it held at its
  writing. It also means "read only the lines a diff adds" to
  `restatement` and `judgment-agent`. Both are left for later (#264).
- Retired quotes and examples are still not claims, and have no kind.
- The reading agent's verdicts and `judgment-agent`'s line up one to
  one, `true`, `false` and `not checked` against `confirmed`, `refuted`
  and `inconclusive`. Merging them is left for later, in `TODO.md`.
- This record settles the vocabulary, not the mechanism. #261 builds the
  reading agent's and the skill's handling of kinds, the kind on a mark,
  the expiry of past and superseded marks and the approval listing, and
  marks this repository's findings that `not checked` left stuck. It
  settles there, test-first against those findings: how the copy of a
  tree is made and cached; which commit a past claim's writing is and
  which change superseded a claim; what a mark hashes for its unit's text
  and its kind's evidence, and whether word-normalised; how a unit whose
  claims name different trees is read and marked; and what stops a PR
  quieting its own regression by adding a Status note that supersedes
  the claim it breaks.
