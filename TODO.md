# TODO

- Same ticket, a latent trap for future tests rather than a current bug:
  `tests/test_hook.py` and `tests/test_cli.py` register fake check names
  (`gate-check`, `clean-check`, `spy`, `any-check`, ...) rather than the
  real registry. The first test added to either file that writes a *real*
  check's table (e.g. `[executable-claims]`) into a fixture `claims.toml`
  will trip #21's own unrecognized-table gate as a spurious finding,
  since that real name isn't among the fakes actually registered in that
  test's registry state. Worth a one-line comment in those fixtures'
  registry setup when next touched, not a standalone fix.
- `claim_words.py` carries its own `_files`/`_designated` pair rather than
  calling `config.string_list_config` and `config.path_matches`, which do
  the same two jobs for every other check. `_designated` uses plain
  `fnmatch.fnmatch`, whose case folding is platform-dependent — the exact
  defect `path_matches`' own docstring says it exists to avoid, so the
  same `files` glob can match on macOS and not on Linux. `temporal_words.py`
  (ticket #52) calls the shared helpers; swapping `claim-words` over is a
  three-line change, but it alters a shipped check's matching on one
  platform, so it wants its own commit and a changelog entry rather than
  riding along with a new check.

- `claim_words._files` is a private copy of `config.string_list_config`,
  same coercion, same comment; noticed while documenting the check, left
  because folding it in touches `claims/` for no consumer-visible change.
