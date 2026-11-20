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
them, the subjects it names, and the diff range it was raised over. The
finding's **unit** is what it reads first: a `stale-claims` section from
its heading to the next heading, a whole `spliced-docs` doc comment, a
`claim-words` or `temporal-words` sentence, or a `restatement` line. A mark
covers that unit, so the agent reads all of it, never only the cited
line.

## What it reads

The unit, and then every subject it names, each opened in full with the
file-reading tool. A search hit locates a subject; it is not a reading of
it, however short the file. A claim with a totalising word, "every" or
"never", is true only once every site it covers has been read. The agent
has three tools, Read, Glob and Grep, and no shell: nothing it does can
change the working tree, and nothing it can't read settles a claim.

## What it reports

One JSON object, with:

- each claim in the unit, quoted, with a verdict of `true`, `false` or
  `not checked`, the `file:line` it actually read as evidence, and a
  sentence of reasoning;
- what it read in full, and, apart from that, what it only searched for;
- a draft note for the mark, saying what was verified and naming any
  claim that is false or wasn't checked.

`false` covers prose that doesn't finish as well as prose the subject
contradicts: a sentence that trails off says nothing true, whatever its
subject holds. `not checked` is for what reading alone can't settle, such
as a command's output; it names what would settle it. A dated claim, one
true when written and not meant to be re-read against today's tree, such
as a decision record's account of what it changed, is judged against the
state it describes; the agent has no shell to read that state, so such a
claim is usually `not checked`.

## What the session does with it

The `check-claims` skill hands each markable finding to the reading agent
before marking it, and marks only after reading the agent's evidence:

- Every claim `true`: a full mark, with `--by "claims:reading-agent
  (<model>)"`, so the mark names its reader and the model that read it.
- Any claim `false`: no mark. The prose is fixed.
- A claim `not checked`, in a `stale-claims` section or a `spliced-docs`
  doc comment: a [partial mark](checked-marks.md#partial-marks), whose
  note names the claim left unchecked. In any other mode, no mark: the
  session reads that claim's subject itself, or leaves the finding
  unmarked. A full mark always means every claim was checked.

The skill marks with `--pending`, so a person reviews each reading before
it stands, and `pending-marks` prints the `by` of each mark beside it.
Approving records the approver in `approved_by` and leaves `by` as it is
([`decisions/0018-the-reader-and-the-approver-are-recorded-apart.md`](../decisions/0018-the-reader-and-the-approver-are-recorded-apart.md)
says why), so the reader stays on record after approval.

A session that can start no subagent reads the finding itself, to the
same rule, and its marks name the session and its model in `by` instead.
`claims` puts no format on `by`; `<agent name> (<model>)` is the skill's
convention, not something a check enforces.

When a mark expires, because its unit or a subject changed, the finding
is read again in full, as if it had never been marked.

## The model

The agent runs on sonnet. Its golden fixtures, under
`tests/fixtures/reading_agent_golden/`, are three `stale-claims` sections
about one small cache module: one true throughout, one with a sentence
left unfinished among true ones, and one claiming the cache evicts its
oldest entry when the code evicts its newest. Each fixture passes only
when every claim gets the expected verdict, the agent opened the section
and the module with the file-reading tool, and no claim comes from
outside the section. `python3 scripts/run_reading_agent_golden.py
--model <model>` runs them against the real model, one API call each.

Sonnet passes all three on every run. Haiku, over two runs,
gives the right verdict on every claim, both false ones included,
but in three of its six fixture runs it also reports the sentence under
the next heading as one of the section's claims, which fails that
fixture. A reader that doesn't keep to the unit can't be trusted on a
mark covering that unit, so sonnet stays the default.

## Next

The check pages follow, gate checks first, and
[executable-claims](checks/executable-claims.md) opens them.
