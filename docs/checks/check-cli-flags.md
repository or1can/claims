# check-cli-flags

A sentence naming a script and, in the same breath, a flag it accepts.
The check runs the script with `--help` and looks for the flag in what it
printed. A flag the help text does not mention is an advisory finding:
the prose promises an option the script does not advertise, and someone
should look. Before anything runs, though, the script has to be one this
machine's owner has chosen to run, and in a fresh checkout none is, so
the state a reader meets first is the check asking for that choice.

## What it checks

A **claim** is one line of tracked Markdown carrying, in backticks, both
a script and a flag. The two may share one span, as a full invocation,
or sit in two spans on the same line:

```markdown
Build it with `scripts/build.py --release`.
The `manage.py` script accepts `--verbose`.
```

A **script** is a path-shaped token ending in a recognised script
extension: `.py`, `.sh`, `.rb`, `.js`, `.ts` or `.pl`. A **flag** is a
`--word` or a single-letter `-x`. A bare command name with no extension
is never a script, so a sentence about `npm`, `docker` or `git` is not a
claim: without an extension there is no way to tell a tool's name from
any other backticked word, and guessing wrong would mean running an
arbitrary word as a command. A flag with no script on its line is not a
claim either, since nothing says which of a project's entry points it
belongs to. A claim inside a fenced code block is not read.

For each claim the check builds one command: the script, followed by
the help flag.

A script named without a directory, `manage.py`, is run as
`./manage.py` <!-- example -->, so the lookup is pinned to the repository
root rather than to whatever same-named binary the path might hold. The
command is then looked up, as an exact string, in `claims.local.toml`,
and this is where a fresh checkout stops. The grant mechanism is shared
with `executable-claims` and documented once, on [the grant
file](../configuring.md#the-grant-file) section of the Configuring page;
this page does not repeat it. The one difference is severity: a command
with no grant is an advisory finding here, matching the rest of the
check, where `executable-claims` reports the same state as a gate. A
`claims.local.toml` that git tracks is the exception in the other
direction, the one gate finding this otherwise advisory check produces,
because a committed grant file is a compromise indicator whatever the
check's own severity.

A granted command runs from the repository root, under a timeout, and
the outcome is one of three. A clean exit whose combined output mentions
the flag as a whole token, not as a prefix or substring of a longer one,
is a pass, so `--norm` does not pass on the strength of `--normalize`. A
clean exit whose output does not mention it is the finding this check
exists for. A non-zero exit or a timeout is inconclusive, reported as
"could not be verified" rather than as false, because no answer is not a
wrong one. A script whose help text itself exits non-zero is therefore
inconclusive on every run, and the way to stop it re-asking is a
`denied` entry, which keeps it visible as an advisory finding. Each
distinct command runs once per invocation, however many claims name it.

Verification is only as complete as the help text. A framework that
truncates its help, or lists a flag only under a subcommand, leaves a
real flag unfound through no fault of the claim, and `--help` is the only
introspection the check knows.

The check is whole-tree, over every tracked `.md` file on every run.

## Why it exists

A flag is documented once and renamed in the parser. The sentence that
named it keeps reading like a fact, and a reader who copies it gets an
error from the script rather than from anything that read the sentence.
A citation check sees declarations, and a flag is not one. Asking the
script itself is the only test there is, and asking through `--help` is
the one question nearly every command-line framework answers the same
way, which is what lets the check stay this narrow.

## Example

The example is a Markdown file and two scripts. The file makes one claim
in each shape, names a bare command that is never a claim, and shows an
invocation inside a fenced block. The build script accepts the flag its
claim names; the management script does not accept the one its claim
names.

`examples/check-cli-flags/README.md`:

````markdown
{{#include ../../examples/check-cli-flags/README.md}}
````

`examples/check-cli-flags/scripts/build.py`:

```python
{{#include ../../examples/check-cli-flags/scripts/build.py}}
```

`examples/check-cli-flags/manage.py`:

```python
{{#include ../../examples/check-cli-flags/manage.py}}
```

Run against a fresh repository holding those three files, with no
`claims.local.toml` beside them, the check reports:

```
{{#include ../captures/check-cli-flags.txt}}
```

This is the ungranted state, the one every fresh clone, colleague's
checkout and CI runner is in, and each finding gives the exact TOML that
would grant or deny its command. Nothing ran to produce them, which is
also why the capture is identical on any machine; a granted run would
need a `claims.local.toml` no repository can commit, for the reasons the
grant file section gives. The second finding shows the `./` the check
adds to a script named without a directory, and that string, not the
bare name, is what a grant has to list. The package manager line is
never a claim, and the fenced invocation is not read.

Once both commands are granted, the build script's claim reports
nothing, because its help text lists the flag, and the management
script's claim reports that the script does not appear to support the
flag: the command succeeded and never mentioned it.

## Configuration

```toml
[check-cli-flags]
exclude = ["docs/legacy/*.md"]
timeout = 15
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `exclude` | list of glob strings; a bare string is a one-element list | `[]`, nothing excluded | A file's script-and-flag claims should not be checked at all: prior-art notes naming scripts from another layout, or a directory of inputs written to be broken, like this site's own examples. An excluded file is skipped whole. |
| `timeout` | number of seconds, integer or float; `true` and `false` are rejected rather than read as `1` and `0` | `10` | A script's help text is slow to appear, a cold build or a heavyweight interpreter, and keeps reporting an inconclusive timeout at the default. There is no per-script override, so this is set for the project. |

The grant lists, `allowed` and `denied`, are not keys of this section.
They live under the same table name in `claims.local.toml`, and are
documented once, on the [Configuring
`claims`](../configuring.md#the-grant-file) page.

`enabled`, which takes this check out of the commit gate while leaving it
in the on-demand skill and the CLI, is shared by every check and covered
on [Configuring `claims`](../configuring.md#silencing-one-check-at-commit-time).

## Retirement markers

None. A claim inside a blockquote, an italicised sentence or a paragraph
opening "Previously said:" is checked like any other. The [retired-quote
exemption](../concepts.md#the-retired-quote-exemption) skips a sentence
quoted in order to retire it; this check's unit is a script and a flag
rather than a sentence, and a claim that must not run on this machine is
recorded under `denied` in the grant file, which keeps it visible as an
advisory finding rather than hiding it.

## Next

[spliced-docs](spliced-docs.md), which reads Swift and Rust doc comments
for one that an insertion has pushed onto the wrong declaration.
