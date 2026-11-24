# 0020. A historical reference that moved is a markable finding

## Status

Accepted. Issue #264; amends
`decisions/0002-historical-links-resolve-at-their-own-commit.md` and
`decisions/0011-append-only-is-a-property-of-the-file.md`, and builds on
`decisions/0012-a-ci-run-can-fail-on-unmarked-findings.md` and
`decisions/0019-claims-are-intended-current-superseded-or-past.md`.

## Context

`historical` means two things. To `check-links` and `check-file-refs`
(ADR 0002) a reference in a matching file that fails against the working
tree is re-tested where its line was written, and passes if it held
there or just before it, or if its line predates the project's adoption
commit. To `restatement` and `judgment-agent` (#174) a line in a matching
file that the diff didn't add is not read at all.

The first meaning is a file-level stand-in for a claim's kind. ADR 0019
made kind a property of a claim, inferred by reading it, and noted that
the stand-in passes a current claim in a `historical` file, such as a
decision's link, if it held at its writing. A reference that moved is
then never read again: nothing says whether the line around it records
what was, and so is fine, or says what is, and so is now false. And a
line older than the adoption commit is passed without being tested at
all, held or not.

The second meaning is not about a claim's kind at all. A line the diff
didn't add is skipped because the file is a record nobody may reword,
which is ADR 0011's append-only property of the file, set once for the
project under `[subjects] append_only`.

The words for severity predate both. `CONTEXT.md` defined a gate as
"the finding severity that stops a commit" and an advisory finding as
one "surfaced and never fails the run". ADR 0012 let a run fail on an
unmarked advisory finding, and a project passing `--fail-on-unmarked`
in CI, as or1can/ratect does, fails on both. What still tells them
apart there is what settles them.

Measured on the reference this would demote: in this repository, 5
mentions in ADR 0004 naming `docs/configuration.md`<!-- example -->, past by its
Status. On or1can/ratect, 106 findings on 91 lines, 88 of them before
its adoption commit, and 3 of those never held: `CHANGELOG.md` naming
`docker/connection.rs`<!-- example -->, `RELEASES.md` naming `tests/cli.rs`<!-- example -->, and its
ADR 0005 naming `src/grpc/mod.rs`<!-- example -->.

## Decision

**Gate and advisory are defined by what settles them.** A gate finding
is settled only by a change: to the text, a fix or a marker beside the
claim, or to the configuration scoping the check. It always fails the
run. An advisory finding may also be settled
by a reading, recorded as a checked mark. An unmarked one fails the run
only where the caller asks for that (ADR 0012).

**A claim's kind comes from reading it.** Configuration scopes checks
(`exclude`, `exclude_sections`, `[subjects] append_only`) and never
declares a kind, and neither does a document's structure, such as a
changelog's release headings or a decision record's Status line.

**`historical` demotes a reference that moved.** In a file matching
`[check-links] historical` or `[check-file-refs] historical`, a
reference that fails against the working tree is:

- an advisory finding, in a mode of its own per check
  (`check-links-historical`, `check-file-refs-historical`), when its line
  predates the adoption commit, or when the reference resolves at the
  commit that wrote its line or at one of that commit's parents. The
  message says which, and names the commit;
- a gate finding as before otherwise: a line written after adoption whose
  reference held neither where it was written nor just before it.

An uncommitted line is tested at `HEAD` as before, and demoted if it
held there. A reference that resolves against the working tree is never
a finding. ADR 0002's resolution stands; what changes is that it no
longer passes a reference, and instead decides which severity a
failure takes.

The demoted modes can be marked. A mark's unit is the line and the
reference it names, and its expiry follows ADR 0010 and, for a past
mark, ADR 0019: a reader reads the line around the reference, infers its
kind, and reads it at that kind's tree. A past claim gets a past mark
once, which expires only on its wording. A current one reads `false`
against the tree as it stands, and is fixed, or superseded by a Status
note. The demoted modes are covered by `--fail-on-unmarked` and
`[hook] fail_on_unmarked` under their check's name.

**The added-lines skip belongs to append-only files.** `restatement` and
`judgment-agent` skip a line the diff didn't add in every file
`[subjects] append_only` matches, `CHANGELOG.md` built in, and take no
`historical` key. A `historical` key in either table makes `claims.toml`
invalid, with a message naming `[subjects] append_only`. The name
`historical` stays on the two gate checks, with one meaning.

## Alternatives considered

- **Infer the kind from document structure**: a release heading in a
  changelog, a decision record's Status line. Each format needs its own
  decoder, and a project's own records need one each, where reading the
  claim works for any of them.
- **Keep the pass.** Costs nothing at adoption, and leaves a moved
  reference unread for good, current claims included.
- **Keep skipping pre-adoption lines silently.** On or1can/ratect that
  hides the 3 mentions that never held, which a reading finds at once.
  A missed claim stays invisible forever, where a demoted finding is
  read once and marked.
- **Report a shipped line of an append-only file to `restatement` and
  `judgment-agent`, and quiet it with past marks.** Every new retraction
  matching a shipped entry raises it again, as a different finding,
  where the line can never change.
- **Rename `historical`.** Its remaining meaning is the one the word
  says, and a project's configuration keeps working for the two checks
  that keep it.

## Consequences

- `CONTEXT.md`'s **Gate** and **Advisory**, and the "Gate versus
  advisory" section of `docs/concepts.md`, define each by what settles
  it.
- A project with a `historical` file gets a one-time batch of markable
  findings for references that moved since their writing, and for
  pre-adoption references that fail today. Those that never held are
  read as false and fixed or superseded.
- A project's `[restatement] historical` or `[judgment-agent]
  historical` is refused, and moves to `[subjects] append_only`. That
  list also changes `stale-claims`' churn and mark expiry for the file
  (ADR 0011), which is what an append-only record wants.
- ADR 0011's "The two settings say different things about the same
  file" now holds of `check-links` and `check-file-refs` alone.
