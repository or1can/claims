# TODO

- `check_config_defaults.py` (ticket #17) has no fenced-code-block
  awareness — a claim shaped `` `NAME` defaults to `value` `` inside a
  ` ``` ` fence (e.g. a docs page's own illustrative example of this
  check's syntax) is scanned as a real claim, not skipped as example
  content. `check_env_vars.py` (ticket #18), `check_file_refs.py`
  (ticket #16) and `check_cli_flags.py` (ticket #19) all fixed this via
  the fence-state pass now shared as `claims.markdown.fence_state`; #17
  shipped before the gap was noticed and hasn't been revisited. Cheap to
  port (an import and two lines), just not done yet.
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
- `restatement` has no `.scratch/*` exclusion, so the frozen archive is
  still swept for both retracted lines and survivors. Excluding
  `CHANGELOG.md` there (#53) newly reported three findings, two of them in
  `.scratch/claims-consolidation/spec.md`, the changelog having been the
  second surviving copy holding them under `duplication_threshold`. (The
  third, in `claims/hook.py`, is a real duplicate the changelog had been
  masking, and wants no exclusion at all.) Adding
  the glob wasn't in #53's scope — its acceptance criteria are measured
  against exactly the two globs it names — and unlike `stale-claims`, a
  retracted line still asserted in the archive isn't obviously noise, so
  this wants deciding rather than copying across.
