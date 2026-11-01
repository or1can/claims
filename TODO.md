# TODO

- `stale-claims` has no output cap (`top = N`) or churn floor
  (`min_percent`). Diff-scoping it (#155,
  `decisions/0009-stale-claims-is-diff-scoped.md`) removed the fixed
  per-commit ranking that prompted them; revisit if a wide-range audit
  is too long to read.
- `restatement` reads an extension with no row in its built-in comment
  table (`.ts`, `.go`) whole-line, code included, so a removed line of
  code there is still reported as a retraction. A `claims.toml` key that
  adds a row of the same shape (line-comment tokens, block delimiters,
  nesting, docstrings) is the likely fix.
- `claims.git.added_lines_by_file` counts an old last line with no
  newline as added when anything is appended after it (git shows it
  removed and re-added, its text unchanged), so `claim-words` and
  `temporal-words` treat that untouched line as new. `restatement`
  works around it in its own whole-file walk; the helper sees only
  `--unified=0` hunks, so fixing it there means reading git's
  `\ No newline at end of file` marker.
- `claims.markdown.SENTENCE_RE`'s fallback for a paragraph's unterminated
  tail is `\S.+$`, so a one-character tail is dropped: `It runs. X`
  yields only `It runs.`. Found reviewing #154; out of that ticket's
  scope.
