# check-config-defaults

A sentence that states a setting's default value, "`TIMEOUT` defaults to
`30`", beside code in which the default is something else. The check
reads the line of code the project has mapped the setting to and looks
for the stated value in it. A value the line does not contain is an
advisory finding: the sentence and the code disagree, and someone should
look, but which of the two is wrong is not the check's to say. A setting
the project has not mapped is never looked at, and a project maps nothing
until it writes the mapping, so the state every project starts in is one
where this check reads every claim and verifies none.

## What it checks

A **claim** is one line of tracked Markdown holding, in order: a
backticked setting name, one of four fixed phrases, and a backticked
value. The phrases are `defaults to`, `default is`, `defaulting to` and
`default:`, matched without regard to case. Both backtick spans are
required. "`STATION_NAME` defaults to the AI Radio station" states a
default and is not a claim, because the value is prose rather than an
exact string; a statement split across two lines is not a claim either.
The phrase list has no configuration surface, because widening it would
trade away the precision that makes the comparison honest: a claim that
states its value exactly is the only kind a substring test can be
trusted with.

Whether a claim is checked at all depends on the **mapping**, which is
the check's own section of `claims.toml`: each key is a setting name, and
its value names where the real default lives, as a file and a line or a
file and a short inclusive range of lines. A claim naming a setting with
no entry is out of scope and produces nothing, not a finding. With an
empty section, or no section, nothing is in scope. The
[configuration](#configuration) below shows the shape, and the
[example](#example) shows one at work.

Comparison is a substring test. The claimed value, with only its own
surrounding quote characters stripped, must appear somewhere in the raw
text of the mapped lines. The code side is not normalised at all: a claim
of `ai_radio` matches a line reading `STATION_NAME = "ai_radio"` because
the bare characters are there inside the quotes, not because either side
was parsed. A mapped file that does not exist, or a range beyond the end
of it, is reported as not containing the value, with the message saying
that nothing was found there rather than quoting a line; it does not say
which of the two it was.

The substring test cuts both ways, and the check accepts that rather than
parse code. A claimed `30` passes against a line reading `TIMEOUT = 300`;
a claimed value equal to the setting's own name passes unconditionally,
since the mapped line always contains it. A mapping entry also stays
where it was written: when the default moves to another line and the
entry is not updated, the check compares against whatever now sits at
the old line and quotes it in the finding, which is the one signal that
the mapping has gone stale.

A mapping entry not shaped `path:line` or `path:start-end`, with 1-based
lines and a start no greater than its end, is a configuration error,
reported as a crash of the check rather than skipped.

The check is whole-tree, over every line of every tracked `.md` file on
every run, except lines inside a fenced code block: a block showing the
claim syntax is an example rather than a claim. It runs no command; the
mapped lines are read as text.

## Why it exists

A stated default is the most precise claim documentation makes about
configuration, and the one most quietly falsified: a timeout is doubled
in the code and the sentence quoting the old value stays, still exact,
still confident. No other check reads a value. A citation check asks
whether `TIMEOUT` exists, not what it is set to. The price of verifying
the value is that the project says where each default lives, which is
also why nothing here has to guess at a project's structure.

## Example

The example is a Markdown file, a source file, and the `claims.toml` that
connects them. The Markdown makes two claims the mapping covers, one true
and one false, one claim it does not cover, and one statement that is not
a claim at all.

`examples/check-config-defaults/README.md`:

```markdown
{{#include ../../examples/check-config-defaults/README.md}}
```

`examples/check-config-defaults/src/config.py`:

```python
{{#include ../../examples/check-config-defaults/src/config.py}}
```

`examples/check-config-defaults/claims.toml`:

```toml
{{#include ../../examples/check-config-defaults/claims.toml}}
```

Run against a fresh repository holding those three files, the check
reports:

```
{{#include ../captures/check-config-defaults.txt}}
```

The finding is the timeout: the claim says `30`, the mapped line says
`60`, and the message quotes the line so the disagreement is visible
without opening the file. The station name is a claim too, and passes:
its value is quoted in the prose, the quotes are stripped, and `ai_radio`
sits inside the mapped line. The log level is a claim the check reads
and has no mapping for, so it is out of scope even though the source
file plainly states it. The retry count is stated without a backticked
value and is never a claim.

Without the `claims.toml`, the same run reports nothing. That is why the
mapping is shown here rather than described: a project that has not
written one has the check installed and inert.

The fix for the finding is to correct whichever side is wrong, the
sentence or the code, or to move the mapping entry if the default has
moved.

## Configuration

```toml
[check-config-defaults]
STATION_NAME = "src/config.py:42"
TIMEOUT = "src/settings.py:40-45"
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| any setting name | `"path:line"` or `"path:start-end"`, 1-based and inclusive, with the start no greater than the end; anything else is a configuration error | no entries: every claim is out of scope | The project's prose states a default in the checkable shape, a backticked name and a backticked value around one of the fixed phrases, and the project wants it held to the line of code that sets it. One entry per setting; a setting with no entry is never checked, however often it is claimed. |

There is no `exclude`. The mapping is the only scope the check has: a
claim about a mapped setting is checked wherever it appears, and a claim
about anything else is checked nowhere.

`enabled`, which takes this check out of the commit gate while leaving it
in the on-demand skill and the CLI, is shared by every check and covered
on [Configuring `claims`](../configuring.md#silencing-one-check-at-commit-time).

## Retirement markers

None. A claim inside a blockquote, an italicised sentence, a paragraph
opening "Previously said:" or a fenced code block is read like any other
line. The [retired-quote
exemption](../concepts.md#the-retired-quote-exemption) skips a sentence
quoted in order to retire it; this check has no exemption of its own,
and a sentence about a mapped setting's former default is kept out of
its reach by stating the old value as prose rather than as a backticked
string.

## Next

[check-env-vars](check-env-vars.md), which holds a backticked environment
variable name to the files a project says define its environment.
