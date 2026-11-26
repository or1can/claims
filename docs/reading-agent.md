# The reading agent

A [checked mark](checked-marks.md) says a finding was read against what it
names and found true. The **reading agent**, `claims:reading-agent`, is the
plugin's subagent for that reading. It takes a list of markable
findings, reads each in full against every subject it names, and reports
a verdict for each claim in each with the evidence behind each verdict. It never writes a
mark and never edits a file. The session that called it reads its report
and decides what to mark.

It reads findings from every markable mode except `judgment-agent`'s:
`stale-claims`, `spliced-docs`, `claim-words`, `temporal-words`,
`restatement`, `check-links-historical` and `check-file-refs-historical`. A `judgment-agent` candidate goes to its own subagent, as
its [page](checks/judgment-agent.md) describes.

## What it is given

A list of findings, each with its `file:line`, its mode and message as the run printed
them, the subjects it names, and its root, the directory holding the
tree the finding was raised in: the project itself, or, for a range
ending at a commit, a `git worktree` the session makes at it. Every
finding in one list has the same root. The
finding's **unit** is what it reads first: a `stale-claims` section from
its heading to the next heading, a whole `spliced-docs` doc comment, a
`claim-words` or `temporal-words` sentence, a `restatement` line, or the
line holding a demoted `check-links` link or `check-file-refs` path. A mark
covers that unit, so the agent reads all of it, never only the cited
line.

