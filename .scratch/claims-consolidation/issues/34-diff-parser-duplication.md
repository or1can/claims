# 34 — `added_lines_by_file` and `_diff_by_file` hand-roll the same diff-header state machine twice

**What to build:** `claims/git.py`'s `added_lines_by_file` and
`claims/checks/restatement.py`'s `_diff_by_file` each independently
implement the same "walk `git diff --unified=0` output, find file
boundaries via `diff --git `, don't trust a bare `+++`/`--- ` match
because hunk content can collide with it" state machine — one keyed on a
nullable `path`, the other on a separate `awaiting_header` boolean — to
solve the identical problem two different ways.

Found during ticket 32's `/code-review` pass, out of scope for that
ticket (which fixed the header-collision bug itself, not the
duplication).

Confirmed concretely: ticket 32 needed the exact same fix — reasoned
through, tested, and applied — twice, once per file, with two separate
test suites (`tests/test_git.py`, `tests/test_restatement.py`) needing
matching new cases to catch a regression in either copy. Any future
diff-header hazard git introduces (or a fix to how renames/binary files
are handled) has to be diagnosed and patched in both places; missing one
silently reintroduces exactly the class of bug ticket 32 just fixed.

`claims/git.py`'s own module docstring says "Shared git plumbing used by
more than one check" — the precedent for sharing already exists
(`tracked_files`, `QUOTEPATH_OFF`), but this specific state machine wasn't
factored in. The two callers collect different things from it (added
line *numbers* keyed by path vs. removed+added line *text* with per-side
scope filtering), so a shared primitive needs to be general enough for
both — e.g. a generator in `claims/git.py` yielding one event per line
("new file segment, here's its path" / "hunk line, here's which side"),
with each caller building its own specific aggregation on top.

**Blocked by:** none.

**Status:** resolved

- [x] A single, shared diff-walking primitive lives in `claims/git.py`,
      used by both `added_lines_by_file` and `restatement.py`'s
      `_diff_by_file` — no second hand-rolled state machine.
- [x] All existing tests in both `tests/test_git.py` and
      `tests/test_restatement.py` (including ticket 32's `++`/`-- `
      collision regression tests) still pass unchanged.
- [x] The shared primitive itself has direct test coverage for the
      collision cases (`++`, `-- `, deleted-file `+++ /dev/null`), rather
      than relying on each caller's own tests to exercise it.

## Answer

Went further than a flat "one event per line" primitive (the ticket's
own sketch) after `/code-review` — spread across 8 parallel angles on the
first pass — repeatedly converged on the same gap in that shape: a caller
has to remember to reset its own per-file state on a `DiffNewFile` event,
and nothing enforces it. `git.py`'s `added_lines_by_file` remembered
(`path = None`); `restatement.py`'s `_diff_by_file` didn't
(`from_scope`/`to_scope` were never reset). Three independent review
angles flagged the asymmetry; all three confirmed it wasn't a *live* bug
(a file with no header never has content lines to misread its stale
scope through) — but it's exactly the kind of implicit invariant this
whole ticket exists to stop relying on.

Redesigned `iter_diff` to yield one `FileDiff(src, dst, body)` per file
instead of a flat event stream — `src`/`dst` are the header's paths
(`None` for that side's `/dev/null`), `body` is that file's
`DiffHunkStart`/`DiffLine` items, and a header-less file (pure rename,
binary, mode-only change) is simply a `FileDiff` with both paths `None`
and an empty body. Both callers now compute their per-file state fresh
inside the outer per-`FileDiff` loop — there's no cross-file state left
to forget to reset, because there's nothing to carry between iterations.
This closes the gap structurally rather than by remembering to add a
reset line, and confirmed by `/code-review` afterward: "the old
`_diff_by_file`... had a latent global-state leak... the new per-`FileDiff`
scoping eliminates that class of bug entirely rather than papering over
it."

Side effects along the way, all improvements, none regressions (each
verified individually, not just asserted):
- `restatement.py`'s `_diff_by_file` never pinned `--src-prefix`/
  `--dst-prefix` (only `added_lines_by_file` did, since ticket 27).
  Routing through the shared `iter_diff` pins them for both callers now,
  closing a `diff.mnemonicPrefix`/`diff.noprefix` gap `restatement.py`
  never had a fix for — added its own regression test
  (`test_a_non_default_diff_header_prefix_still_flags_a_retraction`)
  rather than relying only on `iter_diff`'s.
- `restatement.py`'s own `git diff` invocation never passed `--no-color`
  either (flagged as a latent gap back in ticket 27's own review, never
  fixed until now) — also closed for free by going through `iter_diff`.
- A stale test docstring in `tests/test_restatement.py` referencing
  "restatement.py's own `+++ ` match" (that match lives in `iter_diff`
  now) — fixed.

`DiffEvent`/`DiffNewFile`/`DiffHeader` (the flat-stream types from the
first pass) are gone; `FileDiff` replaces them. `_in_scope` in
`restatement.py` now takes the extracted path (`str | None`) instead of
the raw header line — same suffix check, operating on what `iter_diff`
already resolved instead of re-deriving it from text.

Verified: full suite (`python3 -m unittest discover -s tests -p
'test_*.py'`) — 158 passed (up from 147; 11 new tests: 9 direct
`iter_diff` cases in `tests/test_git.py`, 1 in `tests/test_restatement.py`
for the prefix-immunity gap, and ticket 27/31/32's existing coverage for
both files passing unchanged throughout every step of the redesign).
`uv run pyright claims tests` — 0 errors, 0 warnings, 0 informations.
`/code-review` run three times across this ticket: first pass (8
parallel angles, the deepest yet run this session) found the
Union-vs-`|` style nit (fixed) and the from_scope/to_scope asymmetry
(fixed via the `FileDiff` redesign, not a small patch); second and third
passes on the redesigned code found nothing further.

One follow-up noted but not filed as its own ticket, since it's a
different concern (per-run caching across checks, not diff-parsing
correctness): an efficiency angle observed that `claim-words` and
`restatement` each still call `iter_diff` independently for the same
`(repo_root, diff_range)` in a single run — pre-existing (each had its
own separate `git diff` subprocess before this ticket too), not something
this ticket introduced or was scoped to fix.
