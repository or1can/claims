# check-env-vars

A backticked name shaped like an environment variable, `DATABASE_URL`,
that appears nowhere in the files the project has said define its
environment. The check searches those files for the name as a whole word,
and a name none of them contains is an advisory finding: the prose names
something the project does not appear to have, and someone should look.
Until a project has named those files, though, there is nothing to
search, and the check reports nothing at all. That inert state is the
default, and it is the first thing to know about this check.

## What it checks

A **candidate** is a backticked token in tracked Markdown shaped
`ALL_CAPS_WITH_UNDERSCORES`: an uppercase letter first, then uppercase
letters and digits, with at least one underscore. The underscore is what
keeps a protocol acronym in backticks, `HTTP` or `TLS`, and an emphasised
word such as `NOTE`, from being read as a variable. A name that is not
backticked is never a candidate, however it is shaped. A candidate
inside a fenced code block is not read either, since a block showing a
variable being exported is an example rather than a claim.

The **scope** is the set of files a candidate is checked against: the
tracked file named exactly `.env.example` at the repository root, if
there is one, plus whatever the project lists under `definition_files`.
The files are read as plain text, whatever language they are in, and a
candidate passes when it appears in any of them as a whole word.

With no scope, the check is inert. No tracked `.env.example` and no
`definition_files` means there are zero files to search, and the check
produces nothing rather than searching the whole tree, because a bare
token matched against every source file would collide with any local
variable, class attribute or unrelated constant that happens to share
the name. A project that installs `claims` and does nothing else has this
check running and reporting nothing, and stays that way until it tracks
an example environment file or names its definition files. A scope that
exists but is empty, a tracked `.env.example` with nothing in it, is a
scope, and every candidate is then a finding.

Verification is existence, not value or use. The name has to appear
somewhere in the scope as text; nothing here understands what reading an
environment variable looks like in any language, and a variable consumed
only through a build tool's own configuration, or assembled from parts
at runtime, is unfound through no fault of the claim.

Detection is shape-only, and the noise runs both ways. A backticked
constant, enum value or regular-expression name that was never an
environment variable is a candidate exactly as a real one is, and is
reported if the scope does not mention it. The `exclude` key keeps a
directory of historical or illustrative prose out of the sweep for that
reason.

The check is whole-tree, over every tracked `.md` file on every run, and
runs no command.

## Why it exists

An environment variable is named in prose far more often than it is
declared anywhere: a README's setup section, a deployment note, an agent
instruction file. It is a naming convention rather than a declaration a
compiler sees, so a rename in the code leaves every mention behind and
nothing reports it. A citation check reads Swift declarations and cannot
see a name that was never declared in a language at all. Searching the
files a project says define its environment is the narrowest test that
can be honest about it.

## Example

The example is a Markdown file and an example environment file. The
environment file defines two names. The Markdown names both, names a
third the file does not define, and carries the shapes the check sets
aside: an unbackticked name, two backticked acronyms, and a name inside a
fenced block.

`examples/check-env-vars/.env.example`:

```sh
{{#include ../../examples/check-env-vars/.env.example}}
```

`examples/check-env-vars/README.md`:

````markdown
{{#include ../../examples/check-env-vars/README.md}}
````

Run against a fresh repository holding those two files, the check
reports:

```
{{#include ../captures/check-env-vars.txt}}
```

The finding is the cache lifetime, backticked in the prose and absent
from the environment file. The database URL and the station name are
candidates too, and pass, because the file defines both. The retry bound
is not backticked and is never a candidate; `HTTP` and `TLS` are
backticked and have no underscore; and the secret key is inside a fenced
block, where nothing is read.

The same two files with the environment file untracked, or absent,
report nothing, because the scope is then empty. That is the state a
project with no scope is in, and a capture of it would be blank.

The fix for the finding is to add the variable to the environment file,
or to list under `definition_files` the file that really does define it,
or to correct the sentence if the name is wrong.

## Configuration

```toml
[check-env-vars]
definition_files = ["src/*.py", "deploy/*.tf"]
exclude = ["docs/legacy/*.md"]
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `definition_files` | list of glob strings; a bare string is a one-element list | `[]`: the scope is `.env.example` alone, if tracked, and otherwise nothing | The names the prose uses are defined somewhere other than, or as well as, `.env.example`: the source that reads them, an infrastructure variable file, a container manifest. Entries are added to the built-in default, never substituted for it. Do not point this at the Markdown being swept: a mention that is also its own definition passes unconditionally, and the check is silently switched off for that file. |
| `exclude` | list of glob strings; a bare string is a one-element list | `[]`, nothing excluded | A file's backticked names should not be checked at all: prior-art notes, decision records naming another project's environment, or a directory of inputs written to be broken, like this site's own examples. An excluded file is skipped whole. |

`definition_files` names files to search, not prose to sweep. The key is
deliberately not called `files`, the name some checks use for the prose
they read, because here that name would mean the opposite thing.

`enabled`, which takes this check out of the commit gate while leaving it
in the on-demand skill and the CLI, is shared by every check and covered
on [Configuring `claims`](../configuring.md#silencing-one-check-at-commit-time).

## Retirement markers

None. A candidate inside a blockquote, an italicised sentence or a
paragraph opening "Previously said:" is checked like any other. The
[retired-quote exemption](../concepts.md#the-retired-quote-exemption)
skips a sentence quoted in order to retire it; this check's unit is a
name rather than a sentence, and a name that is genuinely about the past
is kept out of the sweep by writing it without backticks, inside a
fenced block, or in a file listed under `exclude`.

## Next

[check-cli-flags](check-cli-flags.md), which asks a script whether it
really accepts the flag a sentence says it does.
