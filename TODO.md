# TODO

- `claims/hook.py`'s `_is_git_commit` (ticket 37) doesn't recognize a git
  alias resolving to `commit` (`git cm -m x`, a common `alias.ci = commit`)
  — only the literal `commit` token in subcommand position, so an aliased
  commit lands with the gate silently skipped. Surfaced by `/code-review`
  during ticket 36; out of scope there (no `hook.py` change in that diff).
- Same file, same function: `shlex.split` collapses a `bash -c "..."` /
  `sh -c "..."` / `eval "..."` argument into one token, so a `git commit`
  wrapped that way is never seen as its own `git` token — the docstring's
  "residual accepted gap" list doesn't mention this one. Also surfaced
  during ticket 36's review, also out of scope there.
- `claims/runner.py`'s `run()` looks up a check's `claims.toml` section by
  `config.get(name, {})` — a mistyped or wrong-case table name (e.g.
  `[executable_claims]` for the real `[executable-claims]`) silently
  resolves to `{}`, no error. Pre-existing, but ticket 36's `exclude`
  option is the first place this makes a typo look like a working
  opt-out instead of just an ignored, inert section. Surfaced by
  `/code-review` during ticket 36; fixing it means validating config
  table names against the registry, out of scope for that ticket.
