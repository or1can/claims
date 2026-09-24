# check-citations

A backticked name in tracked Markdown, or in a comment in a tracked Swift
file, that names a symbol the repository once declared and no longer
does. The check reads every declaration any commit ever added, subtracts
the ones still present, and reports a citation of anything left. That is
a gate finding: a rename either left a citation behind or it did not, and
there is nothing for a person to weigh.

## What it checks

A **citation** is a backticked identifier. A dotted name cites its last
component, and trailing call parentheses are ignored, so `Room.loadWidget`
and `loadWidget()` both cite `loadWidget`. The same dead name cited twice
on one line is reported once, at that line.

A **declaration** is a Swift declaration: a line introducing a function,
variable, constant, type, protocol, actor, type alias, enum case or
initialiser, with any access and modifier keywords in front of it. The set
of names ever declared comes from the full commit history of every tracked
`.swift` file, including a declaration that only ever existed in a merge
commit's own conflict resolution. The set declared now comes from the
tracked `.swift` files as they stand, plus the name of any directory
ending in `Tests`, since a test target is cited in prose like a symbol and
declared nowhere. A name in the first set and not the second is gone, and
a citation of it is a finding.

Only Swift declarations are read. A name a Python, Rust or TypeScript file
once declared is outside what the check can see, and a citation of it is
never reported, which is a gap rather than a false positive. In a project
with no tracked Swift file the check finds nothing.

Citations are read from every tracked `.md` file, whole, and from the
comment portion of every line of every tracked `.swift` file. The check is
whole-tree: a citation left behind by a rename is reported on the next
commit, whatever that commit touched.

Reading full history is what makes the check honest, so a checkout that
cannot provide it is a finding of its own rather than a silent pass. A
shallow clone produces one gate finding saying the check cannot run here
and how to fetch the history it needs, and so does any other failure to
read the repository. The history walk is cached in the repository's own
git directory, keyed by the commit it was taken at, so a second run on
the same history reads the cache and a run after new commits walks only
those.

## Marking a historical reference

A citation that is meant to name the old symbol, in a changelog entry or
a comment explaining a rename, is exempted by a `was:` marker: in Markdown,
an HTML comment containing `was: name`; in Swift, a comment that is the
marker and nothing else, `// was: name`. The marker covers citations of
that name on its own line and on the next line, and no further. A wider
scope was tried and silenced real dead citations along with the one it
was meant to cover. The word `was:` in ordinary prose is not a marker,
so a sentence such as "the old name was: `loadWidget`" still fires.

## Why it exists

A rename is the edit most likely to leave prose behind. The compiler finds
every call site; nothing finds the sentence in a design note, the comment
two functions down, or the migration guide that still tells a reader to
look for the old name. The citation was true when it was written and
became false at the rename, and only history can show that it was ever
true. A check that compared prose with the current tree alone would have
to treat every unknown name as suspect, which is unusable; comparing it
with everything the tree has ever declared is what makes a certain, gate
finding possible.

## Example

The example is history, because no static tree can be missing a symbol
it once had. The capture builds it as three commits. The first declares
`loadWidget`:

`examples/check-citations/history/01-declares/Sources/Room.swift`:

```swift
{{#include ../../examples/check-citations/history/01-declares/Sources/Room.swift}}
```

The second replaces it with `loadGadget`, and leaves a comment citing the
name it removed:

`examples/check-citations/history/02-renames/Sources/Room.swift`:

```swift
{{#include ../../examples/check-citations/history/02-renames/Sources/Room.swift}}
```

The third adds a note that cites the old name twice, once as a live
recommendation and once under a `was:` marker:

`examples/check-citations/docs/NOTES.md`:

```markdown
{{#include ../../examples/check-citations/docs/NOTES.md}}
```

Run against that repository at its third commit, the check reports:

```
{{#include ../captures/check-citations.txt}}
```

The first finding is the comment the rename left behind: `loadWidget` was
declared in the first commit and is declared nowhere now, so the citation
in the second commit's own comment is dead the moment it lands. The
second is the note's recommendation to call a function that does not
exist. The note's last line cites the same name and is not reported,
because the `was:` marker on the line above it says the reference is
deliberately to the past. `Room` and `loadGadget` are cited on the same
line as the second finding and resolve, so they produce nothing. `Widget`
and `Gadget` were never declared by any commit and are outside the
check's knowledge altogether.

The fix is one of two edits: retarget the citation to the name the
repository has now, or mark it `was:` if the sentence is genuinely about
the past.

## Configuration

None. The check reads no key from `claims.toml`, and there is no `exclude`:
every tracked `.md` and `.swift` file is read, and the only way to keep a
citation from being checked is the `was:` marker on the line above it. A
`[check-citations]` table is accepted and configures nothing.

`enabled`, which takes a check out of the commit gate while leaving it in
the on-demand skill and the CLI, is read by the commit hook rather than by
the check, so it applies here as it does everywhere; see [Configuring
`claims`](../configuring.md#silencing-one-check-at-commit-time).

## Retirement markers

None. A citation inside a blockquote, an italicised sentence or a
paragraph opening "Previously said:" is checked like any other. The
[retired-quote exemption](../concepts.md#the-retired-quote-exemption)
skips a sentence quoted in order to retire it; this check's unit is a
name rather than a sentence, and it has its own marker for the one case
that needs one, a name cited in order to say it is gone.

## Next

[check-links](check-links.md), which holds a Markdown link to the file
and heading it names.
