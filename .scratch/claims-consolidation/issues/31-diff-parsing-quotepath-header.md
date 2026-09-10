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

**Status:** ready-for-agent

- [ ] A file whose name contains a non-ASCII character, added alongside a
      normal file in the same diff, has its added lines correctly
      attributed to itself (not folded into another file's entry, not
      dropped) by `added_lines_by_file`.
- [ ] The same case for `restatement.py`'s `_diff_by_file`/`_in_scope`: an
      in-scope extension with a quotable filename is still recognized as
      in scope.
- [ ] A regression test for each call site, using a real `git diff`
      invocation against a `Repo` fixture with a quotable filename — not
      a hand-typed diff string.
