# 0002. A historical record's links resolve at the commit that wrote them

## Status

Accepted. Ticket #50.

## Context

`check-links` is a gate: a commit is refused while any internal Markdown
link in any tracked file fails to resolve against the working tree. That
is the right rule for a living page. It is the wrong rule for an
append-only record — a changelog, release notes, an ADR — whose own
convention forbids editing an entry once it has shipped, and which links
to living pages by the hundred (or1can/ratect's `CHANGELOG.md` carries 113
`docs/<page>.md#<anchor>` links).

The two rules together make every living page those records link to
un-renameable. Discovered in or1can/ratect#158, an information-architecture
audit of that project's `docs/` whose every structural fix turned out to be
blocked by this. The escape hatches all cost something the project didn't
want to pay: editing the record breaks the append-only rule; leaving a
stub heading at every old destination forever defeats the restructure;
excluding the record files from the check wholesale also stops checking
their still-live parts, since a changelog's Unreleased section is edited
in every release and an `exclude` glob can't tell the two apart.

## Decision

A project may list its append-only records under `[check-links]
historical`. For a link in a matching file that fails against the working
tree, the check re-resolves it against the tree at the commit `git blame`
attributes the line to, and passes it if it held there.

The reasoning: a link in a record is a claim about the tree *as it was
when the line was written*, and a gate's job is to admit the commit being
made now. Holding a five-release-old entry to today's tree tests a claim
nobody is making. Holding it to its own commit tests the claim its author
made.

Three details follow from the same reasoning rather than being separate
choices:

- **An uncommitted line resolves against the working tree.** `git blame`
  reports it with the all-zero SHA (or refuses to blame a file not yet in
  `HEAD`); it is being written now, so it is gated exactly as any other
  file. This is what keeps a changelog's Unreleased section fully checked
  while its shipped sections are not re-litigated.
- **A line a later commit touched must hold as of that commit.** Blame
  re-attributes it, so the gate re-tests it — which makes a deliberate,
  link-only retarget of a historical line (should a project ever decide
  its rules allow one) self-consistent rather than a special case.
- **A line older than the commit that first added `claims.toml` is
  skipped when it fails.** It was written before this plugin gated
  anything, so it may have been broken then, and the append-only rule
  means nothing can fix it now. The cutoff is discovered from history,
  not configured: a project with no tracked `claims.toml` has no cutoff
  and every line is checked.

The working-tree check runs first and blame only on a failure, so a
project whose records are all still valid pays nothing, and one mid-rename
pays one `git blame` per record file that has a failing link.

## Alternatives considered

- **An alias/redirect table** (`old path → new path`) in `claims.toml`, or
  read from mdBook's own `[output.html.redirect]` so site and check share
  one source of truth. Rejected: it grows forever, it maps paths but not
  `#anchor`s (so a heading move still needs a stub), and the mdBook
  variant teaches the plugin one site generator's config. A project that
  publishes a site still wants its own redirects for external links — that
  is the project's concern, not this check's.
- **Excluding the record files** via the existing `exclude` key. Works
  today with no code, and remains available; rejected as the answer
  because it also un-gates the live part of the same file.
- **Editing the record's links** (retarget the pointer, leave the prose).
  A defensible reading of "append-only" — the pointer isn't the claim —
  but it is the consuming project's rule to relax, not this plugin's to
  assume. The second consequence above keeps that option open.
- **Skipping every pre-adoption line rather than only failing ones.** No
  observable difference (a line that resolves today passes either way),
  and checking first keeps the common case cheap.

## Consequences

- A `historical` file's shipped entries stop being a reason a rename can't
  land. The rename commit still has to fix every *living* link — the check
  reports those exactly as before.
- A finding on a historical line now says where it was tested: `broken
  link: docs/x.md (not in the working tree, nor at abc1234 where this
  line was written)`.
- The check now shells out to `git blame`, `git cat-file`, `git log` and
  `git merge-base` — only for a `historical` file with a failing link, and
  cached per file, per commit, and per (commit, path) within one run.
- A symlink stored in history is read as its target text by `git cat-file`
  rather than followed; a historical link *to* a tracked symlink is
  therefore judged on the wrong content. Accepted: the working-tree check
  already follows it correctly, so this only matters for a symlink that
  has since been removed, and no project using this plugin has one.
