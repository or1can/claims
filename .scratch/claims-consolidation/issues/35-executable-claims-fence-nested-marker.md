# 35 — `executable-claims` treats a marker line inside an already-open fence as live

**What to build:** `claims/checks/executable_claims.py`'s `_blocks()` scans
lines for `MARKER_RE` with no fence-depth tracking. A `<!-- verify: ... -->`
line that appears as literal text *inside* an already-open fenced code
block — shown there purely to document the marker syntax itself — still
matches, and `_blocks()` then pairs it with the nearest following fence
line as if that were the block's own opening fence. When the marker sits
one line before that fence's *close*, the close is read as the open, and
the very next fence (typically the start of whatever comes after in the
doc) is read as the matching close — producing an empty expected block.
The real command then runs for real, its actual output almost never
matches empty, and a documentation example — not a false claim — fails as
a **gate** finding.

Confirmed root cause, not assumed: reproduced directly against a
consuming project. A closed ticket in that project's own append-only
history directory (the same `.scratch/`-style convention this repo uses)
illustrated the marker+block syntax with a realistic example — a fenced
block containing the `<!-- verify: ... -->` line, immediately followed by
a second fenced block showing the expected output. That project's own
`verify_claims.py` (the tool this check was ported from) never swept that
directory — its `main()` excludes history wholesale by design, and its
own ticket history already named this exact scenario as a known, deferred
latent limitation of the mechanism: a marker written inside a fenced
example being picked up as live, left unfixed on the grounds that nothing
in that repo could reach it. `executable-claims` has no equivalent
exclusion and swept the directory anyway, so the previously-unreachable
case fired for the first time — against history, not against a fresh
documentation mistake.

Two things worth separating when this is picked up:

- **The actual bug:** no fence-depth tracking in `_blocks()`. A marker
  found while already inside an open fence should never be treated as a
  live marker — a marker's contract is "directly above a fenced block,"
  not "matches the regex somewhere in the file." Fixing this benefits
  every consuming project, independent of any exclusion config.
- **A separate, smaller gap noticed on the way:** both `executable_claims.py`
  and `check_links.py` accept a `config` argument (per-check section of
  `claims.toml`) and ignore it entirely — there's no wired-up way for a
  consuming project to exclude a path (e.g. its own append-only history
  directory) from either check. Not this ticket's fix, but likely the
  same shape of fix `stale_claims.py` already has for its own exclusions —
  worth a glance when this is resolved, in case one fix covers both.

**Blocked by:** none.

**Status:** resolved

- [x] A marker line that appears as literal text inside an already-open
      fenced block is not treated as live — reproduced with a fixture
      shaped like the one described above (marker inside one fence,
      immediately followed by a second fence showing expected output).
- [x] Existing `executable_claims` tests still pass — a marker that is
      genuinely directly above a fenced block (the supported case) must
      keep working exactly as before.
- [x] A regression test pins this specific fence-nesting case, not just a
      general "markers still run" smoke test.
- [x] Note whether the `config`-exclusion gap (above) gets folded in or
      left for its own ticket.

## Answer

Added `_fence_state()`: a single whole-file pass tracking, per line,
whether it sits inside a still-open fence — length-aware (a shorter
backtick run nested inside a longer one is literal content, not a real
delimiter, per CommonMark's own nesting rule), not a naive "any 3+
backticks toggles it" parity count. `_blocks()` now skips a marker match
while `in_fence` is true, and reuses the same array to bound a live
marker's own expected block (so a block that legitimately nests a fenced
example of its own isn't truncated at the nested example's first line).

Three review rounds, each surfacing one more genuine gap in the previous
pass, all fixed:
1. The original ticket bug (marker inside a fence treated as live).
2. Two CommonMark-nesting cases the first pass's naive boolean-parity
   toggle got wrong: a marker inside a *longer* outer fence (the length-
   aware rule above), and a live marker's own block legitimately
   containing a nested fenced example (the shared-array reuse above).
3. A new silent-failure mode the fence-tracking fix itself introduces: a
   stray, never-closed fence anywhere earlier in a file desyncs
   `in_fence` for everything after it, so a marker that would otherwise
   be live goes unchecked with **no finding at all** — worse than ticket
   35's own original bug, which at least failed loudly (a wrong gate
   finding), not silently. Added `dangling_open_line` to `_fence_state`
   and a "fenced code block is never closed" gate finding for it.

That third item drew real, repeated scrutiny in review — multiple passes
flagged it as scope creep against this ticket's own literal checklist
(CLAUDE.md's "no features beyond what was asked"), landing at PLAUSIBLE
rather than CONFIRMED each time specifically because of the counter-
argument: unlike the ticket's own bug, an unclosed fence's silent-failure
mode doesn't exist *before* this fix — fence-tracking didn't exist at all
pre-ticket-35, so there was nothing for a stray fence to desync. Shipping
the requested fence-tracking without also closing the new silent-failure
hole it creates would trade one bug for a worse, quieter one. Kept it on
that basis, not as an unrelated feature.

**One related gap deliberately *not* closed, on the user's explicit
call**: a stray, self-closed fence pair around an otherwise-live marker
(no dangling fence, everything balances) is structurally identical to a
genuine nested documentation example — both are "a fence opened, then
closed, around some lines." There's no mechanical way to tell "accidental
pairing" from "deliberate nesting" apart without guessing the author's
intent, unlike the dangling case, which is always reliably detectable
(nothing closes it, full stop). Documented as an accepted narrowing in
`_fence_state`'s own docstring rather than chased with another heuristic.

Filed ticket 36 for the `config`-exclusion gap — checked ticket 35's own
assumption that `stale_claims.py` already has a reusable config-driven
exclusion pattern to copy, and it doesn't (`CHANGELOG.md` is excluded by
a hardcoded filename check, not anything config-surfaced) — so this needs
its own design, not a copy, and is a different concern from this ticket's
actual bug regardless.

Nine tests in `tests/test_executable_claims.py` cover: the original
nested-marker case, a nested-marker example not interfering with a real
marker elsewhere, length-aware nesting in a longer outer fence, a live
marker's own block nesting a nested fenced example, and a genuinely
dangling fence being reported without swallowing an earlier legitimate
marker. Extracted the repeated nested-example fixture into a
`nested_marker_example()` helper (review-flagged duplication).

Verified: full suite (`python3 -m unittest discover -s tests -p
'test_*.py'`) — 163 passed. `uv run pyright claims tests` — 0 errors, 0
warnings, 0 informations. `/code-review` run four times as the diff
evolved — each of the first three found one genuine, distinct gap (all
fixed above); the fourth (two independent verification passes on the
"scope creep" question) confirmed the unclosed-fence finding as
defensible-but-worth-flagging (PLAUSIBLE) rather than clean, and one
test-fixture whose docstring mischaracterized its own mechanism (fixed:
`test_an_unclosed_fenced_block_is_reported_not_silently_mishandled` now
isolates a genuinely dangling fence from a genuinely live marker, instead
of conflating the dangling case with the separately-accepted
stray-pair case).
