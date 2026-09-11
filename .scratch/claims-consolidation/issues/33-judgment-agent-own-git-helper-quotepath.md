# 33 — `judgment_agent.py`'s own `_git` helper has the same quotepath gap ticket 31 fixed elsewhere

**What to build:** `claims/checks/judgment_agent.py` has its own local
`_git` helper (line 127) — separate from `claims.git`'s shared plumbing,
and not updated by ticket 31 — that shells out to `git` without
`claims.git.QUOTEPATH_OFF`. `_files_at_ref` (line 188) uses it for `git
ls-tree -r --name-only <ref>`, then filters with
`rel.endswith((".swift", ".rs"))` (line 197).

Found during ticket 31's `/code-review` pass, out of scope for that
ticket's two named call sites (`claims/git.py`, `restatement.py`).

Same failure shape as ticket 31: with `core.quotepath` at its default
(`true`), a tracked `.swift`/`.rs` file with a non-ASCII character in its
name comes back from `git ls-tree` as a C-quoted string
(`"caf\303\251.rs"`), which doesn't end in `.rs` — `rel.endswith((".swift",
".rs"))` is `False`, so that file is silently dropped from
`_files_at_ref`'s result. A symbol declared only in that file, at the ref
being compared against, would then look like it was never declared there —
wrong input to whatever `check()` (line 236) does with the two file sets.

`_files_working_tree` (line 179) is unaffected — it goes through
`claims.git.tracked_files`, already fixed by ticket 31.

Fix: either import and use `claims.git.QUOTEPATH_OFF` in this file's own
`_git` (simplest — matches ticket 31's fix exactly), or replace the local
`_git` helper with `claims.git`'s shared plumbing if a suitable function
exists for `ls-tree`/`show` (it doesn't yet, so the simpler fix is likely
right).

**Blocked by:** none.

**Status:** resolved

- [x] A tracked `.swift` or `.rs` file with a non-ASCII character in its
      name, present at `ref`, is included in `_files_at_ref`'s result (not
      silently dropped by the `.endswith` filter).
- [x] A regression test using a real `git` repo fixture (a `Repo` with a
      quotable filename, committed, read back via `_files_at_ref` or
      through `check()`'s public seam) — not a hand-typed `ls-tree` string.

## Answer

Took the simpler of the ticket's two options: `judgment_agent.py`'s own
`_git` helper now passes `claims.git.QUOTEPATH_OFF`, same as `git.py` and
`restatement.py`. Applies uniformly to all three of `_git`'s call sites
(`ls-tree`, `show`, `log`) since they all share the one helper.

Added `test_a_quotable_filenames_declaration_at_base_is_still_seen` to
`tests/test_judgment_agent.py` — same shape as the existing rename test
(`test_a_rename_falsifies_a_citation_in_a_file_the_diff_never_touched`),
but the declaring file's own name has a non-ASCII character, exercising
`_files_at_ref`'s `git ls-tree` call through the public `check()` seam.
Confirmed genuine red against committed code (`0 != 1`) before applying
the fix.

Verified: full suite (`python3 -m unittest discover -s tests -p
'test_*.py'`) — 147 passed. `uv run pyright claims tests` — 0 errors, 0
warnings, 0 informations. `/code-review` run on the diff — no findings.
