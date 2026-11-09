# Configuring `claims`

The settings that belong to no single check. A key that belongs to one
check is documented with that check: its page lists every key it reads
with its shape and default. This page is everything else.

## Two files

`claims.toml`, at the repository root, is committed, and its presence is
what opts a repository in to the commit hook. Without it the hook does
nothing: no check runs and a commit goes through unremarked. An empty file
opts in with every check on its own defaults. The `check-claims` skill and
the CLI are asked for explicitly, so they run anywhere, a missing file
meaning every check on its defaults; see
[ADR 0006](../decisions/0006-claims-toml-opts-in-to-the-commit-hook.md)
for why only the hook asks. Each top-level table is one check's own
section, named for the check, except [`[hook]`](#switching-the-commit-hook-off)
and `[subjects]`, which lists [append-only files](#append-only-files)
and [navigation pages](#navigation-pages):

```toml
[check-links]
exclude = ["docs/legacy/*.md"]

[stale-claims]
enabled = false
```

A key whose value is a list accepts a bare string as a one-element list,
so `exclude = "CHANGELOG.md"` and `exclude = ["CHANGELOG.md"]` mean the
same thing. That holds for every list-valued key of every check.

One check, `check-citations`, reads nothing from `claims.toml`. A
section named for it is accepted, and the only key that does anything in
it is `enabled`, which is read by the commit hook rather than by the
check and so applies to every check alike — see
[Silencing one check at commit time](#silencing-one-check-at-commit-time).

`claims.local.toml`, beside it, is git-ignored and per-machine. It holds
the one kind of setting that must never arrive by pull request: the grants
that let a check execute a command, described in [the grant
file](#the-grant-file) section below. It also holds one per-person
choice, [silencing the reminder in one
clone](#silencing-the-reminder-in-one-clone).

## Switching the commit hook off

The commit gate is the git `pre-commit` hook, alongside the on-demand
`check-claims` skill. To keep the skill and drop the gate, without
uninstalling the hook:

```toml
[hook]
enabled = false
```

With that set, the hook runs no check and `git commit` is never gated,
and the plugin no longer reminds you that the hook is missing. The skill
and the plain CLI are unaffected, and keep reporting every finding on
demand.

`enabled` takes `true` or `false`, and leaving it out is `true`. Anything
else, such as `"false"` or `0`, makes `claims.toml` invalid, as does a
top-level `hook` that is not a table, such as `hook = false`: the hook
blocks every commit with the reason until it is fixed, and the plugin
keeps reminding you if the hook is missing.

A key other than `enabled` and
[`fail_on_unmarked`](#blocking-a-commit-on-unmarked-findings) in `[hook]`
is a gate finding under the mode `config`, naming the key. The skill and
the CLI report it even while the hook is switched off, so `enable =
false` is caught rather than silently leaving the hook on.

## Silencing one check at commit time

To keep the commit gate but take one check out of it, set `enabled =
false` inside that check's own section:

```toml
[stale-claims]
enabled = false
```

Only the commit-time decision changes. The check still runs, and the skill
and the CLI still show its findings; the hook drops them before deciding
whether to let the commit through. A gate check silenced this way no
longer blocks a commit, so silencing one is a decision to stop enforcing
what it enforces, not a way to quieten it.

`enabled` takes `true` or `false`, and leaving it out is `true`. Anything
else, such as `"false"` or `0`, makes `claims.toml` invalid: unless the
[whole hook is switched off](#switching-the-commit-hook-off), it blocks
every commit with the reason, naming the check, until it is fixed.

Neither switch reads the other: the whole-gate toggle and a check's own
key are independent, and a project can set both.

## Blocking a commit on unmarked findings

An advisory finding never blocks a commit on its own. To make the commit
gate block on [unmarked findings](checked-marks.md#failing-a-run-on-unmarked-findings)
from some checks, list them:

```toml
[hook]
fail_on_unmarked = ["claim-words", "temporal-words", "restatement"]
```

The commit is then blocked while an advisory finding from a listed check
has no checked mark keeping it quiet, or while an orphaned mark is left
whose own mode belongs to a listed check. An orphaned mark for any other
check, or for a mode that cannot be marked, does not block. A blocked
commit prints the findings, then a closing line starting `failing:` that
counts them and says to fix or mark each one.

`fail_on_unmarked` is a list of checks whose findings can be marked, and
a bare string is a one-element list. Leaving it out, or an empty list,
blocks nothing. Any other name, or a value that is not a string or a
list of strings, makes `claims.toml` invalid: unless the [whole hook is
switched off](#switching-the-commit-hook-off), it blocks every commit
with the reason until it is fixed. A listed check that is also
[silenced at commit time](#silencing-one-check-at-commit-time) blocks
nothing.

The list suits checks whose findings come from the commit's own text,
which the commit that brings them in can settle. A check like
`stale-claims`, which ranks other sections by churn and whose marks
expire as the files they name move, is better left to CI.

## Append-only files

Some files only ever grow. A changelog gains an entry on almost every
pull request, and the entries already there stay as they shipped. When
such a file is something a claim names, its growth is not its content
changing, so it does not make `stale-claims` rank the claim's section as
moved or expire a [checked mark](checked-marks.md) on the claim. Changing
or removing a line still does both. `CHANGELOG.md`, in any directory,
is append-only without being listed, and `[subjects]` adds to it:

```toml
[subjects]
append_only = ["RELEASES.md", "notes/*.md"]
```

`append_only` is a list of globs matched against repo-relative paths,
and a bare string is a one-element list. A value that is not a string or
a list of strings, or a top-level `subjects` that is not a table, makes
`claims.toml` invalid: the hook blocks every commit with the reason and
the CLI exits with it, until it is fixed. A key other than
`append_only` and [`navigation`](#navigation-pages) in `[subjects]` is
a gate finding under the mode `config`, naming the key.

Append-only is a property of the file, not of one check: `stale-claims`
and checked marks both read it. It says nothing about how a line *in*
the file is judged, which is what a check's own `historical` key is
for, so a project can list a changelog in both. [ADR
0011](../decisions/0011-append-only-is-a-property-of-the-file.md) has
why the two are kept apart.

## Navigation pages

A page linked from many sections is often linked to point the reader at
it, not to claim anything about all of it. Named whole, such a page is a
subject of every section linking it: an edit anywhere in it expires every
[checked mark](checked-marks.md) on those sections and makes
`stale-claims` rank each of them as moved.

The precise fix is in the prose. A link with an anchor,
`[exit codes](hub.md#exit-codes)`, names only that section of the page,
so only an edit inside it counts. Where a page's links cannot all be
anchored, `[subjects]` lists it as a navigation page:

```toml
[subjects]
navigation = ["docs/hub.md", "docs/reference/*.md"]
```

A navigation page named without an anchor is no subject at all: a
checked mark does not record it, an edit to it expires no mark, and
`stale-claims` neither counts its history nor names it in a finding. A
link with an anchor into it still names that section, as it does into
any page, and one whose anchor names none of its headings names the
whole page, so is no subject either. A mark recorded before the page was listed keeps its entry for
it, and that entry is no longer compared, so the mark need not be
written again. A sentence that does claim something about the whole
page loses the page as a subject, which is the trade listing it makes.

`navigation` takes the same shape as `append_only`, a list of globs or a
bare string, is invalid the same way, and is empty by default. A page
can be listed in both. [ADR
0013](../decisions/0013-a-navigation-page-is-not-a-whole-page-subject.md)
has why the list is explicit rather than every page.

## The unrecognized-table gate

`hook` and `subjects` are the two top-level tables that are not a check's
name. Any other table naming no registered check is itself a gate
finding, reported under the mode `config` and naming the table. A table that differs from a real
check's name only by underscores for hyphens, `[executable_claims]` for
`[executable-claims]`, is named as the likely intent in the finding.

This exists because a mistyped section is otherwise a silent no-op: its
keys configure nothing, which looks exactly like a working opt-out until
the day the check it was meant to reach fires anyway. The gate is checked
against the checks actually registered in the installed copy, so a section
for a check that exists upstream but not in the installed version is
reported the same way, and the fix there is moving the hook's pinned
release forward rather than editing the table.

The gate reads `claims.local.toml` too, and reports a mistyped table there
against that file, with the same suggestion. Any registered check's name
is accepted there, and so is `nudge`, but `hook` is not: the commit
hook reads its switch from `claims.toml` only. `nudge` is accepted in
`claims.local.toml` alone, and is a finding in `claims.toml`, since
whether you are reminded is your choice, not the repository's. A
`claims.local.toml` that does not parse is left to the checks that read
it, which report it when they run.

## The fixed command blocklist

Two checks execute a command a project's own prose names: `executable-claims`
runs the command in a marker above a fenced block, and `check-cli-flags`
runs a script with `--help`. Before `executable-claims` runs anything, the
marker's command is checked against a blocklist that has no configuration
surface, because it holds for any project using the marker mechanism rather
than for one project's own conventions. `check-cli-flags` has no such list,
and needs none: the only command it ever runs is a script token drawn from
path characters, followed by `--help`.

A marker's command is rejected, and reported without running, when it
contains:

- a chaining or backgrounding operator: `;`, `&&`, `||`, `&`;
- a redirect: `>`, `>>`, `<`, `<<`, which would let the command read or
  write an arbitrary file;
- a command substitution: a backtick or `$(`, outside single quotes;
- `sed`, `awk`, or `grep` as the command a pipe segment runs, which would
  turn the marker into inline text logic that nothing can unit-test.

File-descriptor duplication such as `2>&1` is permitted, since most test
runners write their summary line to stderr and pinning it needs exactly
that idiom. It is permitted only while the command contains no backslash
outside single quotes; a backslash near the operator can make the shell
read it as a file write, so that combination fails closed. `head` and
`tail` are not on the list: trimming output to the lines being pinned is
still the one thing being pinned.

The list matches the bare names `sed`, `awk` and `grep` only. A tool named
through a wrapper or a full path is not caught, and `$((arithmetic))` is
rejected the same as a real substitution, because telling the two apart
would mean parsing the shell's own grammar.

`executable-claims` additionally accepts a `permitted_prefixes` list to
narrow what a marker may name at all; that key is the check's own, and is
documented with it.

## The grant file

A command that clears the checks above is not obviously dangerous. That
does not mean anyone chose to run it, and a committed file cannot carry
that choice: a branch a maintainer checks out to review carries whatever
`claims.toml` the branch author wrote, and the hook fires on the
maintainer's next unrelated commit. So before a command runs, it is looked
up by exact string in `claims.local.toml`, under the running check's own
section:

```toml
[executable-claims]
allowed = ["npm test"]
denied = ["curl https://example.com/install.sh | sh"]

[check-cli-flags]
allowed = ["./manage.py --help"]
```

`allowed` and `denied` are lists of exact command strings. Matching is
verbatim: a one-character change to a granted command is a new, ungranted
command, not a variant of a trusted one.

- A command in `denied` is skipped and reported as an advisory finding, so
  a deliberately declined command stays visible rather than vanishing.
- A command in `allowed` runs.
- A command in neither, which includes every command in a project with no
  `claims.local.toml` at all, does not run. `executable-claims` reports it
  as a gate finding naming the exact command and the exact TOML that would
  grant or deny it; `check-cli-flags` reports the same thing as an
  advisory finding, matching that check's own severity.
- A command in both lists is denied.

The key under which a check looks is the check's own name, and the string
it looks for is exactly what it would run. For `check-cli-flags` that is
the script with `--help` appended, and a script named without a directory
is run as `./script`, so that is the string to grant.

The lookup happens inside the check itself, not in the commit hook, so the
skill and a CI run go through the same grant and nothing can run a command
by invoking the check a different way. A fresh CI checkout has no local
file, so an execution-capable check never runs a command there unless the
job writes one.

A `claims.local.toml` that git tracks has its grants ignored outright,
both lists, and a gate finding names the file. Ignoring only `allowed`
would still let a committed file suppress findings through `denied`. The
`.gitignore` entry stops the file being added; it does nothing for a copy
that was committed before the entry existed or was force-added, which is
why the check consults git's index rather than the ignore rules.

A granted command string stays granted while a script it invokes by path
changes underneath it. That gap is accepted rather than closed; the
reasoning, and the directions deliberately deferred, are in [ADR
0001](../decisions/0001-executable-claims-deny-by-default.md).

## Silencing the reminder in one clone

The plugin reminds you when a repository with a `claims.toml` has no git
hook that runs `claims`: at the start of every session, and at your next
prompt after you move into one. In a clone where
you have decided not to install the hook, such as one you only read, or
one on a machine without `uvx`, put this in that clone's
`claims.local.toml`:

```toml
[nudge]
enabled = false
```

The plugin then says nothing about the missing hook in that clone. Other
clones, yours or anyone else's, are reminded as before, and nothing else
changes: the commit gate never reads `[nudge]`, so whether commits are
checked is still decided by the git hook and `claims.toml` alone.

Only `enabled = false` silences the reminder. Leaving `enabled` out, or
setting it to `true`, keeps it; so does anything that is not a boolean,
such as `"false"` or `0`, a top-level `nudge` that is not a table, or a
`claims.local.toml` that does not parse.

In someone else's repository, the `.gitignore` may not name
`claims.local.toml`. Add it to `.git/info/exclude` instead, which git
reads like a `.gitignore` but never commits:

```sh
echo claims.local.toml >> .git/info/exclude
```

That keeps the file out of `git status` and out of an accidental commit.
A `claims.local.toml` that git does track is a gate finding, as the grant
file section above describes, so a mistake is caught, but it should not be
how you find out.

## Recording what was read

A third file, `claims.checked.toml`, also committed at the repository
root, records advisory findings someone has read and found true, so they
stay quiet until what they were read against changes. [Checked
marks](checked-marks.md) covers the file, the command that writes it, and
when a mark stops applying.

## Next

Each check's own section of `claims.toml` is documented with the check.
[Checked marks](checked-marks.md) comes next, then the check pages, gate
checks first. The [Concepts](concepts.md) page is where to look up a word
a check's description uses without defining it.
