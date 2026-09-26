# check-links

Every internal Markdown link in every tracked `.md` file resolves: the
file or directory it names is tracked by git, and where it names a heading
anchor in a Markdown page, a heading in that page has that anchor. A link
that fails either test is a gate finding. The claim "this page exists,
with this section" has been disproved, and the commit is refused until it
holds again.

## What it checks

Every link destination without a scheme is in scope: another `.md` file,
with or without a `#anchor`; a bare `#anchor` into the file it appears in;
a source file, a script, or an image (`![alt](img.png)`); and a directory
(`[scripts](scripts/)`). A destination with a scheme (`https://`,
`mailto:`) is out of scope and never reported. So is a link inside a fenced
code block or an inline code span, which is example syntax rather than a
link.

The destination is resolved against the directory of the page it appears
in, and what it names must be tracked by git. A file that is on disk but
never added, or is git-ignored, is missing from every other clone, so a
link to it is a finding like a link to nothing. A directory counts when
git tracks at least one file under it. A link to a symlink, such as a
`CLAUDE.md` pointing at `AGENTS.md`, is followed, provided it stays inside
the repository, and so is a link through a symlinked directory. A link to
a file deliberately kept out of git is what `known_untracked`, below, is
for.

An anchor is checked only on a Markdown page. On any other target it names
a line or a viewer position, as in `claims/cli.py#L10`, and only the path is
checked.

A destination starting with `~` or `/` is out of scope too, much as
[check-file-refs](check-file-refs.md) sets aside a host path. Such a
destination is not relative to the page, so resolving it against the
page's directory could only report it as broken for the wrong reason. A
leading `~` names a home directory. A leading `/` may name a place on the
host or, as GitHub reads it, the repository root, and nothing in the link
says which, so neither is checked: write a link relative to the page if
you want it held to this check.

An anchor matches a heading under GitHub's rule: the heading text is
lowercased, every character outside letters, digits, spaces, hyphens and
underscores is dropped, and each space becomes a hyphen. `## Upgrading an
install` is reached by `#upgrading-an-install`, and `## claims.toml` by
`#claimstoml`. Two headings with the same text produce the same anchor,
and a link to it is satisfied by either.

The check is whole-tree. It reads every tracked `.md` file on every run,
not only the files the commit touched, so a link broken by a rename
elsewhere is reported on the next commit whatever that commit was about.

## Why it exists

A relative link is the narrowest claim a document makes about its own
tree: this file, this heading, right here. It is also the claim most often
made false by an edit somewhere else. A page is renamed, a heading is
reworded, and a sentence three directories away that nobody opened now
points at nothing. Reporting it as a gate on the very next commit puts the
finding in front of the person who made the change while they still hold
the context to fix it.

## Example

The example is two files. The first links to the second three times, to
a page that does not exist, to its own title, to a directory and to a
script, and also carries an external URL and link syntax written as code.

`examples/check-links/README.md`:

```markdown
{{#include ../../examples/check-links/README.md}}
```

`examples/check-links/docs/setup.md`:

```markdown
{{#include ../../examples/check-links/docs/setup.md}}
```

Run against a fresh repository holding those two files, the check reports:

```
{{#include ../captures/check-links.txt}}
```

The first finding is a missing file: nothing in the example is named
`configuration.md`. The second is a file that exists with a heading that
does not: the setup page's heading is `## Upgrading`, whose anchor is
`#upgrading`, and no rule maps the longer anchor onto it. The third is a
script that does not exist, held to the same test as a page. The link to
`#installing` resolves, as do the bare `#widget` link to the page's own
title, the setup page's own `#installing`, and the `docs/` directory,
which holds the setup page. The external URL and the code span produce
nothing, because neither is a link this check reads.

Every finding names the file and line of the link, so the fix is either to
retarget the link or to restore what it named.

## Configuration

```toml
[check-links]
exclude = ["docs/legacy/*.md"]
known_untracked = [".claude/settings.local.json"]
historical = ["CHANGELOG.md", "RELEASES.md", "decisions/*.md"]
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `exclude` | list of glob strings; a bare string is a one-element list | `[]`, nothing excluded | A file's links should not be validated at all: a tutorial whose example deliberately links to a heading that does not exist yet, or a directory of inputs written to be broken, like this site's own examples. An excluded file is skipped whole, live parts included. |
| `known_untracked` | list of glob strings; a bare string is a one-element list | `[]`, every target must be tracked | A link names a file that is real but deliberately never added to git, such as a git-ignored per-machine settings file, and should not gate like a link to nothing. A match must still exist on disk inside the repository, and a Markdown page reached this way still has its anchor checked. |
| `historical` | list of glob strings; a bare string is a one-element list | `[]`, every link resolves against the working tree | A file is an append-only record, such as a changelog or a set of decision records, whose shipped entries your own rules forbid editing, and you still want to rename or restructure the pages it links to. |

A `historical` file's links get one more chance. A link that fails against
the working tree is re-resolved against the tree at the commit that wrote
its line, as `git blame` attributes it, and passes if it held there: for a
Markdown page, that the page and its heading were in that commit's tree;
for anything else, that a file or directory was at that path.
`known_untracked` plays no part in that second lookup, since a file never
added to git is in no commit's tree. The record's shipped entries stay
what they were without leaving a stub heading behind at every old
destination. A link that held nowhere is still a finding, and its message
says both where it was tested: not in the working tree, nor at the commit
where the line was written, named by its short hash.

Three consequences follow, and all three are the same rule read
consistently rather than special cases:

- An uncommitted line resolves against the working tree like any other
  file. A changelog's unreleased section, being written now, stays fully
  gated.
- A line a later commit touched is attributed to that commit and must
  hold as of it. Deliberately retargeting an old link, should your rules
  allow one, is checked against the tree it was retargeted in.
- A line older than the commit that first added `claims.toml` is skipped
  when it fails. It was written before anything gated it, may have been
  broken then, and the append-only rule means nothing can fix it now. A
  project with no tracked `claims.toml` has no cutoff, and every line is
  checked.

The working-tree check always runs first and history is consulted only on
a failure, so a project whose records all still resolve pays nothing for
listing them. The reasoning behind the mechanism, and the alternatives it
was chosen over, are in
[ADR 0002](../../decisions/0002-historical-links-resolve-at-their-own-commit.md).

`enabled`, which takes this check out of the commit gate while leaving it
in the on-demand skill and the CLI, is shared by every check and covered
on [Configuring `claims`](../configuring.md#silencing-one-check-at-commit-time).

## Retirement markers

None. A link is checked wherever it appears, including inside a
blockquote, an italicised sentence, or a paragraph opening "Previously
said:". The
[retired-quote exemption](../concepts.md#the-retired-quote-exemption)
exists for a sentence quoted in order to retire it, and a link is a
pointer rather than a sentence: quoting an old claim does not need the
page it pointed at to stay put. A record that must keep old links intact
is what `historical` is for.

## Next

[check-file-refs](check-file-refs.md), which holds a bare path mention in
prose to the same standard this check holds a link.
