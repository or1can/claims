# 0002. A historical record's references resolve at the commit that wrote them

## Status

Accepted. Ticket #50.

Amended by #57, which gave `check-file-refs` the same key. The reasoning
below was always about a reference, not a link; it read as
`check-links`-specific only because `check-links` was the one check in
scope when it was written. The amendment restates it that way, and adds
the section on which checks it reaches.

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

The same held for a bare backticked path, which `check-links` never
reads. #53 measured that this repo's `CHANGELOG.md` and ADRs cite files
that way and contain no internal Markdown links at all, so the mode
protected the citation style records here do not use, and the style they
do use had no protection. #56 then found three shipped changelog lines
naming paths it was about to move, each a permanent `check-file-refs`
gate finding had they not been retargeted.

## Decision

A project may list its append-only records under a check's `historical`
key — `[check-links] historical` for links, `[check-file-refs]
historical` for bare path mentions. For a reference in a matching file
that fails against the working tree, the check re-resolves it against
the tree at the commit `git blame` attributes the line to, and passes it
if it held there. What "held" means is the check's own: for a link, the
target file existed with the anchored heading, if any; for a bare path,
a file existed at that path, taken either from the repository root or
from the citing file's directory, the same two bases the working-tree
test accepts.

The reasoning: a reference in a record is a claim about the tree *as it
was when the line was written*, and a gate's job is to admit the commit
being made now. Holding a five-release-old entry to today's tree tests a
claim nobody is making. Holding it to its own commit tests the claim its
author made.

Three details follow from the same reasoning rather than being separate
choices:

- **An uncommitted line resolves against the working tree.** `git blame`
  reports it with the all-zero SHA (or refuses to blame a file not yet in
  `HEAD`); it is being written now, so it is gated exactly as any other
  file. This is what keeps a changelog's Unreleased section fully checked
  while its shipped sections are not re-litigated.
- **A line a later commit touched must hold as of that commit.** Blame
  re-attributes it, so the gate re-tests it — which makes a deliberate,
  pointer-only retarget of a historical line (should a project ever decide
  its rules allow one) self-consistent rather than a special case.
- **A line older than the commit that first added `claims.toml` is
  skipped when it fails.** It was written before this plugin gated
  anything, so it may have been broken then, and the append-only rule
  means nothing can fix it now. The cutoff is discovered from history,
  not configured: a project with no tracked `claims.toml` has no cutoff
  and every line is checked.

The working-tree check runs first and blame only on a failure, so a
project whose records are all still valid pays nothing, and one mid-rename
pays one `git blame` per record file that has a failing reference.

## Which checks this reaches

The key earns its keep only where a claim can have been *false when
written*. Re-resolving at the blame commit then discriminates "was always
broken", which still gates, from "broke later", which does not — and that
discrimination is the whole value. Where the claim held at the commit
that wrote it by construction, re-resolving there passes every line
unconditionally, and an `exclude` glob already *is* the historical
semantics, without the blame walk. That test, read against each check's
own page and code:

- **`check-links` and `check-file-refs`** assert existence — this
  reference resolves — can be false when written, and are answered at a
  commit from that commit's own objects. Both take the key, and share one
  resolver (`claims/historical.py`), each passing in only its own
  at-commit test.
- **`check-env-vars`** asserts existence too: a backticked name appears
  in the files the project says define its environment. The reasoning
  applies, and the mechanism would be a blob read of those files at the
  commit. Not built.
- **`check-citations`** asserts existence as well — a cited Swift symbol
  is still declared — and it already walks full history, so the
  reasoning applies. It answers the record case per citation instead,
  with its `was:` marker, and has no `historical` key.
- **`check-config-defaults`** asserts agreement, but not agreement by
  construction: it is advisory, so a stated default can have disagreed
  with its mapped line from the day it was written. The reasoning
  therefore applies. The mechanism does not follow directly, because the
  mapping it reads is today's `claims.toml`, naming today's line numbers;
  re-testing at an old commit would also have to read the mapping as it
  stood then. Not built.
- **`check-cli-flags`** and **`executable-claims`** assert what a command
  does — a script advertises a flag, a command prints a block — and can
  be false when written, so the reasoning applies. The mechanism does
  not: each verifies by *running* something in the working tree, and no
  read of a commit's blobs reproduces running it at that commit. A record
  there takes `exclude`, which un-gates its live part too.
- **`restatement`** asserts that a retracted sentence is not still said
  elsewhere. A survivor matched its source exactly at the commit that
  wrote it — that is what makes it a restatement — so re-resolving there
  passes every one. `exclude` is the historical semantics.
- **`stale-claims`** ranks sections by churn since their last edit, which
  is zero at the commit that made that edit. It degenerates the same way;
  `exclude` again.
- **`claim-words`** and **`temporal-words`** read only sentences the
  diff added, so a shipped entry is never re-read and there is nothing to
  resolve historically. **`judgment-agent`** does reach a shipped entry
  citing a name the diff touched, but it only nominates a candidate; the
  verdict comes from a subagent reading today's code, and it gates
  nothing. **`spliced-docs`** reads doc comments in code, not references
  in prose. All four are out of scope.

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
  land. The rename commit still has to fix every *living* reference — the
  check reports those exactly as before.
- A finding on a historical line now says where it was tested: `broken
  link: docs/x.md (not in the working tree, nor at abc1234 where this
  line was written)`, and `check-file-refs` the same way after its own
  message: `` `docs/x.md` does not resolve to a tracked file (not in the
  working tree, nor at abc1234 where this line was written) ``.
- A check with the key shells out to `git blame`, `git cat-file`, `git
  log` and `git merge-base` — only for a `historical` file with a failing
  reference, and cached per file, per commit, and per (commit, path)
  within one run. `check-file-refs` asks `git cat-file` for the object's
  type rather than its content, since existence is all it needs.
- `check-file-refs`' `known_untracked` is not consulted at a commit: a
  deliberately untracked file was never in any commit's tree, so the key
  has no commit-time meaning.
- A symlink stored in history is read as its target text by `git cat-file`
  rather than followed; a historical link *to* a tracked symlink is
  therefore judged on the wrong content. Accepted: the working-tree check
  already follows it correctly, so this only matters for a symlink that
  has since been removed, and no project using this plugin has one.
