# spliced-docs

A doc comment that has ended up above the wrong declaration. Inserting a
declaration between an existing comment and the declaration it was
written for is a routine edit, and the compiler and the documentation
renderer are both content with the result: the comment now documents the
newcomer, and the declaration it described is bare. The check looks for
a comment that reads as two documents run together and names the
declaration that lost its own. That is an advisory finding, because a
break in a comment is common and only some breaks are splices. The check
reads Swift and Rust, and nothing else.

## What it checks

Every tracked `.swift` and `.rs` file is read; no Markdown is, and no
comment other than a `///` line. The unit is a **run**: one contiguous
block of `///` lines, together with the attributes and the declaration
beneath it.

A **break** is a place inside a run where one line ends a sentence and
the next reads as a fresh summary, with no blank `///` between them. A
line reads as a summary when it opens the way a summary line does: with
"The", "A" or "An"; with a third-person verb such as "Loads" or
"Returns"; or, in Swift, with one of a few further openers such as
"Whether". That reading comes from the house style both languages'
conventions share, a one-line summary, a blank `///`, then detail, so a
second summary with no blank line before it is where one document ends
and another begins.

A break alone is far too noisy to report; an ordinary second sentence
trips it constantly. What distinguishes a splice is that the stranded
half, the lines above the break, names in backticks a declaration that
the comment is plainly not attached to. Two readings of "not attached"
are available, each a **mode** of the check, and a finding names the
mode that fired:

- `undocumented`, on by default: the stranded half names a declaration
  in the same file that has no `///` run of its own. That is the shape
  an insertion leaves behind, and the finding is reported under the mode
  `spliced-docs-undocumented`. In Rust, "names" also covers a parameter
  of the undocumented function when the parameter sits on a line of its
  own, and a name documented once on a trait and bare on every
  implementation is not counted as undocumented.
- `unknown`, opt-in: the stranded half names something no tracked Swift
  or Rust file declares at all, reported under `spliced-docs-unknown`.
  On a codebase with dense, cross-referencing doc comments this fires on
  ordinary technical prose, a configuration field, a domain term, a
  parameter, far more often than on a splice, which is why it is off
  until a project has looked at its own noise level and chosen it.

A comment whose declaration is documented and whose stranded half names
nothing bare is not reported, whatever its breaks. A documented
declaration is one whose `///` run sits immediately above it, with only
attributes between.

The check is whole-tree, and has no `exclude`: a splice can predate the
commit being checked by years, and every tracked Swift and Rust file is
read on every run. The only way to keep a file from being read is to take
the check out of the commit gate altogether, and this repository does
exactly that. Its only Swift and Rust are the worked examples under
`examples/`, one of which is the splice on this page, so the check is
switched off here at commit time rather than left to report its own
example on every commit.

## Why it exists

A splice is invisible to everything that normally catches a
documentation error. The compiler does not read the comment; the
renderer attaches it to the nearest declaration and renders it there,
under the wrong heading; a reviewer sees a diff adding a documented
declaration, and a comment that still reads well. The text is true of a
declaration it is no longer attached to, and the one it was written for
shows as undocumented. That is the one trace the edit leaves, and it is
what the check reads.

## Example

The example is one Swift file and one Rust file, each with the same
splice. In each, a comment was written for a function, and a property
or struct was later inserted between the comment and the function with
a summary line of its own.

`examples/spliced-docs/Sources/Room.swift`:

```swift
{{#include ../../examples/spliced-docs/Sources/Room.swift}}
```

`examples/spliced-docs/src/project.rs`:

```rust
{{#include ../../examples/spliced-docs/src/project.rs}}
```

Run against a fresh repository holding those two files, with no
`claims.toml`, the check reports:

```
{{#include ../captures/spliced-docs.txt}}
```

In the Swift file, the run above the property is two documents: a
sentence about whether an in-place restore is allowed, then a summary of
the plugin that vetoed one. The break is the line where the second
summary begins with no blank `///` before it. The stranded half names
`canRestoreInPlace`, which is declared further down with no comment of
its own, and that is the evidence. The property is documented, by the
run as it stands, so the finding is about the function and not about it.

The Rust file is the same shape. The stranded half names `load_project`,
which is bare, so the finding names it. The stranded half also names
`path`, and the finding does not, because `path` is a field of the
documented struct rather than a bare declaration. Run with `unknown`
mode on as well, the same break produces a second finding naming
`path`, since no Rust file declares an item by that name: that is the
noise the mode is opt-in for.

The fix is to move the stranded half back above the declaration it
describes. Where a break is genuinely one document with two summaries,
a blank `///` line between them is read as summary-then-detail and is
not a break.

## Configuration

```toml
[spliced-docs]
modes = ["undocumented", "unknown"]
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `modes` | list naming one or both of `"undocumented"` and `"unknown"`; a bare string is a one-element list; any other name is a configuration error | `["undocumented"]` | The project has checked what `unknown` reports on its own tree and found the noise acceptable, or wants `unknown` alone. Naming only `unknown` switches the default mode off. |

There is no `exclude`. Every tracked Swift and Rust file is read, and a
project that needs one of them left alone takes the check out of the
commit gate instead.

`enabled`, which takes this check out of the commit gate while leaving it
in the on-demand skill and the CLI, is shared by every check and covered
on [Configuring `claims`](../configuring.md#silencing-one-check-at-commit-time).

## Retirement markers

None. The check reads no Markdown, so it never meets a blockquote, an
italicised sentence or a paragraph opening "Previously said:", and the
[retired-quote exemption](../concepts.md#the-retired-quote-exemption)
has nothing here to apply to. A doc comment is either attached to its
declaration or it is not. A second summary that is deliberate is kept
from being read as a break by a blank `///` line before it.

## Next

This is the last page. The settings shared across checks are on
[Configuring `claims`](../configuring.md), and the words this page used
without defining are on [Concepts](../concepts.md).
