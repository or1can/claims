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

**Status:** ready-for-agent

- [ ] A heading containing an underscore (e.g. `` `RUST_LOG` `` or
      `additional_args`) round-trips: a link to its real GitHub anchor is
      not flagged as broken.
- [ ] Existing `check_links` tests still pass — this must not reintroduce
      false negatives for headings that never had underscores.
- [ ] A regression test pins the specific underscore-stripping bug, not
      just a general "links resolve" smoke test.
