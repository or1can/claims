# 10 — Port claim-words check (advisory)

**What to build:** a diff-scoped sweep over added lines for totalising
words ("every", "only", "never"), spelled-out or digit counts, and words
asserting something "elsewhere" only when adjacent to a citation, scoped to
whole sentences within designated record-like files. Registered as an
**advisory** check.

**Blocked by:** 06.

**Status:** resolved

- [x] A totalising claim that generalises past what a nearby table/figure
      actually supports is flagged.
- [x] A spelled-out or digit count is recognised regardless of magnitude
      (not capped at a fixed ceiling).
- [x] A document quoting its own retired false claim (the house style for
      retiring a sentence — an italic, a block quote, or a fixed lead-in
      phrase) does **not** fire on the quotation.
- [x] A number that measures the world (an external count, a byte
      comparison) is not treated the same as a number describing the tree.
- [x] Never fails the run (advisory).

## Answer

`claims/checks/claim_words.py` — `NAME = "claim-words"`,
`check(repo_root, diff_range, config) -> list[Finding]`, self-registered as
an **advisory** check (`gate=False` on every finding), wired into
`claims/checks/__init__.py` alongside the other three checks.

Ported from Project B's `tools/claim-words.py` (same author, relicensed),
narrowed per spec.md's user story 17 to whole *sentences* within
*designated* record-like files (`files`, a config list of glob patterns —
nothing is swept until a project opts a file in), rather than the source
tool's per-paragraph, per-language-comment sweep over everywhere-minus-
`CHANGELOG.md`. The word lists (`STRONG`/totalising, `ELSEWHERE`/reaches-
for-code-not-shown) carry over; the count list doesn't — it's now a run of
spelled-out number words of any magnitude, not a fixed `two`..`twelve`
ceiling, and a count beside a known unit of measurement (`UNIT_WORDS`:
bytes, seconds, days, decades, ...) is treated as describing the world, not
the tree, and isn't flagged.

**House style for retiring a sentence**, established here since nothing
elsewhere in the codebase's history defined one: a quoted, retired false
claim is exempt when it's a Markdown blockquote, wrapped whole in
`*italics*`/`_italics_`, or opens with the fixed lead-in phrase "Previously
said:" — any one of the three; an unmarked quotation still fires, since
it's indistinguishable from the claim still being made.

Three modes (`MODE_TOTALISING`, `MODE_COUNTS`, `MODE_ABOUT_ELSEWHERE`), not
one — `runner.Finding`'s own docstring says `mode` should name the matching
strategy when a check has more than one, the way `restatement` already does
with `MODE_NGRAM`/`MODE_WHOLE_LINE`. A sentence matching more than one class
(e.g. "Only twelve configs remain.") produces one `Finding` per mode rather
than folding them into a single finding's message.

Tests: `tests/test_claim_words.py` (17 cases) against fixture git repos —
totalising/count/about-elsewhere detection (including a multi-mode
sentence), all three retirement-suppression forms plus the "unmarked
quotation still fires" counterexample, the opt-in `files` scoping (an
undesignated file untouched, an unconfigured project sees nothing), and the
advisory `gate=False` contract. 63 tests total across the suite, all green.

Post-review (`/code-review`, two rounds) found real gaps, all fixed:
`STRONG_RE`/`ELSEWHERE_RE`'s `\b` boundaries matched inside a hyphenated
identifier (`` `--always-verify` `` flagged "always" as a claim) — fixed
with a hyphen-aware boundary. `UNIT_WORDS` was missing `decade`/`century`,
so "three decades" was flagged as a tree count contrary to the check's own
stated rule — added. A bare-string `files` config value (`files =
"record.md"` instead of `["record.md"]`) silently iterated as single
characters, turning "opt in one file" into "sweep every file" via an
`fnmatch` against `"*"` — fixed by coercing a bare string to a one-element
list. The blockquote suppression matched any line starting with a literal
`>`, including a no-space "greater-than" threshold marker (`>5 hosts...`);
it now requires the CommonMark blockquote marker's trailing whitespace/EOL,
narrowing (not eliminating — `"> 5 hosts"`, with a space, is genuinely
ambiguous between prose and blockquote) the false-negative surface. The
second round's Finding-mode gap (above) came from a Spec-axis review
against `runner.py`'s own documented contract.

Deferred, not this ticket's scope, noted in `TODO.md`: this check's
`_added_lines` duplicates unified-diff hunk-parsing `restatement.py`
already does independently (a follow-up gardening commit promotes it to
`claims/git.py`, per the same pattern ticket 08's gardening commit used);
the runner has no per-check exception isolation, so a raising check (e.g.
`git diff` against an unborn `HEAD`) crashes the whole run rather than
degrading one advisory check; and the retired-quote suppression rule is
private to this check, worth promoting to a shared module if a future
check (e.g. ticket 11's `spliced-docs`) needs the same judgment.
