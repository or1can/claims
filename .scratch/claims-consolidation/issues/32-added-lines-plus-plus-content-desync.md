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

**Status:** ready-for-agent

- [ ] An added line whose content starts with `++` is recorded as added,
      at the correct line number.
- [ ] Every added line after it in the same hunk keeps the correct line
      number (no off-by-one desync).
- [ ] A regression test covers this case using a real `git diff`
      invocation against a `Repo` fixture, not a hand-typed diff string.
