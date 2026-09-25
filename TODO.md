# TODO

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
