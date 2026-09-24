# stale-claims

A section of tracked Markdown that names a file, beside a history in
which that file has changed since the section was last edited. The check
finds the code each section names, counts the commits each of those
files has seen since the section's own last touch, and ranks the sections
by the largest share of any named file's history that falls after that
point. The output is a ranked list of candidates, never a verdict: a
section high on the list names code that has moved a great deal since
the section was written, and someone should read the two together, but
nothing here has found the section false. A busy file makes an accurate
sentence look suspicious, and a sentence can be wrong about a file that
has not changed at all.

## What it checks

A **section** is a heading and everything below it to the next heading,
at any level, or the whole file when it has no heading. The section is
the unit because a claim about a file is rarely one sentence, and the
heading is what the finding names.

A **subject** is a tracked file the section names, in one of two shapes.
An explicit relative path, a directory and a file name with an
extension, counts when a tracked file has exactly that path. A
backticked bare name, with or without an extension, counts when exactly
one tracked file has that stem: `cache.py` and `cache` both name the
one file whose name without its extension is `cache`. A stem that two
tracked files share names no single file and is dropped rather than
guessed at. A section naming no subject is not ranked.

The bare form is ambiguous in a way the path form is not, because a
word such as `cache` or `config` is as often ordinary prose or a
configuration key as it is a module. The `module_reference_scope` key
narrows where a bare name counts as a subject; by default it counts
everywhere.

The section's **last touch** is the newest commit `git blame` attributes
to any of its lines, by committer time. For each subject, the check
reads the file's full commit history and counts the commits strictly
after that time. The section's **score** is the largest fraction, across
its subjects, of that subject's history that lies after the touch, so a
claim older than most of a quiet file's life outranks one older than a
sliver of a busy file's. The finding names up to three subjects, most
changed first, each with its commit count and its share of history.
Sections are reported in descending score, and a section none of whose
subjects has changed since its last touch is not reported.

A section and its subject changed in the same commit score zero for that
subject, because the commit that touched both is the section's own last
touch and not a change after it. Two separate commits that share a
committer timestamp to the second fall into the same gap. A rewrite of a
claim to match a change to its subject, landed together, is therefore
invisible here, and nothing else in the check compensates for it.

The check is whole-tree, over every tracked `.md` file on every run, and
runs no command. `CHANGELOG.md` is skipped by name in any directory,
because a changelog entry describes a release as it shipped and its
subjects moving afterwards is expected.

## Why it exists

Most prose about code is true when written and stops being true later,
and nothing reports the moment it stops. A rename is caught by a
citation check; a default that moved is caught by a defaults check; but
a paragraph that describes how a module works has no single fact to
test, and the only signal that it might have rotted is that the module
kept changing while the paragraph did not. That signal is weak, which is
why the check ranks rather than decides, and it is still the one signal
available for a claim no narrower check can reach.

## Example

The example is history alone, because a section can only be older than
its subject's changes once those changes have been committed after it.
The capture commits three steps an hour apart. The first writes the
design note and the three files it names:

`examples/stale-claims/history/01-writes/docs/design.md`:

```markdown
{{#include ../../examples/stale-claims/history/01-writes/docs/design.md}}
```

`examples/stale-claims/history/01-writes/src/cache.py`:

```python
{{#include ../../examples/stale-claims/history/01-writes/src/cache.py}}
```

`examples/stale-claims/history/01-writes/src/store.py`:

```python
{{#include ../../examples/stale-claims/history/01-writes/src/store.py}}
```

`examples/stale-claims/history/01-writes/src/log.py`:

```python
{{#include ../../examples/stale-claims/history/01-writes/src/log.py}}
```

The second step changes the cache to evict:

`examples/stale-claims/history/02-evicts/src/cache.py`:

```python
{{#include ../../examples/stale-claims/history/02-evicts/src/cache.py}}
```

The third rewrites the cache again and changes the store's layout on
disk:

`examples/stale-claims/history/03-rewrites/src/cache.py`:

```python
{{#include ../../examples/stale-claims/history/03-rewrites/src/cache.py}}
```

`examples/stale-claims/history/03-rewrites/src/store.py`:

```python
{{#include ../../examples/stale-claims/history/03-rewrites/src/store.py}}
```

The design note is never edited after the first step. Run against that
repository at its third commit, the check reports:

```
{{#include ../captures/stale-claims.txt}}
```

The Caching section is first because its subject changed most: of the
three commits in the cache file's history, two came after the section
was written. The Storage section names its subject as a path rather than
a bare name, and ranks second, with one of the store file's two commits
after the section. The Logging section names a file that has not
changed since the section was written, and is not reported at all. The
capture is the same on every run because the commits carry fixed
timestamps; the score depends on commit times, not on the clock.

Both findings are candidates. The Caching section is in fact false now,
since the cache evicts, and the Storage section is still true, since
entries are still one file per key. The check cannot tell those apart,
and does not claim to. The fix for a candidate is to read the section
against the code and either correct it or leave it, and a section that
is read and left alone stays on the list until its lines are next
touched.

## Configuration

```toml
[stale-claims]
module_reference_scope = ["decisions/*.md", "AGENTS.md"]
exclude = ["docs/legacy/*.md"]
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `module_reference_scope` | list of glob strings; a bare string is a one-element list | absent: a bare backticked name counts as a subject in every file | Common file stems double as ordinary words or configuration keys in the tree, so a bare `cache` or `config` in a tutorial names a module the sentence is not about. With the key set, a bare name counts only in a matching file; a name with an extension, and an explicit path, count everywhere regardless. |
| `exclude` | list of glob strings; a bare string is a one-element list | `[]`: nothing excluded beyond the built-in `CHANGELOG.md` | A file's sections should not be ranked at all: prior-art notes about another project, or a directory of inputs written to be broken, like this site's own examples. An excluded file is skipped whole. |

`enabled`, which takes this check out of the commit gate while leaving it
in the on-demand skill and the CLI, is shared by every check and covered
on [Configuring `claims`](../configuring.md#silencing-one-check-at-commit-time).

## Retirement markers

None. A section is ranked by the age of its lines and the history of
its subjects, and a blockquote, an italicised sentence or a paragraph
opening "Previously said:" inside it is read like any other line. The
[retired-quote exemption](../concepts.md#the-retired-quote-exemption)
skips a sentence quoted in order to retire it; this check's unit is a
section rather than a sentence, and a section that is deliberately
about the past belongs in a file listed under `exclude`.

## Next

[restatement](restatement.md), which finds a sentence a diff retracted
that is still asserted, word for word, somewhere else.
