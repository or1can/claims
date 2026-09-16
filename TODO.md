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
- Same ticket, a latent trap for future tests rather than a current bug:
  `tests/test_hook.py` and `tests/test_cli.py` register fake check names
  (`gate-check`, `clean-check`, `spy`, `any-check`, ...) rather than the
  real registry. The first test added to either file that writes a *real*
  check's table (e.g. `[executable-claims]`) into a fixture `claims.toml`
  will trip #21's own unrecognized-table gate as a spurious finding,
  since that real name isn't among the fakes actually registered in that
  test's registry state. Worth a one-line comment in those fixtures'
  registry setup when next touched, not a standalone fix.
- Ticket #16's `check-file-refs` excludes any path already inside real
  Markdown link syntax (`[text](path)`) from its own detection, per that
  ticket's own acceptance criteria — but `check-links` itself only
  validates a link destination naming another `.md` file (with or without
  `#anchor`) or a bare `#anchor`, not any other extension. So a broken
  link destination naming some other recognized extension (e.g.
  `[the script](scripts/foo.py)` where `foo.py` doesn't exist) is
  currently unflagged by either check. Named in `check_file_refs.py`'s own
  module docstring as a known, deliberate gap; narrowing it means either
  broadening `check-links`' own scope past `.md`/anchors, or excluding
  only the subset of link destinations `check-links` actually validates —
  either is bigger than #16's own scope.
- Discovered while building #16, not fixed there since it's a different
  file: `stale_claims.PATH_RE`'s leading `\b` word-boundary anchor doesn't
  match between two non-word characters, so it silently drops the leading
  dot off a real hidden-directory path in prose — `.github/workflows/ci.yml`
  matches with its own leading dot dropped, which then never resolves to
  the tracked file it should. Harmless for `stale-claims` today — a wrong
  match just fails to resolve and drops out of its own ranking, the same tolerance
  that let this go unnoticed — but it does mean `stale-claims` can never
  correctly rank a citation of a dotfile/dotdir path as a subject.
  `check_file_refs.PATH_RE` (ticket #16) fixes the same defect in its own
  copy via a negative lookbehind instead of `\b`; porting that fix here
  needs its own verification pass against `stale-claims`' existing ranking
  output and tests, out of scope for #16.
- `check_config_defaults.py` (ticket #17) has no fenced-code-block
  awareness — a claim shaped `` `NAME` defaults to `value` `` inside a
  ` ``` ` fence (e.g. a docs page's own illustrative example of this
  check's syntax) is scanned as a real claim, not skipped as example
  content. `check_env_vars.py` (ticket #18) and `check_file_refs.py`
  (ticket #16) both fixed this via `_fence_state`; #17 shipped before the
  gap was noticed and hasn't been revisited. Cheap to port (three lines,
  the pattern already exists twice), just not done yet.
