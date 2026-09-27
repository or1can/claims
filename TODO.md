# TODO

- The commit hook's manifest (`claims/hooks.json`) names `bash`, `sh`,
  `zsh` and `eval` by bare command, so a commit inside `/bin/zsh -c`,
  `/bin/bash -c` or `/bin/sh -c` never starts the hook, verified live
  (#85). `_is_git_commit` already handles the path form; the gap is only
  in Claude Code's `if` matching. Closing it means either a handler per
  likely path or dropping `if` and paying a Python start on every Bash
  call — a tradeoff to settle in its own ticket.

- `claim-words` reads sentences inside fenced code blocks, where
  `temporal-words` blanks them first (`_prose_lines` in
  `claims/checks/temporal_words.py`). A verbatim capture on a swept page
  therefore fires it: `docs/installation.md`'s plugin inventory block
  reports advisory findings ("added to every session", "~81 tok") that no
  wording change can fix, since the block is captured output. Blanking
  fences in `claim-words` the same way is a `claims/` change with its own
  version bump, so it wants its own ticket.
