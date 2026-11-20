# Checked marks

A record that someone read an advisory finding and found it true. A
marked finding stays quiet on later runs until something it was read
against changes, and then it is reported again without anyone lifting the
mark. Marks live in `claims.checked.toml` at the repository root, beside
`claims.toml`, and are committed with the project, so its history shows
what was checked and by whom.

Marks are for prose that was read. Prose that should never be read at all
is what a check's `exclude` key is for.

## The file

`claims.checked.toml` holds one `[[mark]]` table per mark:

| Key | Shape | What it records |
| --- | --- | --- |
| `file` | string | The file the finding cites. |
| `mode` | string | The finding's mode. A mark on one mode of a sentence leaves the sentence's other modes reported. |
| `unit` | string | A hash of the finding's unit, described below. |
| `copies` | positive integer | How many copies of the unit the file held when it was marked. |
| `subjects` | table of path to hash | A content hash of each file, or `page.md#anchor` section, the unit names; for an [append-only file](configuring.md#append-only-files), its git blob id. |
| `note` | non-empty string | What the reader verified. Required. |
| `by` | string, optional | Who read it: the reader, never the approver. Nothing acts on this key; it is a record. |
| `approved_by` | string, optional | Who approved a [pending mark](#pending-marks), written by `approve-marks --by` or `fold-approvals --by`. Nothing acts on this key; it is a record. |
| `extent` | `"full"` or `"partial"`, optional | How much of the unit was read. Written only for a [partial mark](#partial-marks); an entry without it is full. |
| `review` | `"pending"`, optional | That no person has reviewed the reading yet. Written only for a [pending mark](#pending-marks); an entry without it is reviewed. |

A missing file means no marks. A file that does not parse, an entry
missing a required key or holding one of the wrong shape, an entry with an
empty note, an entry whose `extent` is neither `"full"` nor
`"partial"`, an entry whose `review` is anything but `"pending"`, an entry whose `file` or a subject is an absolute path or
climbs out with `..`, an entry with the `file`, `mode` and `unit` of an
earlier one, as a conflict resolved by keeping both sides leaves, or an
entry written other than as a `[[mark]]`
table is invalid. A path that reaches outside the repository through a
symlink, or names anything but a regular file, is never read. An invalid file is reported as one gate finding, cited at
`claims.checked.toml:0`, so it blocks a commit the way an invalid
`claims.toml` does, and no mark applies until it is fixed.

The file is written by `mark-checked`, below. Editing or removing an entry
by hand is allowed, and deleting an entry is how a mark is lifted early.

## Units

A mark is keyed by its finding's **unit**, never by a line number, so it
follows the text when lines above it move. Each markable check has one
kind of unit:

| Check | Unit |
| --- | --- |
| `claim-words`, `temporal-words` | The sentence the finding quotes. |
| `judgment-agent` | The sentence holding the cited line; where two sentences share that line, the one holding the cited name. A line inside a fenced code block, which no sentence holds, is its own unit. |
| `stale-claims` | The section's heading. A heading repeated in one file is a separate unit each time, told apart by its order, as a repeated heading's anchor is, so inserting an identical heading above existing ones can move a mark onto another section of the same name, where only a subject change expires it. A file with no heading is one section, whose unit is the file itself: its mark expires only with its subjects. |
| `restatement` | The surviving line, together with the retracted words the finding quotes. |
| `spliced-docs` | The run of `///` doc-comment lines holding the cited line. |

Findings from any other check, and gate findings, cannot be marked.
Checking a gate finding does not fix what it reports.

A unit is hashed as its words, the way `restatement` reads text: case,
punctuation, inline markup and a link's destination are dropped. So
rewrapping a paragraph, or changing a word's emphasis, keeps a mark, and
changing, adding or dropping one word loses it.

## When a mark stops applying

A mark keeps a finding quiet only while everything it was read against is
unchanged. It stops applying when any of these happens:

- No unit in the file hashes to the mark's `unit`: the wording changed.
- A recorded subject's content differs from its recorded hash, or its file
  is gone. An append-only file only growing is not a difference. A
  subject whose file is already gone when the mark is written is not
  recorded.
- The unit now names a subject the mark did not record, such as a bare
  `` `store` `` once a `store.py` exists to resolve it to.

Subjects are found the way `stale-claims` finds them, from the paths and
backticked file names the unit's text holds, and are read as they are on
disk. No commit is recorded, so a rebase, a squash, or the order in which
fixes land after a reading does not matter: a mark applies while what it
was read against is byte-identical, or for an append-only file, below,
has only grown. Edit a subject and then put it back exactly as it was,
and the mark applies again.

An [append-only file](configuring.md#append-only-files), which
`CHANGELOG.md` is by default, is recorded as its git blob id: the id
staging the file would give it, with the line-ending conversion and
filters staging applies, so a clone that checks it out with `\r\n`
records the same id as one that does not. Growing does not count as its
content differing. While the file matches the recorded blob the mark
applies. Otherwise the recorded blob is read from git's object store,
and the mark applies while every one of its lines is still in the file,
in the same order: lines added anywhere keep the mark, and a line
changed or removed expires it. A subject naming one section of such a
file is compared the same way over that section's lines. The recorded
blob counts only while it is the file's content in a commit `HEAD`
reaches, or is staged for the file in the index; anywhere else it
expires the mark, even if git's object store still holds it. That is
what happens to one recorded against content that was never staged or
committed, that was only ever in another clone, or that is no longer in
`HEAD`'s history because a rebase or amend rewrote the commit holding
it, so a mark that would expire in CI expires in your clone too. A mark
recorded before a file was append-only holds that file's content hash,
and goes on expiring on any change to it until it is marked again.

A [navigation page](configuring.md#navigation-pages) named without an
anchor is not recorded, and an edit to it expires no mark. A link with
an anchor into one records that section, as into any page. A mark
recorded before the page was listed keeps its entry for the whole page,
and that entry is no longer compared.

A unit that names no subject expires only on its wording. Its mark says
that the sentence was read, not that it is still true: a claim about
behaviour the sentence never cites by path or name can go false under
it while the mark holds.

A mark quiets at most `copies` findings. When the file holds more copies
of the unit than the mark recorded, as many findings as there are extra
copies stay reported, because which copy is the new one cannot be told.
Marking the new copy records the larger count and quiets them all.

## Writing marks

`mark-checked` records a batch of marks:

```sh
python3 -m claims.cli mark-checked [--repo-root R] [--diff-range RANGE] [--by NAME] [--partial] [--pending] [--prune] [FILE|-]
```

It reads entries one per line from `FILE`, or from standard input when the
argument is `-` or left out. Each entry is a finding's citation and mode,
as a finding line prints them, then a note saying what was verified:

```
docs/guide.md:3 claim-words-totalising src/cache.py has one reader, get, and nothing else reads the store
```

The checks run once for the whole batch, over `--diff-range` (default
`HEAD`, the same meaning as a normal run), and every entry must name an
advisory finding of that run. An entry marks every finding of its mode at
its citation: two sentences sharing a line print at one citation, and one
note covers both. An audit that read findings over a wide
range marks them over the same range, where a diff-scoped check still
reports them; on `HEAD` alone it would not.

If any entry names no such finding, names a gate finding or a mode that
cannot be marked, or has no note, the command prints each bad entry and
writes nothing. Blank lines are skipped. An entry for a finding that
already has a mark replaces it, so re-marking after a reading refreshes
the recorded subjects and copies. Every other entry in the file is kept
as written, comments included. Each write puts the entries in order of
file, then mode, then unit, so branches that mark findings in different
files edit different parts of the file, and git merges them without a
conflict unless their new entries land next to each other. A comment
directly above an entry moves with it. The order only matters when the
file is written: a file edited out of order by hand reads the same, and
the next write sorts it. Exit codes are `0` once the marks are
written, `1` for a batch with a bad entry or, without `--prune`, no
entries, and `2` when
`claims.toml` or `claims.checked.toml` is invalid or `FILE` can't be
read.

`--prune` also removes every [orphan](#orphans), and only those, in the
same write as the batch's new marks, so a reworded sentence's old mark
goes and its new one is recorded in one call. With `--prune`, entries
are optional: with none, the command only prunes, and it does not wait
for entries when standard input is a terminal. It reports how many marks
it pruned, `0` included, and exits `0` even when it pruned and marked
nothing. A bad entry still fails the batch, and then nothing is pruned
either. A pruned mark needs no note, since removing an orphan quiets
nothing. A comment directly above a pruned entry, with no blank line
between, goes with it. A comment above an entry that stays is kept, even
where the entry before it is pruned or replaced.

`--partial` writes each of the batch's marks as a [partial
mark](#partial-marks), and `--pending` as a [pending
mark](#pending-marks); the two combine.

There is no form that marks findings without a note each. Whoever reads
the finding writes the mark, and that can be an agent, once it has read
the finding against what it cites. The plugin ships one agent for that
reading, the [reading agent](reading-agent.md), which reports what it
read and leaves the marking to the session that called it.

## Partial marks

A section can be long enough that a reader checks only part of it, or
reads only what the branch changed. `mark-checked --partial` records
that, as `extent = "partial"` on each of the batch's marks, so a narrow
reading is never mistaken for a full one. Only a `stale-claims` section
or a `spliced-docs` doc comment can be partly read: a sentence or a line
is read whole or not at all, so a `--partial` entry for any other mode is
a bad entry.

A partial mark keeps its finding quiet, counts as marked under
[`--fail-on-unmarked`](#failing-a-run-on-unmarked-findings), and expires,
exactly as a full mark does. The summary line counts the findings it
keeps quiet [separately](#what-a-run-shows).

A partial entry for a finding whose full mark is still current, with its
unit and every recorded subject as they were, is a bad entry, and the
batch writes nothing: a partial reading can't replace a current full
one. Once that full mark has expired, the partial entry replaces it like
any re-mark. A full entry always replaces a partial mark.

## Pending marks

Where agents write marks, a person may want to review each one later
without holding the agent up. `mark-checked --pending` records each of
the batch's marks with `review = "pending"`: written, and not yet
reviewed. A pending mark keeps its finding quiet, counts as marked under
[`--fail-on-unmarked`](#failing-a-run-on-unmarked-findings) and the
commit hook, and expires, exactly as any other mark does. The summary
line counts the findings it keeps quiet, and the pending marks a range
added, [separately](#what-a-run-shows). A plain `mark-checked` over a
pending entry replaces it as a reviewed mark, recording the subjects
afresh.

The review cycle has two more commands. Neither runs any check.

```sh
python3 -m claims.cli pending-marks [--repo-root R] [--at REV [--own]]
```

`pending-marks` prints each pending entry as `<file>:<line> <mode>
<note>`, followed by ` (by <by>)` when the entry names its reader, so
the reader is in view when a person reviews the mark, then `N pending
mark(s)`, and exits `1` while any exist, `0`
when none do, so CI can fail a pull request until its marks are
reviewed. The line is where the first copy of the mark's unit starts in
`<file>`, or `0` when the unit is gone; expired and
[orphaned](#orphans) pending marks are listed too. Without `--at` it
reads the working tree. With `--at REV` it reads `claims.checked.toml`,
and each marked file, as committed at `REV`, and a commit without the
file has no pending marks. Adding `--own` lists only the pending entries
`REV` wrote itself: those its first parent lacks, or holds with any key
different. An entry `REV` inherited unchanged is left out.

```sh
python3 -m claims.cli approve-marks [--repo-root R] [--by NAME] REV
```

`approve-marks` approves the marks a reviewer read at commit `REV`: it
removes `review` from every entry that is pending in the working tree
and was pending at `REV` with every other key identical. Each approved
entry is rewritten as `mark-checked` writes it; every other entry keeps
its text and comments. It prints `approved <entry>` for each, each
`<entry>` as `pending-marks` prints it, and
`left pending <entry>: <why>` for each pending entry it left: `changed
since REV` when the entry at `REV` differs, including one that was
reviewed there and is pending now, or `not in REV`. A closing line gives
both counts. It exits `0` even when it approved nothing; commit the file
afterwards. Re-running `mark-checked` is no substitute, since it records
the subjects as they are now, which the reviewer may not have read.

With `--by NAME`, each approved entry gets `approved_by = "NAME"`,
replacing any `approved_by` it had. Its `by` is left as it was, so the
entry names its reader and its approver apart. Which entries are
approved is decided before that, so an entry whose `by` differs from its
entry at `REV` is still left pending. `claims` puts no format on `NAME`
and records it as given, the same as `mark-checked --by`. An entry
approved before `approved_by` existed may hold its approver's name in
`by`, where the reader's name used to be; nothing rewrites it.

So the cycle is: an agent marks with `--pending` in the commit that
brings the findings in; a person reads the marks `pending-marks --at
<commit>` lists and runs `approve-marks <commit>`, then commits the
result. Both commands exit `2` for a `REV` git can't resolve to a
commit, or a `claims.checked.toml` invalid at `REV` or in the working
tree.

What `approve-marks` guarantees is the entry's content: each approved
entry is exactly the one the reviewer read at `REV`, compared when the
command runs. Nothing records `REV` afterwards, so it can't later prove
which commit was read, or that a person rather than an agent ran it.
That rests on the project's own process, and a forge rule such as a
required pull request review is set up outside `claims`.

Because the approval holds for content, a rebase, amend or squash that
leaves each approved entry with every key identical needs no re-approval. Only a
pending entry `approve-marks` would leave pending, `changed since REV`
or `not in REV`, needs reading again.

How the approval shows in history is up to the project. It can be a
commit of its own, or [folded](#folding-approvals-into-their-commits)
into the commit that wrote the marks.

## Folding approvals into their commits

The ideal is to approve at commit time: a person working with an agent
interactively reads the marks the agent's commit raised, and approves
them before the commit is made, so no approval is ever pending in
history. Marks written while nobody could approve, by an agent working
alone for instance, reach the branch pending. `fold-approvals` approves
them afterwards inside the commits that wrote them, so each mark is
approved as written in its commit and read against that commit's tree.
A mark written in one commit and re-marked in a later one is two
approvals, one per commit.

```sh
python3 -m claims.cli fold-approvals [--repo-root R] BASE --by NAME [--approve REV ...] [--apply]
```

`BASE` is the commit the branch is folded onto, such as the branch it
will merge into, which has to be up to date already: the command never
fetches. Without `--apply`, it changes nothing. For each commit in
`BASE..HEAD` it prints the commit, then that commit's own pending marks
as `pending-marks --at <commit> --own` lists them, then each `fixup!`
commit that targets it, with that fixup's own pending marks under it.
A `fixup!` targets the commit `git rebase --autosquash` would fold it
into: the first earlier commit whose subject it names, or the one it
names by hash, or the first earlier commit whose subject starts with
what it names. Last comes the plan: which commits it would approve,
and which fixups it would fold. Read the marks it lists, against each
commit's own tree, before naming that commit.

Name each commit whose marks were read with `--approve`. Naming a commit
covers it and the fixups listed under it. With `--apply`, the command
runs one rebase of `BASE..HEAD`, folding every fixup into its commit.
After each named commit and its fixups, it approves that group's own
pending marks against the commit as originally committed, then against
each fixup in turn, writing `NAME` as each approved entry's
`approved_by`, as `approve-marks REV --by NAME` does, and amends
`claims.checked.toml`
into the rewritten commit, without running its commit hooks. A commit not named still has its fixups
folded, and none of its marks is approved; an entry it wrote stays
pending in every later commit too, even a named one.

During that rebase only, `claims.checked.toml` merges entry by entry
rather than line by line, so a later commit that re-marks an entry an
earlier step approved doesn't stop the rebase: where both sides changed
one entry, the commit being replayed wins, and its own reading is
pending again until its own step approves it. A merge or rebase run any
other way merges the file line by line, as git always does.

Afterwards, the new tip's tree has to equal the old tip's, except that
`claims.checked.toml` may only have lost `review = "pending"` lines and
had `approved_by` lines replaced or added, each in an entry it approves. Any
other difference, or a rebase that
stops, puts the branch back at the old tip and exits `1`. On success it
prints each named commit as rewritten, with `left pending <entry>`
under it for each of its own entries still pending, then the old tip's
SHA and the `git push --force-with-lease=<branch>:<old sha>` that
publishes the result. It never pushes.

It refuses, exiting `1` with nothing changed, when the working tree has
uncommitted changes, a rebase is in progress, `HEAD` is detached,
`claims.checked.toml` holds a pending entry at `BASE`, the range holds a
merge commit or a `squash!` or `amend!` commit, a `fixup!` in the range
targets no commit before it in the range, nothing in the range is
pending, an `--approve` names a commit outside the range or a fixup, or
the repository's own `.gitattributes` gives `claims.checked.toml` a
`merge` attribute, which would override the fold's. A `--by` holding a
line break exits `2`.
A preview, with or without `--approve`, exits `0`, and a `BASE` git can't
resolve to a commit exits `2`. Neither the commit
hook nor CI runs the command.

A correction found after a commit is made belongs in that commit too: a
mark for a finding raised there and noticed later, or a rejected mark's
fix with the deletion or re-mark it implies, is a `fixup!` commit for
the commit it belongs to, which the fold then folds in and approves
with it. Because the fold rewrites the branch, publishing it needs a
force-push with a lease, so it is run where someone can approve that.

## Orphans

A mark whose unit no longer exists anywhere in its file, or whose file
is gone, is reported as an advisory finding, with the mode `checked-mark`, citing the mark's line in
`claims.checked.toml`, so a stale entry is seen and removed rather than
left behind: by hand, or with `mark-checked --prune`. So is a mark for a
mode that can't be marked. A mark whose unit still exists but which no finding of the
current run matched is not an orphan: a diff-scoped check reports nothing
about a sentence the diff left alone. Nor is an expired mark whose unit
is still in its file, or one whose file holds fewer copies of its unit
than it recorded but at least one: `--prune` keeps both.

A `restatement-ngram` mark orphaned by a change that rewords its line
and keeps the quoted words leaves a finding behind as well as the
orphan: the same words reported on the reworded line, a new unit to
mark in that commit. The finding comes from the mark as committed, so
it stays when `--prune` removes the orphan
([restatement](checks/restatement.md#what-it-checks)).

## What a run shows

A quieted finding is not printed. The summary line counts it, ending `, Q
quiet while checked` after the gate failure count, so a quiet run is never
mistaken for a clean pass. The count is left off when nothing was quieted.
When [partial marks](#partial-marks) kept some of those findings quiet,
it continues `, P of them partly`, as in `12 quiet while checked, 4 of
them partly`; the clause is left off when `P` is zero. When [pending
marks](#pending-marks) kept some quiet, it continues `, K of them
pending` after that. The commit hook prints the
same count as the last line of its message, including on a commit where
marks quieted every finding. A mark only ever quiets an advisory
finding, so gate findings are unchanged. Only a run [failing on unmarked
findings](#failing-a-run-on-unmarked-findings) exits or blocks
differently for a mark, since quieting a finding is then what lets it
pass.

The CLI's summary line also ends `, A mark(s) added in range` when the
range added entries to `claims.checked.toml`. An entry counts when its
`file`, `mode` and `unit` are on the range's new side and not its old one,
so re-marking a finding that already has an entry adds nothing. When
some of those entries are pending, `, K of them pending` follows. A batch
of new marks is the thing for a reviewer to read: the count is the only
sign that marks were written without a reading. The CLI reads the range
from git, so a `claims.checked.toml` git does not track yet adds nothing.

## Failing a run on unmarked findings

An **unmarked finding** is an advisory finding, from a check whose
findings can be marked, that no mark keeps quiet. A CLI run can be told to
fail on them:

```sh
python3 -m claims.cli --fail-on-unmarked
python3 -m claims.cli --fail-on-unmarked=restatement,judgment-agent
```

On its own, the flag covers every check in the table under
[Units](#units). With a list, it covers only the named checks, and a name
that is not one of them is a usage error, exit `2`, naming it. With the
flag, an orphaned mark fails the run too, whatever checks the flag names,
since deleting its entry resolves it. An advisory finding from a check
that cannot be marked never fails the run, and gate findings behave as
they do without the flag.

With the flag, the summary line ends `, U unmarked`, counting the
unmarked findings and orphans in scope. The exit code is `1` on a gate
finding, otherwise `3` when `U` is above zero, and otherwise `0`. A run
that exits `3` closes with one more line after the summary, starting
`failing:`, which gives the count again and says to fix or mark each one.

The commit hook applies a version of the flag only for the checks a
project lists under [`[hook]
fail_on_unmarked`](configuring.md#blocking-a-commit-on-unmarked-findings),
and there an orphaned mark blocks only when its own check is listed.
Otherwise local commits stay advisory, and the cost of reading lands
where a project asks for it. A project passes the flag in CI, over the
pull request's whole range from its merge base, so that the pull request
resolves every finding it brings in. On GitHub Actions, with the project's history
fetched and `claims` checked out beside it as
[the command line](installation.md#the-command-line) describes:

```yaml
- uses: actions/checkout@v7
  with:
    fetch-depth: 0
- uses: actions/checkout@v7
  with:
    repository: or1can/claims
    ref: <tag>
    path: claims
- run: |
    base=$(git merge-base "origin/${{ github.base_ref }}" HEAD)
    PYTHONPATH=claims python3 -m claims.cli --repo-root . --diff-range "$base" --fail-on-unmarked
```

A pull request that fails this way is fixed by changing the prose, or by
running `mark-checked` over the same range once each finding has been
read. A dependency bot cannot read a finding, so on a bot's pull request
a person or an agent reads the findings and marks them on its behalf.

## Example

The example is the `claim-words` configuration with a guide that makes two
totalising claims, one of which has been read and is marked from a batch
of one entry:

`examples/checked-marks/claims.toml`:

```toml
{{#include ../examples/checked-marks/claims.toml}}
```

`examples/checked-marks/docs/guide.md`:

```markdown
{{#include ../examples/checked-marks/docs/guide.md}}
```

`examples/checked-marks/marks.txt`:

```
{{#include ../examples/checked-marks/marks.txt}}
```

The capture shows the entry `mark-checked` writes, then the findings once
it applies:

```
{{#include captures/checked-marks.txt}}
```

The marked sentence names the example's cache module by path, so its mark
recorded that file's content hash. The unmarked sentence is still
reported. An edit to the cache module would bring the marked sentence
back, as would changing a word of it.

## Next

[The reading agent](reading-agent.md) is the plugin's subagent for
reading a finding before it is marked.
