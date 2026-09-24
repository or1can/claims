# Configuring `claims`

The settings that belong to no single check. A key that belongs to one
check is documented with that check, and its module docstring under
`claims/checks/` lists every key it reads with its default; this page is
everything else.

## Two files

`claims.toml`, at the repository root, is optional and committed. No file
at all means every check runs with its own defaults. Where present, each
top-level table is one check's own section, named for the check:

```toml
[check-links]
exclude = ["docs/legacy/*.md"]

[stale-claims]
enabled = false
```

A key whose value is a list accepts a bare string as a one-element list,
so `exclude = "CHANGELOG.md"` and `exclude = ["CHANGELOG.md"]` mean the
same thing. That holds for every list-valued key of every check.

Two checks, `check-citations` and `judgment-agent`, read nothing from
`claims.toml`. A section named for either is accepted and configures
nothing.

`claims.local.toml`, beside it, is git-ignored and per-machine. It holds
the one kind of setting that must never arrive by pull request: the grants
that let a check execute a command. The [grant file](#the-grant-file)
section below is the whole of what it holds.

## Switching the commit hook off

Installing the plugin gives a project both the on-demand `check-claims`
skill and the automatic gate on `git commit`. To keep the skill and drop
the gate, without uninstalling:

```toml
[hook]
enabled = false
```

With that set, `git commit` is never gated by this plugin. The skill and
the plain CLI are unaffected, and keep reporting every finding on demand.

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

Neither switch reads the other: the plugin-wide toggle and a check's own
key are independent, and a project can set both.

## The unrecognized-table gate

`hook` is the one top-level table that is not a check's name. Any other
table naming no registered check is itself a gate finding, reported under
the mode `config` and naming the table. A table that differs from a real
check's name only by underscores for hyphens, `[executable_claims]` for
`[executable-claims]`, is named as the likely intent in the finding.

This exists because a mistyped section is otherwise a silent no-op: its
keys configure nothing, which looks exactly like a working opt-out until
the day the check it was meant to reach fires anyway. The gate is checked
against the checks actually registered in the installed copy, so a section
for a check that exists upstream but not in the installed version is
reported the same way, and the fix there is updating the plugin rather than
editing the table.

The gate reads `claims.toml` only. A mistyped table in `claims.local.toml`
still grants nothing and reports nothing.

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

## Next

Each check's own section of `claims.toml` is documented with the check.
The check pages follow, gate checks first, and
[check-links](checks/check-links.md) opens them. The [Concepts](concepts.md)
page is where to look up a word a check's description uses without
defining it.
