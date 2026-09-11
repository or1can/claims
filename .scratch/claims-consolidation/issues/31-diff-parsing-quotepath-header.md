# 31 — diff-header parsing breaks under `core.quotepath` (default `true`)

**What to build:** both `claims/git.py`'s `added_lines_by_file` and
`claims/checks/restatement.py`'s `_diff_by_file` parse `git diff` header
lines (`+++ b/<path>` / `--- a/<path>`) with a plain string match. Git's
default `core.quotepath=true` wraps any path containing a non-ASCII
character, tab, quote, or backslash in C-style quotes —
`+++ "b/caf\303\251.md"` instead of `+++ b/café.md` — which neither
parser's match accounts for.

Found while fixing ticket 27 (diff-header *prefix* scheme handling);
distinct bug, same failure class, deliberately left out of that fix's
scope.

Confirmed concretely in both call sites:

- `claims/git.py:69` (`added_lines_by_file`): the quoted header doesn't
  match `line.startswith(f"+++ {_DST_PREFIX}")`, so `path` keeps
  whichever file's path it last held — added lines from the
  quoted-filename file get silently folded into the *previous* file's
  entry instead of being dropped or erroring.
- `claims/checks/restatement.py`'s `_in_scope` (~line 103-104) matches via
  `line.endswith(tuple(extensions))`; a quoted header ends in a trailing
  `"` (`...café.md"`), so the extension match fails and that file's
  added/removed lines are silently excluded from `restatement`'s
  comparison — a genuine retraction or claim addition in that file goes
  unchecked with no signal.

Consider whether a `git diff -z` (NUL-terminated, unquoted paths) or
passing `-c core.quotepath=false` to the `git diff` invocation avoids
needing to parse quoted syntax at all — likely simpler than writing a
C-quote unescaper by hand.

**Blocked by:** none.

**Status:** resolved

- [x] A file whose name contains a non-ASCII character, added alongside a
      normal file in the same diff, has its added lines correctly
      attributed to itself (not folded into another file's entry, not
      dropped) by `added_lines_by_file`.
- [x] The same case for `restatement.py`'s `_diff_by_file`/`_in_scope`: an
      in-scope extension with a quotable filename is still recognized as
      in scope.
- [x] A regression test for each call site, using a real `git diff`
      invocation against a `Repo` fixture with a quotable filename — not
      a hand-typed diff string.

## Answer

Took the ticket's own suggested route: `-c core.quotepath=false` on every
git subprocess call, rather than writing a C-quote unescaper. Disables
quoting for a non-ASCII byte specifically — a literal double-quote,
backslash, or control character in a filename is always C-quoted by git
regardless of this setting, so that narrower case is deliberately left
unhandled (rarer, and the same unescaper tradeoff would apply).

Centralized as `claims.git.QUOTEPATH_OFF`, used by `tracked_files` and
`added_lines_by_file` in `claims/git.py`, and imported by
`restatement.py`'s own `_diff_by_file` — a first pass fixed each call
site with its own copy of the flag and rationale; `/code-review` flagged
the duplication given `claims/git.py`'s whole reason for existing is
"shared git plumbing used by more than one check," so it's a real,
importable constant now, not three copies of the same two strings.

The same review pass also caught that `tracked_files` itself (used by
`restatement.py`'s survivor-reading, and every other check that reads
tracked files) had the identical gap one level up — `git ls-files`, not
`git diff` — which the ticket's own two named call sites didn't cover but
share the same root cause. Fixed in the same commit since it was the same
one-line change to the same shared function, with its own regression test
and the restatement check's own "survivor side" direction test (the
`café.md` file keeping the sentence, not the one retracting it).

A third, out-of-scope sibling instance in `judgment_agent.py`'s own local
`_git` helper (a separate implementation from `claims.git`) has the same
gap for `git ls-tree` — filed as ticket 33 rather than folded in here,
since it's a different file's helper, not one of this ticket's two named
call sites or its own `tracked_files` dependency.

Verified: full suite (`python3 -m unittest discover -s tests -p
'test_*.py'`) — 141 passed. `uv run pyright claims tests` — 0 errors, 0
warnings, 0 informations. `/code-review` run twice — first pass found the
`tracked_files` gap and the duplication (both fixed above), second pass
on the updated diff found nothing further.
