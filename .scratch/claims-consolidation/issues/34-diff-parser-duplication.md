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

**Status:** ready-for-agent

- [ ] A single, shared diff-walking primitive lives in `claims/git.py`,
      used by both `added_lines_by_file` and `restatement.py`'s
      `_diff_by_file` — no second hand-rolled state machine.
- [ ] All existing tests in both `tests/test_git.py` and
      `tests/test_restatement.py` (including ticket 32's `++`/`-- `
      collision regression tests) still pass unchanged.
- [ ] The shared primitive itself has direct test coverage for the
      collision cases (`++`, `-- `, deleted-file `+++ /dev/null`), rather
      than relying on each caller's own tests to exercise it.
