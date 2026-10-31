# TODO

- `claims/gate.py`'s `_disabled_checks` reads a check's own `enabled` by
  truthiness, so `[stale-claims] enabled = 0` silences that check and
  `enabled = "false"` does not: the same defect #129 fixed for `[hook]
  enabled`, left out of that ticket's scope.
- `restatement` reads an extension with no row in its built-in comment
  table (`.ts`, `.go`) whole-line, code included, so a removed line of
  code there is still reported as a retraction. A `claims.toml` key that
  adds a row of the same shape (line-comment tokens, block delimiters,
  nesting, docstrings) is the likely fix.
