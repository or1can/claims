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

**Status:** ready-for-agent

- [ ] Decide and document where the cache persists and what invalidates it
      (a new commit on `HEAD`? a config change?).
- [ ] A regression test proves the second invocation over an unchanged
      history does less work than the first (e.g. mocks/counts `git log
      -p` invocations), and that a cache-invalidating change (a new
      commit) is still picked up correctly.