For a claim about a state that has gone, the session also gives it the
trees that claim is read at, each a copy of a commit's tracked files
with no `.git` (see [Kinds and trees](#kinds-and-trees)). For a finding
whose mark expired, it gives the mark's kind and note, as context.

## Reading batches

The findings one commit raises usually name the same files: a change to
a module raises a `stale-claims` finding on every section citing it, and
a reader given one finding at a time opens that module once per finding.
So the session hands the agent a **reading batch**: the findings that
share a subject, transitively, so a finding sharing a subject with any
finding in the reading batch joins it. A finding that shares no subject
with another is a reading batch of one, and unrelated findings are never
packed together to fill a reading batch.

The agent reads each finding in a reading batch as if it were the only
one. Each keeps its own unit, read in full, every subject it names, read
in full, a verdict and a kind for each of its claims, and its own trees.
The one thing a reading batch shares is a reading: a subject read in
full once counts as read for every finding in the reading batch naming
it, at the same tree. The same path at a different tree, such as a past
claim's tree, is read again there.

A reading batch holds at most five findings. The cap is set by the
golden runs of whole reading batches under [The model](#the-model): a
batch of 5 passed the [bar](#the-bar) and a batch of 10 did not. A
reading that is cheaper but sometimes wrong would write marks that hide
false claims, so the cap is only a size that passes. A group larger than
the cap is split, keeping together the findings that share the most
subjects.

The session checks that each reading batch's output holds exactly one
report per finding it sent, matched by the finding's `file:line` and
mode. It ignores a report naming a finding it didn't send, re-sends
alone each finding with no report or two, and marks nothing from that
reading batch until each has one. A finding that needs a tree is
re-sent with its trees, without the rest of its reading batch.

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
per commit, under `.claims/trees/` at the top of the project, and reused
after; its files are read-only. `.claims/` holds a `.gitignore` of its
own, so git never lists it, and a search that honours ignore files never
reads an old tree in place of the project's own.

The session makes the trees: when the agent reports a past or superseded
claim with no tree to read it at, it names the line to pass to
`claim-trees`, and the session hands it the finding again with the trees
printed.

A claim comparing two states, such as "identical before and after", is
read against both. A unit whose claims are of different kinds is read
claim by claim, each at its own tree. A list's lead-in, ending in a
colon, goes with its items: it takes their kind, and is read at their
tree.

## What it reports

A JSON array, one object per finding, each with:

- each claim in the unit, quoted, with a verdict of `true`, `false` or
  `not checked`, its kind and the `file:line` that kind rests on, the
  tree it was read at, the `file:line` it actually read as evidence, and
  a sentence of reasoning;
- what it read in full, and, apart from that, what it only searched for;
- a draft note for the mark, saying what was verified, naming any
  claim that is false or wasn't checked, and giving each claim's kind and
  tree where any is not current.

Every path in it is given from the root, as the finding gives its own,
and never as a bare file name: a file a search of one directory matched
too, and each file in a list. A path in a tree is the same relative path,
beside the tree's role or commit.

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

The `check-claims` skill hands each markable finding to the reading
agent, in its reading batch, before marking it, and marks only after
reading the agent's evidence and comparing it with what the agent lists
as read. The agent sometimes returns `true` from a search alone, so
before marking:

- A finding naming a subject that wasn't opened in full is unsettled. It
  is re-sent alone, and a claim's verdict then replaces its earlier one,
  or the session reads the subject in full itself.
- A `true` claim citing a file not listed as read at the claim's own
  tree, or lines outside what was read of it, is unsettled, even where
  its other cited files were read. The session opens the cited lines
  itself, with enough around them to settle the claim, at that tree.
- A `true` claim whose evidence names no file is unsettled too. The
  session finds what settles it and opens that.
- A claim that something is absent or unused, resting on a search, is
  unsettled whatever else was read. The session searches the tracked
  files itself, such as with `git grep`, opens every hit, and names the
  search in the note.

What the session finds becomes the verdict, and a claim it can't settle
is `not checked`. Where it settled a claim or read a subject itself, the
mark's `by` names it beside the agent. Each finding is then handled by
its verdicts:

- Every claim `true`: a full mark, with `--by "claims:reading-agent
  (<model>)"`, so the mark names its reader and the model that read it.
  A mark read in a reading batch names the same reader: the reading
  batch is how the session handed the work over, not who read it.
- Any claim `false`: no mark. The prose is fixed. An intended claim the
  pull request delivers later may be marked as not delivered, saying so
  in the note; a past or superseded claim false at its tree sits in a
  record whose prose is not rewritten, and the session settles it with
  the user.
- A claim `not checked`: where the agent couldn't reach what settles it,
  it says what it would need. For a tree or a subject it wasn't given,
  the session hands the finding back with it. For a command's output,
  the history or an issue, the session reads or runs that itself. Only a
  claim nobody can settle, such as a past run's output or a judgement,
  stays unchecked. In a `stale-claims` section or a `spliced-docs` doc
  comment that is a [partial mark](checked-marks.md#partial-marks),
  whose note names the claim left unchecked and why, as long as at least
  one claim is `true`. In any other mode, no mark. A full mark always
  means every claim was checked.

A unit is fully marked when every claim holds at its own tree. Its mark
records the unit's kind, the least settled of its claims': current if
any is, else intended, else superseded, and past only when every claim
is past. Each claim's kind goes in the note.

Then the session reports its readings in two lists. A **notable**
reading is one a person should see before approving its mark: a claim
that came back `false`, so the prose was fixed; one nobody could
check, so the mark is partial or absent; a claim whose kind isn't current, read at
an old tree or held as not delivered; a mark written despite a `false`
claim; one that came back with a claim unsettled or a named subject not
opened in full, saying what was then opened; and a verdict the session
overrode, read again or settled itself. Every other reading is
**routine**. The notable ones come first, each with its reason, and go
in the pull request's description, where the person approving sees them.

The skill marks with `--pending`, routine readings included, so a person
reviews each reading before it stands, and `pending-marks` prints the `by` of each mark beside it.
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

The agent runs on sonnet at medium effort, the effort its golden runs
are made at, whatever the calling session's own. Claude Code lets a
`CLAUDE_CODE_EFFORT_LEVEL` set in the environment override it. Its golden fixtures are under
`tests/fixtures/reading_agent_golden/`. Six are `stale-claims` sections
about one small cache module. Three are a design page's: one true
throughout, one with a sentence left unfinished among true ones, and one
claiming the cache evicts its oldest entry when the code evicts its
newest. Three are a decision record's Decision. One makes that same
eviction claim, which has to come back `false` and intended beside a
delivered claim reported current. One has a Status naming one of its
sentences as replaced, which has to come back superseded and `not
checked` with no tree given, beside a current claim. One has a Status
naming a list's bullets as replaced, and the list's lead-in has to come
back superseded with them. A run of one has no problem only when every
claim gets the expected verdict and kind, the agent opened the section
and the module in full with the file-reading tool, and no claim comes
from outside the section.

Four more come in pairs that share a subject and need opposite verdicts,
so a verdict leaking from one finding into the other fails one of them.
One pair is two pages' `Eviction` sections on the same cache module, one
saying it evicts its oldest entry, which holds, and one its newest. The
other is two sentences from one configuration page about one settings
module, a `claim-words` sentence saying every setting has a default,
when one has none, and a `temporal-words` sentence about a default that
holds.

One more fixture is a small root of ten findings that share subjects, as
a reading batch's do. They name one cache module, one settings module, or
both, across design pages, decision records and single sentences. The
first two are a pair like the `Eviction` one above. The third carries
trees for a past claim, and the cache module in one of them evicts its
newest entry where the root's evicts its oldest, so a reader that takes
one for the other fails it. The skill would re-send a finding with trees
apart from the rest; here it stays, so that one path at two trees meets
in one call. A finding fails if it lists another's claim as its own, and
the kind of every claim is judged.

The last is a large root of ten findings that share subjects, and the
kind of every claim in it is judged too. They name a stock ledger of 358
lines, a planner of 213, or both, and the first two are a pair needing
opposite verdicts. Four findings hold a false claim that depends on code
late in one of those files. Others hold a claim settled only by a file
the finding doesn't name: a limit a page gives as 40 lines that the code
sets at 25, or a case size that is right. Two say that nothing uses
something: that nothing calls a method, which is true, and that nothing
reads a field, which another file does.

`python3 scripts/run_reading_agent_golden.py --model <model>` runs each
of the thirty findings alone against the real model, one API call each.
`--only` runs just the fixture or the finding it names, and may be repeated.
`--batch-size`, with 2, 3, 5 or 10, hands that many of the large root's
findings, the first in order, to one call, or of the small root's with
`--root small`. `--stress` hands the ten
findings of the other fixtures to one call, each fixture's files under a
prefix of their own. Those are from eight unrelated roots, which no
reading batch is, so a stress run is recorded and never sets the cap.

Each finding is judged by whether it comes back as it has to alone: one
report per finding, the same verdicts and kinds, its unit and every
subject listed as read and opened to the last line with the file-reading
tool, no claim from outside its unit, and no `true` verdict resting on
lines it didn't open. Every problem in every finding is reported with its class, and a run is
labelled by its worst. The command fails only on a rejecting problem.
`--repeat` runs a mode several times, and the summary counts the failed
runs by class, the failures by finding and type, and the claims listed
per finding. `--output-dir` saves each run's final message, the lines of
each file it opened, its effort and its problems, with the ID of each
model that answered and the Claude Code version, both as the call's own
output names them, and a digest of the contract the call ran with, its
system prompt. `--saved` summarises
runs saved earlier, and makes no call. A run saved without those three is
refused. `--alone` names saved runs of the
same findings alone, and the summary then says whether the size passes
the bar, or why it doesn't.

### The bar

A problem weighs what it would do to a mark.

- **Rejecting.** One in any run rejects the size: a false claim returned
  `true` or not reported; another finding's claim listed; a current or
  intended claim called past or superseded; the unit, a named subject or
  a needed tree not opened, or only partly read. A problem in none of
  these lists, such as missing evidence, is rejecting too.
- **Compared** with its rate alone: a `true` verdict none of whose cited
  files was opened, or citing lines of an opened one that the agent
  didn't read. Evidence naming no file in the root, or lines of one that
  isn't there, can't be judged so. It is reported apart, and counts
  against the reading batch but not in the rate alone.
- **Counted**, only recorded: a sentence from the finding's own page
  outside its unit, a true claim returned `false`, any other error of
  kind, and a finding with no report or two, or a report for none.

A call that returns no message is rejecting, unless a person reads its
cause as from outside the agent, such as a usage limit. Its run is then
discarded and made again.

A size passes with no rejecting problem in at least 60 runs that each
return a report for every finding, and with the compared problem's rate
within a margin of its rate alone. The rate alone is measured on the same
findings, each read alone equally often and at least 60 times in all. The
one-sided 95% upper bound on the batched rate less the rate alone has to
be within the rate alone itself, so a reading batch has it at most twice
as often, or within 5 percentage points where the rate alone is under 5%.
The bound resamples whole calls, since one call's findings share a
context. Resampling a few rare problems bounds them too low, and none at
all at 0, so the bound is never lower than the one for none. There the
batched rate is taken as the highest with a 5% chance of seeing none in
that many calls. Too few runs to bring the bound within the margin is a
size not accepted. The runs of a size, and the runs alone they are
compared with, have to agree in model alias, effort, contract digest,
model ID and Claude Code version: an alias can come to name another
model, the contract can change, and Claude Code can update itself, part
way through them. The summary names each that
differs. A failed call is compared only on what it named, and a size
none of whose runs names a model ID, or none a version, doesn't pass.
The runs of a size also have to be of the large root: none rests on the
small root alone.

### The runs

Each call is isolated: the agent's contract is its whole system prompt,
Read, Glob and Grep are its only tools, it loads no hook, skill, plugin,
MCP server or `CLAUDE.md`, its effort is medium whatever the environment
sets, and its root is outside the repository. A call in a real project
does load that project's `CLAUDE.md`. Leaving it out keeps one run comparable with another.

Run alone and isolated, sonnet passes the twenty findings outside the
large root, one run each, judged without the lines opened or the evidence
cited. Of the large root's ten, run alone once each on Claude Code
2.1.311, nine have no problem. The tenth has a counted one: the decision record's undelivered claim came back
`false`, as it has to, but of kind current rather than intended.

Measured with `claude-sonnet-5-5` on Claude Code 2.1.311, in the isolated
context, a batch of 2 failed on its fifth run, so it was stopped there
and 3, 5 and 10 were not run. On the first finding the agent listed
`Nothing is written to disk.`, from the next section of the same page, as
a claim, while saying in its reasoning that it was outside the unit. The
sentence was not the other finding's, and every verdict in that run was
right. The same finding run alone 20 times had no failed run. One failure
in 5 against none in 20 doesn't show that the batch caused it. By the
[bar](#the-bar)'s classes that failure is counted, and rejects nothing,
but these runs don't count towards it: they are few, of the small root,
and judged without the lines opened or the evidence cited. They left
the cap at one finding.

Counting input, cache and output tokens, a finding in that batch cost
about 8,300, about 7,200 of them cache reads, over the five runs. The
first finding alone averaged 19,100 over its 20 runs, 17,400 of them
cache reads, and ranged from 15,700 to 32,600. The ten findings of the
small root, run alone once each, all passed, at 15,600 to 25,900. The
isolated call starts smaller than one in a real project, so a project
would see a different difference.

The runs the cap rests on were made on 25 and 26 November 2026,
on `claude-sonnet-5-5`, Claude Code 2.1.311 and medium effort, with
Claude Code's auto-update off. No call failed, so none was discarded or
replaced, and every run returned a report for every finding. Each of the
large root's ten findings was first read alone 30 times. None of the
300 had a rejecting problem or an `unopened` one, so the compared rate
alone is 0 for both sizes and each margin is 5 percentage points. In 28
readings the decision record's undelivered claim came back `false`, as
it has to, but current rather than intended, which is counted. Two
readings of the cases finding cited `planner.py` without its `depot/`
prefix, evidence naming no file, which is reported apart.

The readings alone were made with `python3
scripts/run_reading_agent_golden.py --only shared_subject_large --repeat
30 --output-dir <alone>`. Each batched run was a call of its own, `python3
scripts/run_reading_agent_golden.py --batch-size 5 --output-dir <run>`,
into a new directory each time, stopping at the first run with a
rejecting problem, on which the harness exits 1. Size 10 was run the same
way, with `--batch-size 10`.

A batch of 5, the first five findings, passed in 60 runs.
Captured from `python3 scripts/run_reading_agent_golden.py --saved <run>
... --alone <alone>`, over the 60 runs of `--batch-size 5`, each saved
to a directory of its own, and the 300 runs alone:

```
failed runs of 60: 0 rejecting, 9 compared, 0 counted
    9 x shared_subject_large/04-audit.finding.txt: unresolved (compared)
compared problem: batched 0.030, alone 0.000, upper bound on the difference 0.049, margin 0.050
passes the bar
```

A batch of all ten had no rejecting problem in 60 runs, but wasn't
accepted. Captured the same way, over the 60 runs of `--batch-size 10`:

```
failed runs of 60: 0 rejecting, 24 compared, 1 counted
    24 x shared_subject_large/04-audit.finding.txt: unresolved (compared)
    1 x shared_subject_large/06-hold-length.finding.txt: kind (counted)
compared problem: batched 0.040, alone 0.000, upper bound on the difference 0.052, margin 0.050
doesn't pass the bar: the bound 0.052 on the compared problem's difference is over its margin 0.050
```

So the cap is 5. Every compared problem in both sizes was the same one,
in a finding that had none in its 30 readings alone: the claim that
nothing in `depot` calls `rebuild` came back `true` on a search and a
list of files read. Its evidence cited `ledger.py:240` without the
`depot/` prefix in 27 of the 33, and no line at all in the rest. The
cases finding's two readings alone were the same slip. A batch of 5
passed the bound by 0.001. The decision record's undelivered claim, current rather than
intended in 28 of 30 readings alone, came back intended in all 60
batches of 10; the one counted problem there is its other, delivered
claim called intended.

The bound is the larger of two: the resampled bound, and the one for no
problem at all in that many calls. Over 60 calls the second is 0.049,
whatever the batch, so a margin of 0.05 leaves a size at 60 runs almost
no room. A batch of 5's resampled bound was 0.047, so its bound is the
one for none; a batch of 10's was 0.052. Over 120 calls the bound for
none would be 0.025, and over 200, 0.015.

The same five findings did worse in the batch of 10. Their compared rate
was 0.080 there, all of it the audit finding, against 0.030 in the batch
of 5. Their claims listed per finding were 2.20 in the batch of 5, 2.18
in the batch of 10 and 2.20 alone; over all ten, 1.79 in the batch of 10
against 1.80 alone. The first two findings sometimes listed their two
sentences as one claim in the batch of 10:

| Finding | Batch of 5 | Batch of 10 | Alone |
| --- | --- | --- | --- |
| 01-holds | 2.00 | 1.92 | 2.00 |
| 02-support | 2.00 | 1.97 | 2.00 |
| 03-planning | 3.00 | 3.00 | 3.00 |
| 04-audit | 2.02 | 2.00 | 2.00 |
| 05-privacy | 2.00 | 2.00 | 2.00 |
| 06-hold-length | | 2.00 | 2.00 |
| 07-stock-totalising | | 1.00 | 1.00 |
| 08-stock-temporal | | 1.00 | 1.00 |
| 09-cases | | 2.00 | 2.00 |
| 10-planner-totalising | | 1.00 | 1.00 |

Why the audit finding's slip grows with the batch is a hypothesis, read
from these saved runs with no new call. Its place in the batch doesn't
separate the readings that slipped from those that didn't: it is the
fourth finding in every batch and its report the fourth in every array,
and the readings that slipped made as many `Read` calls before opening
its unit as those that didn't, 3.0 against 3.0 on average in the batch of
5 and 4.5 against 4.6 in the batch of 10. Where its search for `rebuild`
looked does more. Alone, 28 of its 30 readings searched the whole root,
and 27 cited the match from the root, with its `depot/` prefix. Batched, the search was of
`depot/` in 32 of the 60 batches of 5 and 45 of the 60 batches of 10, and
the evidence named that directory as the search's and then the match
from it: 31 of the 33 slips name `ledger.py` without its directory, and
the other two name `depot/` and its files without theirs. In the batch of
10, 21 of the 45 readings that searched `depot/` slipped, against 3 of
the 15 that searched the root; in the batch of 5 it was 6 of 32 against 3
of 18, so the search's place is not the whole of it. No other claim's
evidence in any batch named a file without its directory. So the slip is
the form an absence claim's evidence takes when it rests on a search,
most often a search of one directory, written from that directory rather
than the root. The contract says every path the agent writes is given
from the root, a match from a search of one directory included, and it
is that form the harness judges, not where the agent searched.

A batch's tokens are its call's, so they are counted per finding as the
call's total over its findings, against the same findings alone, which
ranged from about 19,200 to 69,500 each:

| | Tokens per finding | Of them cache reads |
| --- | --- | --- |
| Batch of 5 | 13,789 | 10,825 |
| Its five findings alone | 43,344 | 35,392 |
| Batch of 10 | 6,970 | 5,209 |
| Its ten findings alone | 36,202 | 29,273 |

Tokens count input, cache-creation, cache-read and output. The batches
are of one root's findings in one order, in an isolated call, so a
project's saving would differ.

Size 10 was measured again under the contract that gives every path from
the root, with the counts, chunks and pins fixed in ADR 0021's Status
before the first run. The runs were made on 26 November 2026, from
the merge commit that tightened the contract, on `claude-sonnet-5-5`, Claude Code 2.1.311 and
medium effort, with auto-update off, and all 800 saved the same contract
digest. No call failed, so none was discarded or replaced. Each of the
large root's ten findings was read alone 60 times, as a chunk of its own,
with `python3 scripts/run_reading_agent_golden.py --only <finding>
--repeat 60 --output-dir <alone>/<finding>`. Size 10 was then run 200
times with `--batch-size 10 --repeat <n> --output-dir <chunk>`, in three
chunks of 20, 20 and 160 rather than the ten of 20 the Status names: the
last was left running unattended, with the usage window judged to have
room for it. The count is the one fixed in advance. Captured from
`python3 scripts/run_reading_agent_golden.py --saved <chunk> ... --alone
<alone>/<finding> ...`, over the three chunks and the ten findings'
readings alone:

```
failed runs of 200: 0 rejecting, 4 compared, 9 counted
    3 x shared_subject_large/01-holds.finding.txt: unit-own-page (counted)
    1 x shared_subject_large/02-support.finding.txt: unit-own-page (counted)
    4 x shared_subject_large/04-audit.finding.txt: unresolved (compared)
    6 x shared_subject_large/06-hold-length.finding.txt: kind (counted)
evidence naming no file: 4 readings
claims listed per finding: 1.78, alone 1.80
compared problem: batched 0.002, alone 0.000, upper bound on the difference 0.015, margin 0.050
doesn't pass the bar: the findings were not each read alone as often
```

So the cap stays at 5. Every run returned a report for every finding,
none had a rejecting problem, and the bound is well within its margin,
but the bar asks for the findings each read alone equally often, and
they weren't. One of the privacy finding's 60 readings alone returned
no array: its final message began "Still checking the privacy claim",
said a verdict was coming, and then gave that finding's report as a bare
object, its verdicts right. That is a counted `matching` problem, and a
run with no report is no reading, so the privacy finding was read 59
times and the other nine 60. Captured from `python3
scripts/run_reading_agent_golden.py --saved <alone>/<finding> ...` over
the ten:

```
failed runs of 600: 0 rejecting, 0 compared, 51 counted
    1 x shared_subject_large/05-privacy.finding.txt: matching (counted)
    50 x shared_subject_large/06-hold-length.finding.txt: kind (counted)
claims listed per finding: 1.80
```

The bare object is the far end of a slip that is common. The contract
asks for one array and nothing else in the final message, and the
harness takes an array behind a code fence or a line of prose too. Of
the 600 replies alone, 515 were the array alone, 75 fenced it, 9 put
prose before it and 1 gave a bare object. Of the 200 batches of 10, 152
were the array alone, 43 fenced it and 5 put prose before it.

The tightened contract did what the hypothesis above said it would. The
audit finding's absence claim slipped in 4 of 200 batches of 10, against
24 of 60 before, and none of the 4 named a file without its directory:
each cited only the search, as `depot/ (grep for rebuild)` or a search
for `\.rebuild\(` found no match, with no file or line. No reading alone
slipped, the cases finding's included. Of the counted problems, the
decision record's undelivered claim came back current rather than
intended in 47 of its 60 readings alone and in no batch, and its other,
delivered claim came back intended in 3 readings alone and 6 batches.
The holds finding listed a sentence from the next section, true and said
to be outside the unit, in 3 batches, and the support finding one in 1.
Claims listed per finding were the same alone and batched for every
finding except holds, at 1.86 batched against 2.00 alone, and support,
at 1.99 against 2.00.

A finding in a batch of 10 cost 7,110 tokens, 5,329 of them cache reads,
against 37,090 and 30,070 for the same findings alone, which ranged from
about 19,100 to 140,700 a reading.

The stress pack failed 16 of its 20 runs, in four findings. The decision
record's undelivered claim came back current rather than intended in 11
runs, and in two others claims were listed from outside its section. The
first pair of opposite verdicts came back with each other's verdict in
five, and one true claim came back `false` in another. None of it decides
the cap.

Handed those ten findings from unrelated roots in one call, before the
calls were isolated, it passed two of four runs.
One failed run listed a sentence from the next section as one of a
section's claims, true but outside the unit; the sentence telling the
agent never to list one was added after it. The same run gave the first
pair's two findings each other's verdict, so a false claim came back
`true`. The other, after that sentence, reported the decision record's
undelivered eviction claim `false`, as it has to be, but current rather
than intended. A reading that strays from its unit or misreads a kind,
or returns a false claim as true, is not one to mark from, so the skill's
cap stayed at one finding.

Haiku, over two runs of the first three,
gives the right verdict on every claim, both false ones included,
but in three of its six fixture runs it also reports the sentence under
the next heading as one of the section's claims, which fails that
fixture. A reader that doesn't keep to the unit can't be trusted on a
mark covering that unit, so sonnet stays the default.

## Next

The check pages follow, gate checks first, and
[executable-claims](checks/executable-claims.md) opens them.
