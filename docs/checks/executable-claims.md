# executable-claims

A `verify` marker directly above a fenced block names a command, and the
block beneath it is a claim about what that command prints. The check
runs the command and compares what it printed, and how it exited, with
the block. A block the command no longer reproduces is a gate finding: the
claim "this command prints this" has been disproved, and the commit is
refused until the block and the command agree again. Before any command
runs, though, it has to be one this machine's owner has chosen to run,
which is where the rest of this page spends most of its time.

## What it checks

A marker is an HTML comment alone on its own line, and it is live when the
next non-blank line opens a fenced block:

````markdown
<!-- verify: npm test -->
```
Tests: 42 passed
```
````

The command runs through the shell, from the repository root, so a pipe
works. Its standard output and standard error are joined, standard output
first, and compared with the block after both sides have had trailing
whitespace removed, leading and trailing blank lines dropped, and the
block's common indentation stripped. A line in the block opening with a
`$ ` prompt is dropped before comparing, so a block may show the command
being typed above its output. A non-zero exit is a finding on its own,
whatever was printed.

A marker inside a fenced block is not live. It is shown as text, the way
the example above is, and nothing runs for it. A marker whose next
non-blank line is not a fence is malformed and is a finding, because a
marker with nothing to pin is a claim that has silently stopped being
checked. So is a fence that opens and never closes, reported at the line
that opened it, since everything after it would otherwise read as inside
the block.

The check is whole-tree: every tracked `.md` file on every run, with a
`CLAUDE.md` that is a symlink to `AGENTS.md` read once rather than twice.
A run in which no command was checked and nothing else was reported is
itself a gate finding, "no verify markers found in repo", because a
mechanism that has silently stopped checking looks exactly like one with
nothing to check. That finding is withheld only when `exclude` is the
reason nothing was swept.

Two departures from gate severity. A command that exceeds its timeout is
reported advisory, because a timeout is no answer rather than a wrong
one. A command listed under `denied` in the grant file is skipped and
reported advisory, so a marker somebody deliberately declined stays
visible instead of vanishing.

## Before a command runs

A marker's command passes three tests in order, and fails closed at the
first it does not pass. A command that fails any of them never runs, and
is reported as a gate finding naming the reason.

1. The fixed blocklist: chaining, redirection, command substitution, and
   piping through `sed`, `awk` or `grep`. It has no configuration and is
   the same for every project; [Configuring
   `claims`](../configuring.md#the-fixed-command-blocklist) lists it.
2. `permitted_prefixes`, if the project set one. The command must start
   with one of the listed strings. This is the check's own key and is
   covered under [Configuration](#configuration) below.
3. The local grant. The command, as an exact string, must appear under
   `allowed` in `claims.local.toml`, a file that is git-ignored and
   per-machine by design. [The grant
   file](../configuring.md#the-grant-file) on the Configuring page is the
   whole account of that mechanism, shared with the other check that
   executes what prose names; this page does not repeat it.

The first two tests decide whether a command is obviously unfit to run.
Only the third decides whether anyone chose to run it, and that is why it
cannot live in committed configuration: a branch checked out to review
carries whatever `claims.toml` its author wrote, and the commit hook fires
on the reviewer's next unrelated commit. The reasoning, and what was
considered and set aside, is in [ADR
0001](../../decisions/0001-executable-claims-deny-by-default.md).

## Why it exists

A block showing a command's output is the most concrete claim
documentation makes, and the most copied. It is pasted from a terminal
once, edited by hand when a flag is renamed, and trusted by every reader
after that because it looks like evidence. Nothing about the prose around
it says whether it was ever true. Running the command is the only test
there is, and running it on every commit puts the drift in front of the
person whose change caused it.

## Example

The example is one file with three markers. The first is well-formed and
names a command nothing on this machine has been asked to run. The second
pipes through `grep`. The third is followed by prose rather than a fence.

`examples/executable-claims/README.md`:

````markdown
{{#include ../../examples/executable-claims/README.md}}
````

Run against a fresh repository holding that file, with no
`claims.local.toml` beside it, the check reports:

```
{{#include ../captures/executable-claims.txt}}
```

This is the ungranted state, and it is the one every reader meets first:
a marker's command with no grant on this machine, which is what a fresh
clone, a colleague's checkout and a CI runner all have. The first finding
says so and gives the exact TOML that would grant or deny the command.
Nothing ran to produce it, and the example needs no local file, which is
also why it can be captured identically on any machine. A capture of the
granted state would need the capture to write a `claims.local.toml` of
its own first, because no repository can commit one: a committed grant
file is exactly the trust boundary the mechanism exists not to rely on,
and the check ignores the grants in any `claims.local.toml` that git
tracks.

The second finding is the blocklist, reached before the grant is even
consulted. The third is the malformed marker. Neither depends on any
local state either.

Once a command is granted, the same marker reports one of two things when
the block is wrong: that the command exited non-zero, naming the code, or
that its output no longer matches the documented block. Both name the
marker's file and line. A marker whose command and block agree reports
nothing, which is the state a granted, correct example sits in.

## Configuration

```toml
[executable-claims]
exclude = ["docs/generated/*.md"]
timeout = 60
permitted_prefixes = ["npm test", "./scripts/"]
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `exclude` | list of glob strings; a bare string is a one-element list | `[]`, nothing excluded | A file's markers should not be swept at all: a generated file, a page of examples of the marker syntax that a longer outer fence does not already cover, or a directory of inputs written to be broken, like this site's own examples. An excluded file is skipped whole. |
| `timeout` | number of seconds, integer or float; `true` and `false` are rejected rather than read as `1` and `0` | `30` | A legitimate command is a slow integration or cold-build step that keeps reporting an advisory timeout at the default. There is no per-marker override, so this is set for the project. |
| `permitted_prefixes` | list of literal string prefixes; a bare string is a one-element list | `[]`, no restriction beyond the blocklist | The project wants a narrower rule than the blocklist gives, such as "a marker may only run our own test suites or a script under our own scripts directory". |

A prefix is matched literally, with no glob expansion and no word boundary
after it. `"npm test"` also permits `npm test-anything-else`; a project
wanting the boundary includes it in the prefix, as `"npm test "`. An
empty list means the check has no way to know the project's conventions
and applies only the blocklist.

The grant lists, `allowed` and `denied`, are not keys of this section.
They live under the same table name in `claims.local.toml`, and are
documented once, on the [Configuring
`claims`](../configuring.md#the-grant-file) page.

`enabled`, which takes this check out of the commit gate while leaving it
in the on-demand skill and the CLI, is shared by every check and covered
on [Configuring `claims`](../configuring.md#silencing-one-check-at-commit-time).

## Retirement markers

None. The [retired-quote
exemption](../concepts.md#the-retired-quote-exemption) is a rule about
sentences a sweep reads, and this check reads no sentences: a marker is
either live, alone on its line above a fence, or it is not a marker.
A marker quoted to show the syntax is put inside a fenced block, and one
that must not run on this machine is recorded under `denied` in the grant
file, which keeps it visible as an advisory finding rather than hiding it.

## Next

[check-citations](check-citations.md), the check that holds a backticked
name to the symbols the repository has actually declared.
