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
| `subjects` | table of path to hash | A content hash of each file, or `page.md#anchor` section, the unit names. |
| `note` | non-empty string | What the reader verified. Required. |
| `by` | string, optional | Who read it. Nothing reads this key; it is a record. |

A missing file means no marks. A file that does not parse, an entry
missing a required key or holding one of the wrong shape, an entry with an
empty note, an entry whose `file` or a subject is an absolute path or
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
| `claim-words`, `temporal-words`, `judgment-agent` | The sentence holding the cited line; where two sentences share that line, the one the finding quotes, or else the one starting there. A line inside a fenced code block, which no sentence holds, is its own unit. |
| `stale-claims` | The section's heading. A heading repeated in one file is a separate unit each time, told apart by its order, as a repeated heading's anchor is. A file with no heading is one section, whose unit is the file itself: its mark expires only with its subjects. |
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
  is gone. A subject whose file is already gone when the mark is written
  is not recorded.
- The unit now names a subject the mark did not record, such as a bare
  `` `store` `` once a `store.py` exists to resolve it to.

Subjects are found the way `stale-claims` finds them, from the paths and
backticked file names the unit's text holds, and are read as they are on
disk. No commit is recorded, so a rebase, a squash, or the order in which
fixes land after a reading does not matter: a mark applies while what it
was read against is byte-identical. Edit a subject and then put it back
exactly as it was, and the mark applies again.

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
python3 -m claims.cli mark-checked [--repo-root R] [--diff-range RANGE] [--by NAME] [FILE|-]
```

It reads entries one per line from `FILE`, or from standard input when the
argument is `-` or left out. Each entry is a finding's citation and mode,
as a finding line prints them, then a note saying what was verified:

```
docs/guide.md:3 claim-words-totalising src/cache.py has one reader, get, and nothing else reads the store
```

The checks run once for the whole batch, over `--diff-range` (default
`HEAD`, the same meaning as a normal run), and every entry must name an
advisory finding of that run. An audit that read findings over a wide
range marks them over the same range, where a diff-scoped check still
reports them; on `HEAD` alone it would not.

If any entry names no such finding, names a gate finding or a mode that
cannot be marked, or has no note, the command prints each bad entry and
writes nothing. Blank lines are skipped. An entry for a finding that
already has a mark replaces it, so re-marking after a reading refreshes
the recorded subjects and copies. Every other entry in the file is kept
as written, comments included. Exit codes are `0` once the marks are
written, `1` for a batch with a bad entry or no entries, and `2` when
`claims.toml` or `claims.checked.toml` is invalid or `FILE` can't be
read.

There is no form that marks findings without a note each. Whoever reads
the finding writes the mark, and that can be an agent, once it has read
the finding against what it cites.

## Orphans

A mark whose unit no longer exists anywhere in its file is reported as an
advisory finding, with the mode `checked-mark`, citing the mark's line in
`claims.checked.toml`, so a stale entry is seen and removed rather than
left behind. A mark whose unit still exists but which no finding of the
current run matched is not an orphan: a diff-scoped check reports nothing
about a sentence the diff left alone.

## What a run shows

A quieted finding is not printed. The summary line counts it, ending `, Q
quiet while checked` after the gate failure count, so a quiet run is never
mistaken for a clean pass. The count is left off when nothing was quieted. The commit hook prints the
same count as the last line of its message, including on a commit where
marks quieted every finding. Gate findings and exit codes are unchanged:
a mark only ever quiets an advisory finding, which never blocked anything.

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
