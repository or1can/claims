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
- `claims.markdown.SENTENCE_RE`'s fallback for a paragraph's unterminated
  tail is `\S.+$`, so a one-character tail is dropped: `It runs. X`
  yields only `It runs.`. Found reviewing #154; out of that ticket's
  scope.
- `spliced-docs`'s Rust walk back from an item to its doc comment looks
  for a doc marker only at the start of a line, and for an attribute
  only where `#[` starts one. So `/* x` / `*/ /** doc */` / `fn a() {}`
  and `/** Doc.` / `*/ #[inline]` / `fn a() {}` both read `a` as
  undocumented, though rustdoc documents it. rustfmt never writes
  either shape. Fixing the first needs `_rust_code` to report doc
  openers partway along a line; the second needs the attribute scan,
  shared with Swift, to read the comment-free view. Found reviewing
  #168.
- Checks number a file's lines with `str.splitlines()`, which also
  breaks on U+2028, U+2029, `\x0b`, `\x0c`, `\x1c`–`\x1e` and `\x85`,
  while git numbers lines by `\n` only. A file holding one of those
  shifts every later line's number against git's, so a finding cites
  the wrong line, and `restatement`'s and `judgment-agent`'s
  `historical` skip can take an added line for a shipped one or the
  reverse. About 34 call sites; splitting on `\n` alone is the likely
  fix. Found reviewing #174.
