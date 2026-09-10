# 29 — `check_citations._declared_ever` re-walks full Swift history on every run

**What to build:** `claims/checks/check_citations.py`'s `_declared_ever`
re-walks the whole repository's history (`git log -p` over every `*.swift`
commit) on every invocation, with nothing persisted between runs. Fine at
this repo's own scale; on a large, long-lived Swift repo run as a
`PreToolUse` hook on every commit, this cost is paid in full every single
time.

No concrete consuming project currently hits this — this repo is Python,
not Swift, so `_declared_ever`'s Swift-history walk is dormant here today.
Logged proactively (not `wontfix`) so it's picked up before a real
large-repo Swift adopter feels it, rather than after.

The fix needs a cache keyed on the last-seen commit SHA (persisted where —
a dotfile in the consuming repo? a `.claims/` cache dir? — is itself a
design decision this ticket should settle, not assume) so repeated
invocations only walk history since the last cached point.

**Blocked by:** none.

**Status:** resolved

- [x] Decide and document where the cache persists and what invalidates it
      (a new commit on `HEAD`? a config change?).
- [x] A regression test proves the second invocation over an unchanged
      history does less work than the first (e.g. mocks/counts `git log
      -p` invocations), and that a cache-invalidating change (a new
      commit) is still picked up correctly.

## Answer

Cache lives at `<real git dir>/claims-cache/check-citations.json` — the
*real* git dir via `git rev-parse --git-dir`, not an assumed
`repo_root/.git`, so a linked worktree resolves to its own shared gitdir
rather than a directory that isn't there. Living under the git dir means
it's never tracked (no `.gitignore` entry needed) and a fresh clone
starts cold automatically.

Invalidation: keyed on `HEAD`'s sha, checked via `git merge-base
--is-ancestor`. Same sha as cached → return the cached set outright, no
`git log` call at all. Cached sha still an ancestor of the new `HEAD` →
walk only `cached..HEAD` and union into the cached set. Cached sha no
longer reachable (history rewritten — amend, rebase, force-push) → fall
back to a full walk, same as a cold cache; never errors, never
under-reports. `check()`'s `config` doesn't affect what `_declared_ever`
walks today, so no config-keyed invalidation is needed.

A read/parse/write failure on the cache file is always a miss or a
no-op, never an exception — caching is an optimization on top of
`_declared_ever`'s existing correctness, not a new correctness
requirement of its own.

Added `_cache_path`, `_load_cache`, `_save_cache`, `_is_ancestor`, and
`_declared_in_range` (the old `_declared_ever` body, now parametrized
over a single rev or an `a..b` range) to `claims/checks/check_citations.py`.

Three regression tests in `tests/test_check_citations.py`
(`CheckCitationsHistoryCacheTests`): a second invocation over unchanged
history makes zero `git log` calls (spying on `subprocess.run`, per the
ticket's own suggested approach); a commit added after caching is still
picked up; history rewritten since the cached sha still finds the dead
citation via the full-walk fallback. Confirmed genuine red on the
call-count test against the pre-change code (`1 != 0`); the other two
were already green pre-change since caching didn't yet exist to go
stale — expected, they pin correctness-preserved, not new behavior.

Verified: full suite (`python3 -m unittest discover -s tests -p
'test_*.py'`) — 137 passed. `uv run pyright claims tests` — 0 errors, 0
warnings, 0 informations. `/code-review` run on the diff — no findings.
