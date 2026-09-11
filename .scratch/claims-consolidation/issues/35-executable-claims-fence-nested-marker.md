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

**Status:** open

- [ ] A marker line that appears as literal text inside an already-open
      fenced block is not treated as live — reproduced with a fixture
      shaped like the one described above (marker inside one fence,
      immediately followed by a second fence showing expected output).
- [ ] Existing `executable_claims` tests still pass — a marker that is
      genuinely directly above a fenced block (the supported case) must
      keep working exactly as before.
- [ ] A regression test pins this specific fence-nesting case, not just a
      general "markers still run" smoke test.
- [ ] Note whether the `config`-exclusion gap (above) gets folded in or
      left for its own ticket.
