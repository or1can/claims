# 26 — `check-links`' slug computation strips underscores GitHub's real anchor slugger keeps

**What to build:** `claims/checks/check_links.py`'s `SLUG_STRIP_RE`
(`[^a-z0-9 -]`) strips underscores when computing a heading's anchor slug.
GitHub's real slugger keeps them. Any heading containing one — a
backtick-quoted identifier like `` `RUST_LOG` ``, or a word like
`additional_args` — gets a computed slug that never matches its own real
anchor, so a correct link to it is reported as a **gate** failure (blocks a
commit that did nothing wrong).

Confirmed root cause, not assumed: computing `_slug()` directly against
`ratect`'s real headings during ticket 19's parity validation found this
is 7 of the 12 `check-links` gate findings on `ratect`'s `main` (pinned at
`5aded18`). See `TODO.md`'s (now-removed) entry and ticket 19's own
`## Answer` for the full breakdown, including the 5 unrelated findings
that aren't this bug (don't fold those into this ticket's fix).

Fix `SLUG_STRIP_RE` (or the slugging logic it's part of) to match GitHub's
actual anchor algorithm for underscores, and add a regression test with a
heading containing an underscore whose real GitHub anchor is known.

**Blocked by:** none.

**Status:** resolved

- [x] A heading containing an underscore (e.g. `` `RUST_LOG` `` or
      `additional_args`) round-trips: a link to its real GitHub anchor is
      not flagged as broken.
- [x] Existing `check_links` tests still pass — this must not reintroduce
      false negatives for headings that never had underscores.
- [x] A regression test pins the specific underscore-stripping bug, not
      just a general "links resolve" smoke test.

## Answer

Fixed `SLUG_STRIP_RE` in `claims/checks/check_links.py` from
`[^a-z0-9 -]` to `[^a-z0-9 _-]` — underscore now survives slugging,
matching GitHub's real anchor algorithm. Updated the module docstring's
stated slug rule to match, and noted the ticket 26 divergence from the
source tool's `slugs_of` (which this port no longer matches on purpose).

Added `test_a_heading_with_an_underscore_anchor_that_resolves_is_not_flagged`
to `tests/test_check_links.py`: a heading `` # `RUST_LOG` `` linked via
`#rust_log` now resolves with no findings.

Verified: full suite (`python3 -m unittest discover -s tests -p
'test_*.py'`) — 131 passed. `uv run pyright claims tests` — 0 errors, 0
warnings, 0 informations. `/code-review` run on the diff; its one finding
(stale docstring) fixed in the same commit. Committed as `a734e1a`.
