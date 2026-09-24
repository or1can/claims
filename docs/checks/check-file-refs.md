# check-file-refs

A bare mention of a path in prose, "run `scripts/build.py` <!-- example --> first",
that resolves to no tracked file. The mention is not written as a Markdown
link; it is a path-shaped run of text with a recognised extension, and
the sentence around it asserts that the file exists. When it does not,
that is a gate finding, and the commit is refused until the mention names
a file the repository has.

## What it checks

A **candidate** is a run of text shaped like a relative path: at least one
directory segment, a slash, and a final segment with an extension, where
the extension is in the recognised set. The default set covers the common
source, script, data and documentation extensions; the
[configuration](#configuration) below lists it, and a project adds to it
rather than replacing it. Text that is path-shaped but ends in something
outside the set, such as the `.0` of `api/v2.0`, is not a candidate and is
never reported. Neither is a bare filename with no slash, so "see
`README`" is not checked.

Four kinds of path-shaped text are set aside before resolution:

- the destination of a real Markdown link, which is
  [check-links](check-links.md)' to validate, so one broken reference does
  not produce two findings under two names;
- a URL, which is not a path however path-shaped its tail;
- a mention starting with `/` or `~/`, which names a place on the host
  rather than in the repository;
- a mention starting with `../`, which the check does not resolve either
  way.

A mention inside a fenced code block is not read, and nor is a fence's
own opening line, so an example path in a code sample is never a
candidate. A fence that is opened and never closed silences the rest of
its file here; that fence is reported by `executable-claims` over the
same sweep.

A candidate is resolved twice before it is reported: first against the
repository root, then, if that fails, against the directory of the file
that cites it. A page citing a sibling as `references/setup.md` <!-- example --> resolves
either way. This trades some precision for recall: a genuinely broken
root-relative mention passes if a same-named file happens to sit beside
the citing page.

A mention that names a real file the project deliberately never tracks,
such as a git-ignored per-machine settings file, is indistinguishable
from a typo by tracking alone. The `known_untracked` key names such paths
by glob; a candidate matching one is exempt from having to be tracked but
must still exist on disk inside the repository, so a typo under an
exempted pattern is still caught, and a symlink out of the repository is
refused rather than followed. It applies to the root-relative form only,
not to the citing-directory fallback.

The check is whole-tree, over every tracked `.md` file on every run.

## Marking a mention as an example

A path that is not meant to exist, a template such as
`decisions/NNNN-slug.md` <!-- example --> or a hypothetical
`plugins/extra.toml` <!-- example -->, is exempted by writing the HTML
comment `example` immediately after it. Only backticks and plain spaces or
tabs may sit between the mention and the marker; the marker's
own spelling is matched without regard to case or internal spacing. The
marker binds to one mention. It is not a configuration entry, because a
list in `claims.toml` has no structural link to the prose it exempts and
goes stale the day that prose changes.

A marker that does not immediately follow a live candidate has no effect,
and the check says so with an advisory finding at that line. That is the
one place this gate check reports advisory: an inert marker is not a
false claim, but it is a mechanism that has silently stopped working,
which is worth a line.

## Why it exists

A link is checked by [check-links](check-links.md). A path in backticks
with no link syntax around it makes the same claim, that this file is
here, and is at least as common, in a README's directory tour, a
changelog's "moved to", an agent instruction file's "read `x/y.md` <!-- example -->
first". Nothing read it. A citation-ranking check drops a path it cannot
resolve as noise, which is right for ranking and wrong for a claim.
Without this check, the bare mention is the one shape of file reference
that can be false forever without a finding.

## Example

The example is a Markdown file and one script. The file names the script
that exists and one that does not, and also carries the shapes the check
sets aside: a Markdown link, a URL, a host path, a version-number
lookalike, a marked hypothetical path, and a marker following nothing.

`examples/check-file-refs/README.md`:

```markdown
{{#include ../../examples/check-file-refs/README.md}}
```

`examples/check-file-refs/scripts/build.py`:

```python
{{#include ../../examples/check-file-refs/scripts/build.py}}
```

Run against a fresh repository holding those two files, the check
reports:

```
{{#include ../captures/check-file-refs.txt}}
```

The gate finding is the deploy script, named on the first line of prose
and present nowhere in the tree. The build script, named on the same line,
resolves and produces nothing. The release notes are a Markdown link,
which this check leaves to check-links; the installer is a URL; the
defaults file starts with `/`; and the endpoint reference ends in `.0`,
so none of those four is a candidate. The plugin settings file is a
candidate, and would be a finding, but carries an example marker and is
exempted.
The advisory finding is the last line's marker, which follows a sentence
rather than a path and so exempts nothing.

The fix for the gate finding is either to add the file the sentence
promises, retarget the sentence to a file that exists, or mark the
mention as an example if it was never meant to exist.

## Configuration

```toml
[check-file-refs]
exclude = ["docs/legacy/*.md"]
extensions = [".proto"]
known_untracked = [".claude/settings.local.json", "*.local.toml"]
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `exclude` | list of glob strings; a bare string is a one-element list | `[]`, nothing excluded | A file's bare path mentions should not be validated at all: prior-art notes discussing another project's tree, decision records quoting a layout that no longer exists, or a directory of inputs written to be broken, like this site's own examples. An excluded file is skipped whole. |
| `extensions` | list of extension strings, each with its leading dot; a bare string is a one-element list | the built-in set: `.py`, `.rs`, `.go`, `.js`, `.ts`, `.rb`, `.java`, `.c`, `.h`, `.cpp`, `.swift`, `.sh`, `.md`, `.txt`, `.yml`, `.yaml`, `.json`, `.toml` | The project's prose names a file type outside that set, such as `.proto`, and a bare mention of one should be held to the same standard. Entries are added to the built-in set, never substituted for it. |
| `known_untracked` | list of glob strings; a bare string is a one-element list | `[]`, every candidate must be tracked | A correctly cited file is real but deliberately never added to git, such as a git-ignored per-machine settings file, and should not gate identically to a typo. A match must still exist on disk inside the repository. |

`enabled`, which takes this check out of the commit gate while leaving it
in the on-demand skill and the CLI, is shared by every check and covered
on [Configuring `claims`](../configuring.md#silencing-one-check-at-commit-time).

## Retirement markers

None. A path mention is checked wherever it appears, including inside a
blockquote, an italicised sentence, or a paragraph opening "Previously
said:". The [retired-quote
exemption](../concepts.md#the-retired-quote-exemption) exists for a
sentence quoted in order to retire it, and a path is a pointer rather
than a sentence: a changelog entry saying a file moved is making a claim
about where it is now, and if the sentence is genuinely about a file that
is gone, the example marker says so for that one mention.

## Next

This is the last page. [Configuring `claims`](../configuring.md) holds the
settings shared across checks, and [Concepts](../concepts.md) the
vocabulary this page used without defining.
