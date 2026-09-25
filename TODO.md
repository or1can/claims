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
