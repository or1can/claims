# judgment-agent

Two things share this name, and the split between them is the whole
point. The **check** is deterministic: it works out which names in
tracked Swift and Rust the diff added or removed, finds every backticked
citation of one of them in tracked Markdown, and reports each as a
candidate, ranked and never filtered. The **subagent** is the judge: it
takes one candidate, reads the code the claim cites, and returns a
verdict with the evidence that decided it. The check never decides
anything, and the subagent never runs on its own. Both are advisory;
nothing either produces blocks a commit.

## What the check computes

A **subject** is a name a tracked `.swift` or `.rs` file declares. In
Swift that is a line introducing a function, variable, constant, type,
protocol, actor, type alias, enum case or initialiser, with any access
and modifier keywords in front of it; in Rust, a line introducing a
function, struct, enum, trait, type alias, module or `impl` block, with
any visibility, `async`, `unsafe` or `const` in front. Nothing in any
other language is a subject.

The **subject index** is built twice, once at the base of the diff range
and once at its head. For the range `HEAD`, which is what the commit
hook and the CLI use by default, the base is the last commit and the
head is the working tree, so the index at the head reads each tracked
file as it sits on disk, whether or not the change to it is staged. A
range `A..B` is split at the dots
into two revisions; `A...B` is split the same way, without resolving a
merge base.

The **delta** is the symmetric difference of the two indexes: a name in
the base index and not the head was removed by the diff, a name in the
head and not the base was added. A rename is one removed name and one
added name, not a pair, because nothing here guesses that the two are
the same thing. A name declared in the diff but present on both sides,
because its body changed and its name did not, is not in the delta.

A **candidate** is a backticked citation, in any tracked `.md` file,
whose name is in the delta. A dotted citation names its last component,
so `Store.fetchRecord` cites `fetchRecord`, and trailing call
parentheses are ignored. The match is exact membership in a set the
code derived; the check never searches prose for the words of a claim.
Citations are read whole-tree, so a claim in a file the diff never
touched is a candidate when the diff touched its subject, which is the
case that scoping by changed files would miss.

Each candidate's message names the cited subject, whether the diff
removed or added it, the file and line where it is or was declared, and
the evidence that it changed: the commits in the range that touched the
declaring file, or, when the head of the range is the working tree and
the change is not yet committed, that fact stated as such. Removed
subjects are listed before added ones, since a citation of a name that
no longer exists is the more urgent read, and within each group the
candidates with more commits behind them come first.

The list is ranked and never filtered. No score drops a candidate as
probably fine, because a list that can shrink to nothing is a verdict
in disguise, and producing a verdict is the subagent's job. Two
imprecisions are accepted in the direction of showing more: a name
declared in more than one file cites the declaration in whichever file
sorts first, and the commits shown are every commit that touched the
declaring file in range rather than only those that touched the
declaring line.

With no name added or removed, the check reports nothing. The check
runs no command and reads no configuration.

## What the subagent decides

Each candidate's message already carries everything the subagent needs:
the citation's `file:line`, the subject's name, which way it changed,
and where it is declared. The `check-claims` skill invokes the
`judgment-agent` subagent once per candidate, never batched, and passes
it the finding's citation and message verbatim.

The subagent locates the subject by its exact name, opens every site it
touches with the file-reading tool rather than stopping at a search
hit, or runs the command the claim implies, and answers with one JSON
object: the candidate's own `file:line`, a verdict of `confirmed`,
`refuted` or `inconclusive`, the code it actually read or the command it
actually ran as evidence, and one or two sentences of reasoning.
Evidence is mandatory in every verdict, including an inconclusive one,
and a verdict whose evidence is the claim's own wording, or its own
file and line, is a failure of the subagent rather than an answer. A
totalising claim is confirmed only if every site it names was read.

The subagent judges and stops. Fixing the claim, editing a file or
running anything that changes the tree belongs to whoever invoked it.
Its verdict is advisory whatever it says; no part of `claims` treats a
refuted verdict as a gate. After a refuted verdict, the skill can be
asked to search the whole tree for every other citation of the same
subject and hand each to the subagent in turn, since the check's own
list only ever holds citations of what this diff touched; that step is
on demand, never automatic.

