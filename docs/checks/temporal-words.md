# temporal-words

A sentence added to a file the project has designated as reference prose,
that frames what the software does as a point in its own version history.
A page describing a binary says what it does; "since 0.21.0", "there is
no output mode yet" and "it used to read JSON" say when, and a reader
holding some other build has no way to check them. The check reads the
sentences a diff added to those files and reports each one carrying a
version number or a history word. It cannot tell whether the sentence is
true, only that it is dated, so every finding is advisory. And it reads
nothing until the project has said which files count: with no `files` key
the check is installed and inert, and that is the state every project
starts in.

## What it checks

A **designated** file is one matching a glob under this check's `files`
key. The check is diff-scoped: it reads only a designated file the diff
touched, and only a sentence at least one of whose lines the diff added.
A sentence already in the file, and a sentence in a file the project has
not designated, are never read, however they are shaped.

A **sentence** is found by joining a paragraph's lines and splitting at
a full stop, question mark or exclamation mark, so a sentence wrapped
across lines is read whole and reported at its first line. Two things
are set aside before any of that. A fenced code block is skipped whole,
delimiter lines included, so the block's own content never joins a
sentence and never breaks one. Inside a sentence, an inline code span is
masked: the backticks stay, the text between them is not matched
against. `` `alpine:3.18.2` `` and `` `ref = "1.2.3"` `` are syntax a
page is showing, not a claim it is making.

Three **modes** classify a sentence, and a sentence matching more than
one is reported once per mode:

- `temporal-words-version`: the sentence carries a version number of
  exactly three dot-separated components, `0.3.0`. A number of two
  components is not matched: in prose it is another project's version,
  not this one's. A hyphen may precede it, so `pre-0.9.0` is a match; a
  letter, a digit or a dot may not, so `v1.2.3` and a four-component
  `99.1.2.3` are not. The full stop ending the sentence does not count
  as a fourth component.
- `temporal-words-phrase`: the sentence contains one of `yet`, `not
  yet`, `used to`, `before this existed`, `currently`, `today`, `this
  first version`, `previously`, `historically` and `until now`, matched
  without regard to case, as whole words. A word inside a hyphenated
  token such as `--today-only` is not a match. The word alone is the
  finding; nothing else about the sentence matters.
- `temporal-words-cited`: the sentence contains `now`, and also contains
  a backticked citation. On its own "now" is ordinary English and
  usually about the reader's own session or a tutorial's own sequence;
  beside a citation it is a claim that the cited thing changed.

`no longer` is deliberately not in any of the lists. It reads like the
others, and in the corpus these lists were measured against it was
always another tool's status — "Earthly is no longer maintained" — never
a claim about the project's own past.

The three lists are fixed and have no configuration surface.

A finding is a sentence to reread, not a defect. A directory "that
doesn't exist yet", a tutorial step with "four tasks in the file now",
and a statement about the reader's own project all read the same to this
check as a rotted "not yet" does. That is the trade it is built on: a
false positive is visible and dismissed in a second, where a "yet" that
went false three releases ago is invisible forever.

## Why it exists

Reference prose has no version picker. A reader on a documentation site
gets whatever is published, and cannot line "since 0.21.0" up against
the build they installed — so a version number in a reference page is a
fact the reader is unable to use and the writer is unlikely to revisit.
A "yet" is worse: it is true when written, silently false the day the
thing lands, and nothing about the sentence changes to say so. Both
belong in a changelog, which is read as a record of a moment and is
never expected to describe the present.

That is also why this is a check of its own rather than a fourth mode of
[claim-words](claim-words.md). The two read sentences the same way and
report the same way, but they want opposite file sets: a changelog and
release notes are where a project's totalising sentences are worth
holding to account and where its temporal wording is exactly correct.
One `files` key cannot mean both.

## Example

The example is a committed reference page, a `claims.toml` that
designates the directory it sits in, and a pending edit that extends it.

`examples/temporal-words/history/01-documents/docs/reference.md`:

```markdown
{{#include ../../examples/temporal-words/history/01-documents/docs/reference.md}}
```

`examples/temporal-words/claims.toml`:

```toml
{{#include ../../examples/temporal-words/claims.toml}}
```

The edit adds a section with one sentence in each shape the check
reports, alongside the shapes it declines: a two-component version, a
version inside a code span, a version inside a fenced block, and the
same dated sentence under each of the two retirement markers. It also
adds a changelog, which the configuration does not designate:

`examples/temporal-words/docs/reference.md`:

```markdown
{{#include ../../examples/temporal-words/docs/reference.md}}
```

`examples/temporal-words/CHANGELOG.md`:

```markdown
{{#include ../../examples/temporal-words/CHANGELOG.md}}
```

Run with that edit staged, the check reports:

```
{{#include ../captures/temporal-words.txt}}
```

The first three findings are the three modes, one each: the release the
TOML reader arrived in, the output mode that does not exist yet, and the
citation that reads differently now. The Docker version is two
components and is another project's; the pinned image and the fenced
`version` line are syntax the page is showing. The fourth finding is the
callout, which this check does not treat as a retirement marker — the
italicised sentence and the "Previously said:" lead-in below it are the
two that do suppress. The changelog's own "now" and "previously" are in
a file the configuration does not name, and are the wording that file is
for.

Without the `claims.toml`, the same edit reports nothing. That is why
the file is shown rather than described: a project that has not written
one has this check installed and inert.

The fix, where one is needed, is to write the sentence in the present
tense and move the date to the changelog: "reads native TOML" rather
than "reads native TOML since 0.3.0", and a sentence deleted rather than
a "yet" left behind.

## Configuration

```toml
[temporal-words]
files = ["docs/*.md", "README.md"]
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `files` | list of glob strings; a bare string is a one-element list | `[]`: nothing is swept | Always, since the check reads nothing until this names a file. List the pages that describe what the software does now: a documentation site's own source, a README, a manual. Leave out the changelog, the release notes and anything else written as a record of a moment — that prose is dated on purpose. A file not listed is never read, whatever it says. |

There is no `exclude`. `files` is the only scope the check has, and a
file outside it is already excluded.

A glob here is matched against the whole path with `*` spanning `/`, so
a pattern like `docs/*.md` reaches every page below `docs/` as well as
the ones directly in it. Name the pages individually where that is not
what you meant.

`enabled`, which takes this check out of the commit gate while leaving it
in the on-demand skill and the CLI, is shared by every check and covered
on [Configuring `claims`](../configuring.md#silencing-one-check-at-commit-time).

## Retirement markers

Two of the three. A sentence is skipped when the whole sentence is
wrapped in `*asterisks*` or `_underscores_`, or when it opens with the
lead-in "Previously said:", in any case. A Markdown blockquote does not
skip it, and that is the one place this check differs from
[claim-words](claim-words.md).

The [retired-quote exemption](../concepts.md#the-retired-quote-exemption)
is decided per check against the prose that check reads. In a record-like
file a `>` means "here is what we used to say". In the reference prose
this check reads, a `>` is a callout: the claim the author wants read
first, and a live one. The reasoning and the measurement behind dropping
it are in [ADR
0003](../../decisions/0003-retirement-markers-are-scope-dependent.md).

## Next

[judgment-agent](judgment-agent.md), which works out which claims a
diff has put in doubt and hands each to a subagent that reads the code.
