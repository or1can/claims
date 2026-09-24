# restatement

A sentence a diff removed that is still asserted, word for word,
somewhere else in the tree. The check reads the removed lines of the
diff, subtracts anything the same file's diff also added, and searches
every tracked file it reads for the words that remain. A surviving copy
is an advisory finding: the diff retracted something in one place, and
the same thing is still said in another, and someone should look. It is
advisory because the same sentence can legitimately live in two places
on purpose, a summary and the page it summarises, and the check cannot
tell a retraction from an edit to one copy of two.

## What it checks

The diff is read file by file, and only the removed lines of a file whose
extension is in scope count. The built-in scope is `.md`, `.swift`,
`.py`, `.sh` and `.yml`, and `extensions` adds to it. Before a removed
line is searched for, the words the same file's diff **added** are
subtracted: a reflowed paragraph removes and re-adds most of itself, and
a thing still said in the same file is not a thing retracted. The
subtraction is per file, so an unrelated addition elsewhere in the diff
cannot cancel a genuine retraction.

Each line is reduced to its **words** before anything is compared: link
syntax is replaced by its text, inline markup characters are dropped,
letters are lowercased, and every other character becomes a space. A
sentence that survives with different emphasis or a re-pointed link is
the same sentence.

Two **modes** search for what remains, and each finding names the one
that fired:

- `restatement-ngram` takes every run of six consecutive words the diff
  removed and did not add back, and reports a line anywhere in scope
  that still contains one. A line with several matching runs is reported
  once, quoting the longest.
- `restatement-whole-line` takes every removed line of at least ten
  words whose whole word sequence does not reappear in the file's added
  words, in order, across line breaks, and reports a line anywhere in
  scope that reduces to exactly the same words.

Six is the run length because eight missed a real restatement that
differed from the retracted sentence by one word. Neither length is
configurable.

The check is verbatim only. A file that restates the removed fact in
different words shares too few consecutive words for the first mode and
does not match line for line for the second, and is not found. That is
by design and not a gap to close: telling a paraphrase from a different
claim is a judgment, and the mechanical half of this tool does not make
judgments.

A survivor is reported only while the removed text exists in at most
`duplication_threshold` other files, one by default. A sentence in two
places, the edited file and one survivor, is exactly the case the check
exists for and is reported; a banner or licence line in three or more is
text duplicated on purpose, where removing one copy says nothing about
the others, and every copy of it is suppressed. The count is taken over
the files that still hold the text, so a line present in two survivors
is over the default threshold whichever of them is read first.

The check is diff-scoped: with nothing removed there is nothing to
search for, and a survivor left behind by an earlier commit is not
reported on a later one. The survivor sweep itself is whole-tree over
every tracked file in scope, so a copy in a file the diff never touched
is found. The check runs no command.

## Why it exists

A fact that lives in two files is corrected in one. The edit that
retracts a sentence is the one moment when the author knows it was
wrong, and the check uses that moment: the removed line is the search
term, and the search finds the copy the author did not remember. A
whole-tree duplicate finder would report every deliberate pair on every
commit; starting from what the diff retracted is what makes the finding
worth reading.

## Example

The example is a committed step and a pending edit. The step holds three
pages that share a banner line, two of which also share a sentence about
eviction, and a third that says the same thing in other words:

`examples/restatement/history/01-states/docs/overview.md`:

```markdown
{{#include ../../examples/restatement/history/01-states/docs/overview.md}}
```

`examples/restatement/history/01-states/docs/setup.md`:

```markdown
{{#include ../../examples/restatement/history/01-states/docs/setup.md}}
```

`examples/restatement/history/01-states/docs/faq.md`:

```markdown
{{#include ../../examples/restatement/history/01-states/docs/faq.md}}
```

The pending edit rewrites the overview, removing the banner and the
sentence and saying the opposite of the sentence:

`examples/restatement/docs/overview.md`:

```markdown
{{#include ../../examples/restatement/docs/overview.md}}
```

Run with that edit staged, the check reports:

```
{{#include ../captures/restatement.txt}}
```

Both findings are the one surviving copy of the retracted sentence, in
the setup page, once from each mode: the first quotes the longest
six-word run the two lines share, the second quotes the whole line as
words. The FAQ says the same thing and is not reported, because it says
it in different words; that is the verbatim limit, and a reader who
wants the FAQ found has to search for it. The banner was removed too,
and survives in both the setup page and the FAQ, which is one file more
than the default threshold allows, so neither copy is reported.

Without the edit, the same three pages report nothing: the check starts
from what a diff removed, and a duplicate that no diff has touched is
not a retraction.

The fix for a finding is to retract the surviving copy too, or to leave
it if the two really are meant to differ; and where a line is shared on
purpose across many files, to raise `duplication_threshold` rather than
dismiss the finding each time.

## Configuration

```toml
[restatement]
exclude = ["CHANGELOG.md"]
extensions = [".rs"]
duplication_threshold = 3
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `exclude` | list of glob strings; a bare string is a one-element list | `[]`: nothing excluded | A file is expected to keep retracted prose on purpose: a release history that still describes a shipped release as it shipped, or a directory of inputs written to be broken, like this site's own examples. An excluded file contributes no removed lines from its own diff, and is dropped from the survivor sweep entirely, so it neither counts toward another file's duplication nor is reported for it. |
| `extensions` | list of dotted suffixes; a bare string is a one-element list | the built-in set alone: `.md`, `.swift`, `.py`, `.sh`, `.yml` | The project has prose or source in a language the built-in set does not cover, `.rs` for a Rust project, and wants its retractions and its survivors read too. Entries are added to the built-in set, never substituted for it. |
| `duplication_threshold` | integer; a boolean or a non-integer is a configuration error | `1` | Text is duplicated on purpose across more files than the default tolerates, a shared licence header or a generated banner, and each copy is reported every time one of the others changes. `0` reports every survivor, including the two-copy case the default keeps. |

`enabled`, which takes this check out of the commit gate while leaving it
in the on-demand skill and the CLI, is shared by every check and covered
on [Configuring `claims`](../configuring.md#silencing-one-check-at-commit-time).

## Retirement markers

None. A surviving copy inside a blockquote, an italicised sentence or a
paragraph opening "Previously said:" is reported like any other line,
because the words are compared after markup is stripped and a
blockquote marker is markup. The [retired-quote
exemption](../concepts.md#the-retired-quote-exemption) skips a sentence
quoted in order to retire it; here a retired quotation of the removed
sentence is a survivor in the plain sense, and a file that keeps such
quotations on purpose belongs under `exclude`.

## Next

[spliced-docs](spliced-docs.md), which reads Swift and Rust doc comments
for one that an insertion has pushed onto the wrong declaration.
