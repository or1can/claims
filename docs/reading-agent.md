# The reading agent

A [checked mark](checked-marks.md) says a finding was read against what it
names and found true. The **reading agent**, `claims:reading-agent`, is the
plugin's subagent for that reading. It takes one markable finding, reads
it in full against every subject it names, and reports a verdict for
each claim in it with the evidence behind each verdict. It never writes a
mark and never edits a file. The session that called it reads its report
and decides what to mark.

It reads findings from every markable mode except `judgment-agent`'s:
`stale-claims`, `spliced-docs`, `claim-words`, `temporal-words` and
`restatement`. A `judgment-agent` candidate goes to its own subagent, as
its [page](checks/judgment-agent.md) describes.

## What it is given

One finding: its `file:line`, its mode and message as the run printed
them, the subjects it names, and its root, the directory holding the
tree the finding was raised in: the project itself, or, for a range
ending at a commit, a `git worktree` the session makes at it. The
finding's **unit** is what it reads first: a `stale-claims` section from
its heading to the next heading, a whole `spliced-docs` doc comment, a
`claim-words` or `temporal-words` sentence, or a `restatement` line. A mark
covers that unit, so the agent reads all of it, never only the cited
line.

For a claim about a state that has gone, the session also gives it the
trees that claim is read at, each a copy of a commit's tracked files
with no `.git` (see [Kinds and trees](#kinds-and-trees)). For a finding
whose mark expired, it gives the mark's kind and note, as context.

## What it reads

The unit, and then every subject it names, each opened in full with the
file-reading tool. A search hit locates a subject; it is not a reading of
it, however short the file. A claim with a totalising word, "every" or
"never", is true only once every site it covers has been read. The agent
has three tools, Read, Glob and Grep, and no shell: nothing it does can
change the working tree, and nothing it can't read settles a claim.

## Kinds and trees

Each claim is one of four [kinds](checked-marks.md#kinds), and the
agent infers which before reading it. The kind names the tree the claim
is read at:

- **Current**, what is, read against the root. Every claim is current
  unless the evidence shows otherwise, and a claim whose kind is in
  doubt is current.
- **Intended**, a decided state, from its place in a decision record's
  Decision or wording that decides ("will"), read against the root for
  whether it has been delivered. One that holds is reported as current.
- **Superseded**, replaced or withdrawn, only when the record's Status,
  or the record it points to, says that this claim or its section is.
  "Amended by" alone is not evidence. It is read just before the change
  that superseded it.
- **Past**, a record of what was, from where it sits (a shipped
  changelog entry, a decision record's Context or Alternatives), its
  wording ("was"), or a Status calling its section history. It is read
  at its writing and just before it.

A `historical` setting is not evidence of a kind. The agent cites the
`file:line` each kind but current rests on.

The agent has no shell, so `claims` makes the old trees:

```sh
python3 -m claims.cli claim-trees --kind past|superseded FILE:LINE
python3 -m claims.cli tree-at REV
```

`claim-trees` prints one tree per line, as `<role> <commit> <root>`. For
a past claim, `FILE:LINE` is the claim's own line, and it prints
`written`, the commit that wrote the line, and `before`, each of that
commit's parents; the claim holds if it held at either. For a superseded
claim, `FILE:LINE` is the line of the Status note, or record, saying the
claim is replaced, and it prints `superseded`, the commit that first
added that line, with no root, and `before`, the trees the claim is read
at. "First added" follows the line back through every later edit to it,
so a note reworded after the change it records still names that change.
A line not yet committed is written in the working tree, printed as
`working-tree` and the project root, and the tree before it is `HEAD`.
`tree-at` prints the root of one commit's copy. Each copy is made once
per commit, inside the repository's git directory, and reused after; its
files are read-only.

The session makes the trees: when the agent reports a past or superseded
claim with no tree to read it at, it names the line to pass to
`claim-trees`, and the session hands it the finding again with the trees
printed.

A claim comparing two states, such as "identical before and after", is
read against both. A unit whose claims are of different kinds is read
claim by claim, each at its own tree.

## What it reports

One JSON object, with:

- each claim in the unit, quoted, with a verdict of `true`, `false` or
  `not checked`, its kind and the `file:line` that kind rests on, the
  tree it was read at, the `file:line` it actually read as evidence, and
  a sentence of reasoning;
- what it read in full, and, apart from that, what it only searched for;
- a draft note for the mark, saying what was verified, naming any
  claim that is false or wasn't checked, and giving each claim's kind and
  tree where any is not current.

`false` covers prose that doesn't finish as well as prose the subject
contradicts: a sentence that trails off says nothing true, whatever its
subject holds. `not checked` is for what reading alone can't settle, such
as a command's output; it names what would settle it. So is a claim no
single tree settles, of whatever kind: one citing a commit or an issue,
or one about a span of history.

An intended claim that doesn't hold is `false`, with kind intended: the
agent can't tell "not delivered yet" from "delivered and since broken",
and leaves that to the session.

## What the session does with it

The `check-claims` skill hands each markable finding to the reading agent
before marking it, and marks only after reading the agent's evidence:

- Every claim `true`: a full mark, with `--by "claims:reading-agent
  (<model>)"`, so the mark names its reader and the model that read it.
- Any claim `false`: no mark. The prose is fixed. An intended claim the
  pull request delivers later may be marked as not delivered, saying so
  in the note; a past or superseded claim false at its tree sits in a
  record whose prose is not rewritten, and the session settles it with
  the user.
- A claim `not checked`, in a `stale-claims` section or a `spliced-docs`
  doc comment: a [partial mark](checked-marks.md#partial-marks), whose
  note names the claim left unchecked, as long as at least one claim is
  `true`. In any other mode, no mark: the session reads that claim's
  subject itself, or leaves the finding unmarked. A full mark always
  means every claim was checked.

A unit is fully marked when every claim holds at its own tree. Its mark
records the unit's kind, the least settled of its claims': current if
any is, else intended, else superseded, and past only when every claim
is past. Each claim's kind goes in the note.

The skill marks with `--pending`, so a person reviews each reading before
it stands, and `pending-marks` prints the `by` of each mark beside it.
Approving records the approver in `approved_by` and leaves `by` as it is
([`decisions/0018-the-reader-and-the-approver-are-recorded-apart.md`](../decisions/0018-the-reader-and-the-approver-are-recorded-apart.md)
says why), so the reader stays on record after approval.

A session that can start no subagent reads the finding itself, to the
same rule, and its marks name the session and its model in `by` instead.
`claims` puts no format on `by`; `<agent name> (<model>)` is the skill's
convention, not something a check enforces.

When a mark expires, because its unit, a subject or its kind's evidence
changed, the finding is read again in full. The mark's kind and note go
to the agent as context, and it infers each kind afresh.

## The model

The agent runs on sonnet. Its golden fixtures, under
`tests/fixtures/reading_agent_golden/`, are five `stale-claims` sections
about one small cache module. Three are a design page's: one true
throughout, one with a sentence left unfinished among true ones, and one
claiming the cache evicts its oldest entry when the code evicts its
newest. Two are a decision record's Decision: one making that same
eviction claim, which has to come back `false` and intended beside a
delivered claim reported current, and one whose Status names one of its
sentences as replaced, which has to come back superseded and `not
checked` with no tree given, beside a current claim. Each fixture passes
only when every claim gets the expected verdict and kind, the agent
opened the section and the module with the file-reading tool, and no
claim comes from outside the section. `python3 scripts/run_reading_agent_golden.py
--model <model>` runs them against the real model, one API call each.

Sonnet passes all five. Haiku, over two runs of the first three,
gives the right verdict on every claim, both false ones included,
but in three of its six fixture runs it also reports the sentence under
the next heading as one of the section's claims, which fails that
fixture. A reader that doesn't keep to the unit can't be trusted on a
mark covering that unit, so sonnet stays the default.

## Next

The check pages follow, gate checks first, and
[executable-claims](checks/executable-claims.md) opens them.