## Without an agent

Through the plain CLI, a git pre-commit hook or a CI step, the check
runs exactly as it does anywhere else, and the candidate lines it prints
are the whole of its output. Nothing resolves them: there is no
subagent to invoke, so a candidate is printed and left, and reading the
cited code against the claim is the reader's own job. The check's half
is not lessened by this, and the subagent's half does not exist there.

## Why it exists

A claim about architecture or intent, "every read goes through the
store", has no single fact a mechanical check can test, and the check
that comes closest is the one that reads the code. What can be computed
is which such claims a diff has put in doubt, and computing it well
turns on two things a simpler approach gets wrong. Scoping the search to
the files the diff changed misses the claim that lives elsewhere. And
counting commits since the claim was last touched, the way
[stale-claims](stale-claims.md) does, reads zero when the claim and its
subject were changed together, because that commit is the claim's own
last touch; the before-and-after set membership computed here sees that
change regardless.

## Example

The example is a committed step and a pending edit. The step declares a
store with one method and a design page that cites it:

`examples/judgment-agent/history/01-declares/Sources/Store.swift`:

```swift
{{#include ../../examples/judgment-agent/history/01-declares/Sources/Store.swift}}
```

`examples/judgment-agent/history/01-declares/docs/ARCHITECTURE.md`:

```markdown
{{#include ../../examples/judgment-agent/history/01-declares/docs/ARCHITECTURE.md}}
```

The pending edit renames the method and drops the disk read, and adds
a changelog entry citing both the old name and the new. The design page
is not touched:

`examples/judgment-agent/Sources/Store.swift`:

```swift
{{#include ../../examples/judgment-agent/Sources/Store.swift}}
```

`examples/judgment-agent/CHANGELOG.md`:

```markdown
{{#include ../../examples/judgment-agent/CHANGELOG.md}}
```

Run with that edit staged, the check reports:

```
{{#include ../captures/judgment-agent.txt}}
```

The delta is two names: the old method, removed, and the new one,
added. The struct is declared on both sides and is not in the delta, so
the design page's second sentence, which cites only `Store`, is not a
candidate. The two citations of the removed name come first, the
changelog's and then the design page's, and the changelog's citation of
the added name last. Each carries the declaration site on its own side
of the diff, and each says the change is uncommitted, because it is; a
run over a range that spans the commit once it has landed, `main..feature`,
names the commit instead.

None of those three lines is a verdict. The changelog's two citations
are about the rename itself; the design page's sentence names a method
that no longer exists and describes a disk read that no longer happens,
and only a reading of the new method body shows the second. That reading
is the subagent's to make, and its verdict for that candidate rests on
the method's own lines rather than on the sentence. Through the CLI
alone, the three lines above are the entire output, and the design
page's sentence stays as it is until someone reads it.

The fix for a refuted claim is to correct the sentence; the fix for a
confirmed one is nothing. A candidate is never itself something to fix.

## Configuration

None. The check reads no key from `claims.toml`, and there is no
`exclude`: every tracked `.swift` and `.rs` file is a source of subjects
and every tracked `.md` file is a source of citations. A
`[judgment-agent]` table is accepted and configures nothing.

`enabled`, which takes a check out of the commit gate while leaving it
in the on-demand skill and the CLI, is read by the commit hook rather
than by the check, so it applies here as it does everywhere; see
[Configuring `claims`](../configuring.md#silencing-one-check-at-commit-time).

## Retirement markers

None. A citation inside a blockquote, an italicised sentence or a
paragraph opening "Previously said:" is a candidate like any other, and
so is one under the `was:` marker that
[check-citations](check-citations.md) honours: a sentence written to say
a name is gone still cites it, and whether the sentence is right is the
subagent's question. The [retired-quote
exemption](../concepts.md#the-retired-quote-exemption) skips a sentence
quoted in order to retire it; this check's unit is a citation, and a
candidate list is not narrowed by anything, by design.

## Next

This is the last page. The settings shared across checks are on
[Configuring `claims`](../configuring.md), and the words this page used
without defining are on [Concepts](../concepts.md).
