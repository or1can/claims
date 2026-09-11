# 32 — `added_lines_by_file` drops added lines whose content starts with `++`

**What to build:** `claims/git.py`'s `added_lines_by_file` guards against
matching the `+++ b/<path>` header line with:

```python
elif line.startswith("+") and not line.startswith("+++"):
```

but an ordinary added line whose *content* happens to start with `++`
(`++i;`, `++bold++` in markdown, etc.) becomes `+++i;` once the diff's own
`+` marker is prepended — indistinguishable from the header guard, so the
`elif` falls through untaken. That line is neither recorded as added nor
does `line_no` get incremented for it, desyncing every subsequent added
line's reported number in that hunk by one.

Found while fixing ticket 27 (diff-header *prefix* scheme handling);
distinct bug, same function, deliberately left out of that fix's scope.

Confirmed concretely: a file with new lines `++i;` (line 2) and `two`
(line 3) added in one hunk returns `{'f.md': {2}}` from
`added_lines_by_file`; the correct result is `{'f.md': {2, 3}}` — line 2
is dropped entirely and line 3 is misreported as line 2.

The header guard only needs to fire on the *first* line after a `---`
line within a given file's header block, not on every line starting with
`+++` anywhere in the diff — tracking header-parsing state (e.g. "have we
seen this file's `+++` line yet") rather than restarting the check per
line should fix both the header/content ambiguity and avoid a fresh
per-line string comparison.

**Blocked by:** none.

**Status:** resolved

- [x] An added line whose content starts with `++` is recorded as added,
      at the correct line number.
- [x] Every added line after it in the same hunk keeps the correct line
      number (no off-by-one desync).
- [x] A regression test covers this case using a real `git diff`
      invocation against a `Repo` fixture, not a hand-typed diff string.

## Answer

Took the ticket's own suggested route: track header-parsing state instead
of matching `+++`/`--- ` wherever they appear. `added_lines_by_file`
(`claims/git.py`) now keys off `path is None` — cleared on `diff --git `
(the one line no hunk content can ever collide with) and read against
`+++ ` only while still `None`. A bare `+++`/`--- ` match, tried first,
turned out to have its own mirror-image collision (a *removed* line
starting with `-- ` becomes `--- ` the same way `++i;` becomes `+++i;`)
and a second, distinct bug (a deleted file's `+++ /dev/null` header
falling through to the added-content branch, fabricating a phantom
entry under the previous file's stale path) — both caught by
`/code-review` on work-in-progress before either was ever committed, not
shipped regressions. `restatement.py`'s `_diff_by_file` had the identical
`++`/`-- ` collision (same root cause, same review pass); fixed the same
way there with its own `awaiting_header` state (kept separate from
`path`, since `_diff_by_file` tracks two independent scope flags with no
natural "unset" sentinel to fold state into, unlike `git.py`'s nullable
`path`).

Five regression tests total: `test_an_added_lines_content_starting_with_plus_plus_is_not_dropped`
and `test_a_deleted_file_later_in_the_diff_adds_no_phantom_line` in
`tests/test_git.py` (both genuinely red against committed code);
`test_an_added_line_after_a_removed_line_starting_with_dash_dash_is_not_dropped`
in `tests/test_git.py` and `test_a_removed_line_starting_with_dash_dash_does_not_hide_a_later_retraction`
in `tests/test_restatement.py` (both pass unchanged against committed
code too — the original cruder matching handled these two specific
scenarios correctly by accident, so they're characterization/insurance
tests for the new mechanism, not red-then-green fixes for a shipped bug —
flagging that plainly rather than overclaiming); and
`test_an_added_line_starting_with_plus_plus_does_not_break_reflow_detection`
in `tests/test_restatement.py` (genuinely red — the `++`/`-- ` collision
in `restatement.py` specifically breaks `_wanted_whole_lines`'s own
reflow-noise suppression, which the existing `test_text_the_diff_also_re_added_is_not_reported`
test doesn't cover since it has no colliding line in its fixture).

Filed ticket 34 for the duplication `/code-review` flagged between
`git.py`'s and `restatement.py`'s now-near-identical state machines —
real, but a bigger refactor than fits this ticket's own fix, and doing it
immediately after three rounds of catching my own mistakes in this exact
code risked a fourth.

Verified: full suite (`python3 -m unittest discover -s tests -p
'test_*.py'`) — 146 passed. `uv run pyright claims tests` — 0 errors, 0
warnings, 0 informations. `/code-review` run five times on this diff as
it evolved — the first three passes each found one genuine, distinct bug
(the `-- ` mirror collision, the deleted-file phantom entry, then a
`path`/`awaiting_header` redundancy plus a missing `restatement.py` test
for the `++` case), all fixed; the last two passes found nothing further.
