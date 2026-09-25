# claim-words

A sentence added to a file the project has designated for its live
claims, that asserts something over a whole set, counts something in the
tree, or reaches for code it is not itself showing. The check reads the
sentences a diff added to those files and reports each one that is
shaped like a claim: "every", "never", "three backends", "without
`evict` this would grow". It cannot tell whether the claim is true, only
that the sentence is making one, so every finding is advisory. And it
reads nothing until the project has said which files count: with no
`files` key the check is installed and inert, and that is the state
every project starts in.

## What it checks

A **designated** file is one matching a glob under this check's `files`
key. The check is diff-scoped: it reads only a designated file the diff
touched, and only a sentence at least one of whose lines the diff added.
A sentence already in the file, and a sentence in a file the project has
not designated, are never read, however they are shaped.

A **sentence** is found by joining a paragraph's lines and splitting at
a full stop, question mark or exclamation mark, so a sentence wrapped
across lines is read whole and reported at its first line. Fenced code
blocks are not set aside: a sentence inside one is read like any other.

Three **modes** classify a sentence, and a sentence matching more than
one is reported once per mode:

- `claim-words-totalising`: the sentence contains a word or phrase that
  asserts over a set and is wrong the moment one member disagrees. The
  fixed list is `every`, `only`, `never`, `always`, `exactly`, `none of`,
  `the one`, `unchanged`, `cannot`, `can never`, `no other`, `nothing
  else`, `each of`, `all three` and `all four`, matched without regard to
  case, as whole words. A word inside a hyphenated token such as
  `--always-verify` is not a match.
- `claim-words-counts`: the sentence counts something with a digit or a
  spelled-out number, of any size, directly before the noun it counts,
  and that noun is not a unit of measurement. "three backends" is a
  count of the tree and a claim; "three seconds", "twelve megabytes" and
  "two percent" measure the world and are not. The unit list covers
  sizes in bytes, durations from milliseconds to centuries, percentages,
  dollars and degrees.
- `claim-words-about-elsewhere`: the sentence holds a backticked
  citation and one of `would`, `otherwise`, `without`, `instead of`,
  `rather than`, `which means` or `which is why`. On its own each of
  those is ordinary English; beside a citation it asserts something
  about the cited code that the sentence is not showing.

The three word lists are fixed and have no configuration surface.

The check runs no command and reads no code. A finding says that a
sentence needs a reader; the subagent described on
[judgment-agent](judgment-agent.md) is the part of `claims` that can
read the code a sentence is about, and a totalising sentence that cites
its subject in backticks is the shape most worth handing to it.

## Why it exists

A specification, a glossary or an agent instruction file is where a
project writes down what is true of the whole tree, and the sentences
there are the ones that go wrong quietly: "every check gates" was true
when the third check landed and false when the fourth did. No
mechanical check can verify a sentence like that, and the alternative to
a sweep for the words such sentences are made of is to never look at
them at all. The sweep is confined to designated files because the same
words in a tutorial are asides, and a check that reported every
"always" in a README would be dismissed on its first run.

## Example

The example is a committed decision record, a `claims.toml` that
designates it, and a pending edit that extends it. The record as
committed already holds a totalising sentence:

`examples/claim-words/history/01-records/decisions/0001-one-cache.md`:

```markdown
{{#include ../../examples/claim-words/history/01-records/decisions/0001-one-cache.md}}
```

`examples/claim-words/claims.toml`:

```toml
{{#include ../../examples/claim-words/claims.toml}}
```

The edit adds a section with one sentence in each shape the check
reports, one count that measures the world, the same retired sentence
under each of the three markers, and the same sentence quoted with no
marker. It also adds a README, which the configuration does not
designate:

`examples/claim-words/decisions/0001-one-cache.md`:

```markdown
{{#include ../../examples/claim-words/decisions/0001-one-cache.md}}
```

`examples/claim-words/README.md`:

```markdown
{{#include ../../examples/claim-words/README.md}}
```

Run with that edit staged, the check reports:

```
{{#include ../captures/claim-words.txt}}
```

The first three findings are the three modes, one each: the sentence
asserting over every read, the sentence counting backends, and the
sentence saying what would happen without a cited function. The sweep
that took three seconds is a count of time and is not reported. The
three marked copies of the retired sentence, the blockquote, the
italics and the "Previously said:" lead-in, are skipped; the unmarked
quotation of the same sentence is the fourth finding, because an
unmarked quotation cannot be told from the claim still being made. The
record's original sentence, "Every request reads through the same
cache", was not added by this edit and is not read. The README's
"every" is in a file the configuration does not name, and is not read
either.

Without the `claims.toml`, the same edit reports nothing. That is why
the file is shown rather than described: a project that has not written
one has this check installed and inert.

Each finding is a sentence to reread. The fix, where one is needed, is
to narrow the sentence to what is actually true, or to retire it under
one of the three markers if it is being quoted to say it was wrong.

## Configuration

```toml
[claim-words]
files = ["spec.md", "CONTEXT.md", "AGENTS.md"]
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `files` | list of glob strings; a bare string is a one-element list | `[]`: nothing is swept | Always, since the check reads nothing until this names a file. List every file whose sentences are claims you would want re-verified against the tree as it stands: a specification, a glossary, an agent instruction file, a README, a documentation site's own prose pages. In practice a changelog and a decision record fail that test — a changelog entry is dated at writing, and while a decision record's consequences are live, its motivation and counts are frozen at the decision's date and outnumber them. Designation is per file, so a file carrying both kinds is included on which kind predominates. A file not listed is never read, whatever it says. |

There is no `exclude`. `files` is the only scope the check has, and a
file outside it is already excluded.

`enabled`, which takes this check out of the commit gate while leaving it
in the on-demand skill and the CLI, is shared by every check and covered
on [Configuring `claims`](../configuring.md#silencing-one-check-at-commit-time).

## Retirement markers

All three. A sentence is skipped when any line it spans is a Markdown
blockquote, `>` followed by a space or the end of the line; when the
whole sentence is wrapped in `*asterisks*` or `_underscores_`; or when
it opens with the lead-in "Previously said:", in any case. Any one of the
three suppresses the sentence, and nothing else does.

That is this check's own set, not a shared one. The [retired-quote
exemption](../concepts.md#the-retired-quote-exemption) is decided per
check against the prose that check reads, and this check honours the
blockquote because narrowing an existing check's exemptions would break
a project already relying on it. A `>` with no space after it is not a
blockquote and not a marker. The reasoning for keeping the sets separate
is in [ADR
0003](../../decisions/0003-retirement-markers-are-scope-dependent.md),
and for keeping this one whole in [ADR
0005](../../decisions/0005-live-and-dated-claims.md).

## Next

[temporal-words](temporal-words.md), the same sweep over the opposite
file set, for sentences dated by a version number or a history word.
