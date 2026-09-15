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
- Ticket #21's unrecognized-top-level-table gate only validates
  `claims.toml`, not `claims.local.toml` (ticket #15) — a mistyped
  `[executable_claims]` under the local grant file still silently grants
  nothing today, the same failure mode #21 closed for `claims.toml`.
  Surfaced by `/code-review` during #21; out of scope there since #21 was
  scoped to the mechanical, `claims.toml`-only half of #13's split.
