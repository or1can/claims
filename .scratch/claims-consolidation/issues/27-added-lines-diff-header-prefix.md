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

**Status:** resolved

- [x] `added_lines_by_file` correctly parses added lines from a diff
      generated with `diff.mnemonicPrefix=true` and one with
      `diff.noprefix=true`, not just the default `a/`/`b/` prefix.
- [x] A regression test covers at least one non-default prefix scheme
      against a real `git diff` invocation (not a hand-typed diff string),
      matching this repo's existing `Repo`-fixture test style.
- [x] If full parsing isn't practical for some prefix scheme, that scheme
      produces a loud failure (raised exception or a Finding), never a
      silent zero.

## Answer

Fixed by pinning the `git diff` invocation's header prefix rather than
parsing multiple schemes: `added_lines_by_file` in `claims/git.py` now
passes `--src-prefix=a/ --dst-prefix=b/`, which overrides
`diff.mnemonicPrefix`/`diff.noprefix` config and makes the `+++ b/<path>`
header always come out in git's default form, regardless of repo config.
The parser's hardcoded `"b/"` match is now backed by a `_DST_PREFIX`
constant shared with the command args, closing the coupling a reviewer
flagged (edit one, not the other, and the bug silently comes back).

Added `test_a_non_default_diff_header_prefix_does_not_lose_added_lines`
to `tests/test_git.py`, `subTest`-parametrized over `diff.mnemonicPrefix`
and `diff.noprefix`, against a real `Repo` fixture. Added a `Repo.config`
helper to `tests/support.py` so the test doesn't hand-roll the `git
config` subprocess call.

Two pre-existing, unrelated bugs turned up by review during this fix —
both out of scope here, filed as their own tickets rather than folded in:
`core.quotepath`-quoted filenames break header parsing in both this
function and `restatement.py`'s equivalent (ticket 31); added lines whose
own content starts with `++` get dropped and desync subsequent line
numbers (ticket 32).

Verified: full suite (`python3 -m unittest discover -s tests -p
'test_*.py'`) — 132 passed. `uv run pyright claims tests` — 0 errors, 0
warnings, 0 informations. `/code-review` run on the diff (5 parallel
angles); the literal-duplication and test-duplication findings fixed in
the same commit; two pre-existing out-of-scope bugs filed as tickets 31
and 32 instead of fixed here.
