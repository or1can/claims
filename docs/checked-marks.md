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
| `by` | string, optional | Who read it. Nothing reads this key; it is a record. |
| `extent` | `"full"` or `"partial"`, optional | How much of the unit was read. Written only for a [partial mark](#partial-marks); an entry without it is full. |

A missing file means no marks. A file that does not parse, an entry
missing a required key or holding one of the wrong shape, an entry with an
empty note, an entry whose `extent` is neither `"full"` nor
`"partial"`, an entry whose `file` or a subject is an absolute path or
climbs out with `..`, or an entry written other than as a `[[mark]]`
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
file is compared the same way over that section's lines. A blob the
store does not hold expires the mark, which is what happens to one
recorded against content that was never staged or committed, or that
was only ever in another clone. Content staged but never committed is
in this clone's store alone, so a mark recorded against it holds here
and expires everywhere else. A mark recorded before a file was
append-only holds that file's content hash, and goes on expiring on any
change to it until it is marked again.

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
python3 -m claims.cli mark-checked [--repo-root R] [--diff-range RANGE] [--by NAME] [--partial] [--prune] [FILE|-]
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
as written, comments included. Exit codes are `0` once the marks are
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
mark](#partial-marks).

There is no form that marks findings without a note each. Whoever reads
the finding writes the mark, and that can be an agent, once it has read
the finding against what it cites.

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

## What a run shows

A quieted finding is not printed. The summary line counts it, ending `, Q
quiet while checked` after the gate failure count, so a quiet run is never
mistaken for a clean pass. The count is left off when nothing was quieted.
When [partial marks](#partial-marks) kept some of those findings quiet,
it continues `, P of them partly`, as in `12 quiet while checked, 4 of
them partly`; the clause is left off when `P` is zero. The commit hook prints the
same count as the last line of its message, including on a commit where
marks quieted every finding. Gate findings and exit codes are unchanged:
a mark only ever quiets an advisory finding, which never blocked anything.

The CLI's summary line also ends `, A mark(s) added in range` when the
range added entries to `claims.checked.toml`. An entry counts when its
`file`, `mode` and `unit` are on the range's new side and not its old one,
so re-marking a finding that already has an entry adds nothing. A batch
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

No `claims.toml` key sets the flag, and the commit hook never applies it,
so local commits stay advisory and the cost of reading lands where a
project asks for it. A project passes it in CI, over the pull request's
whole range from its merge base, so that the pull request resolves every
finding it brings in. On GitHub Actions, with the project's history
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

The check pages follow, gate checks first, and
[executable-claims](checks/executable-claims.md) opens them.
