# 27 — `added_lines_by_file` only recognizes git's default diff-header prefix

**What to build:** `claims/git.py`'s `added_lines_by_file` (ticket 10,
promoted from `claim_words.py`'s own diff parser) only recognizes git's
default `+++ b/<path>` diff-header prefix — inherited as-is from Project
B's `tools/claim-words.py`, its source. A repo with `diff.mnemonicPrefix`
or `diff.noprefix` set produces a different prefix (`+++ w/<path>`, or no
prefix at all), and `added_lines_by_file` silently sees zero added lines
for the whole run rather than erroring.

This is worse than it sounds for a plugin whose entire premise is "a tool
must measure and publish what it misses" (`doc-integrity-tooling.md`
§5.2): every check built on `added_lines_by_file` (at least `claim_words`)
would silently pass everything in an affected repo, with no signal that
anything was skipped.

Fix `added_lines_by_file`'s header parsing to recognize any diff-header
prefix scheme (mnemonic, no-prefix, or default), or — if that's not
practical — make the mismatch loud (raise, or emit a Finding saying diff
parsing failed) instead of silently returning zero added lines.

**Blocked by:** none.

**Status:** ready-for-agent

- [ ] `added_lines_by_file` correctly parses added lines from a diff
      generated with `diff.mnemonicPrefix=true` and one with
      `diff.noprefix=true`, not just the default `a/`/`b/` prefix.
- [ ] A regression test covers at least one non-default prefix scheme
      against a real `git diff` invocation (not a hand-typed diff string),
      matching this repo's existing `Repo`-fixture test style.
- [ ] If full parsing isn't practical for some prefix scheme, that scheme
      produces a loud failure (raised exception or a Finding), never a
      silent zero.
