# User Documentation

How to write a page under `docs/`. `AGENTS.md`'s "User documentation"
section is the trigger — writing or changing a page sends you here; this
is what to follow once you are.

Adapted from or1can/ratect's account of the same problem — same author,
same conventions, a site that has been running long enough to have found
these rules the expensive way. What did not transfer (its two binaries, its
two config references, its animated captures) is simply absent here rather
than restated as a rule with nothing to govern.

## What `docs/` is

`docs/` holds pages written for someone using `claims`, and nothing else.
It is the source root of the published site
([`book.toml`](../book.toml)), so whatever lands here is what a reader
gets. Contributor material lives elsewhere: architecture decision records
in [`decisions/`](../decisions/), agent process docs here in `agents/`,
the release record in [`CHANGELOG.md`](../CHANGELOG.md). See
[`decisions/0004-docs-is-the-user-facing-tree.md`](../decisions/0004-docs-is-the-user-facing-tree.md)
for why the tree is split this way.

A page is published only once [`docs/SUMMARY.md`](../docs/SUMMARY.md) lists
it. A Markdown file left out of the summary is not built and not served, so
adding a page means adding it there too.

## Examples and captured output

1. **Captured or absent.** A block showing output comes from a real run —
   not typed, not hand-edited, not tidied up afterwards — or the page
   shows no output at all and says in prose what happens instead. Either
   way the block carries a one-line provenance: the command, and what it
   was run against, so a reader can see where the text came from and the
   next editor knows what to re-run.

   Where the output is a check's own findings, what it was run against is
   a checked-in example and the run goes through the repository's capture
   tooling, so that a test can re-run it and fail when the check's output
   changes. Where no example can produce the output —
   [`docs/installation.md`](../docs/installation.md)'s plugin inventory
   comes from installing into a disposable project — the provenance names
   what was actually done instead. That is the exception, not a second
   equal option.

   There is no ANSI handling here and none is needed: `claims` emits no
   colour, so a plain fenced block is the whole requirement.
2. **Show, then clarify.** Where the capture shows it, prose does not
   describe it. Prose is for what the capture cannot show — why the check
   holds this claim false, what shape of prose would have passed, what the
   check deliberately misses.
3. **One example per comparison.** Blocks a reader is meant to compare
   come from the same example, so that what differs between them is the
   thing being compared rather than the input.

## Ownership and voice

4. **Present tense.** A page describes what `claims` does today. Version
   numbers, "as of", "not yet", and issue references belong in
   [`CHANGELOG.md`](../CHANGELOG.md) — there is no version picker on the
   site, so a reader cannot check "since 0.10.0" against the copy they
   have installed, and a "not yet" rots silently the day the thing lands.
5. **A page links out for reasoning, never for the fact it states.** An
   ADR link for *why* a check refuses to run a command by default is
   right; a link out of `docs/` for *what* the check does is not. `docs/`
   is self-contained on its own subject, and a contributor document can be
   rewritten out from under a user page's anchor.
6. **Every page in a reading path hands off.** `docs/SUMMARY.md`'s order is
   a reading order — mdBook renders it as previous/next buttons — so each
   page ends by naming where to go next, and a section's last page hands to
   the next section. [`docs/index.md`](../docs/index.md) models this.
7. **Drift-tool-relative framing stays on the index page.** `claims` is
   most quickly explained by contrast with the drift detectors it is not,
   and [`README.md`](../README.md) and `docs/index.md` both open that way.
   No other page does: a reader on a check page wants to know what that
   check holds true, and has no reason to have met a drift detector. An
   inline aside where a detail genuinely turns on the distinction is fine;
   an opening paragraph or a section heading is not.
