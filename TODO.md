# TODO

- The commit hook's manifest (`claims/hooks.json`) names `bash`, `sh`,
  `zsh` and `eval` by bare command, so a commit inside `/bin/zsh -c`,
  `/bin/bash -c` or `/bin/sh -c` never starts the hook, verified live
  (#85). `_is_git_commit` already handles the path form; the gap is only
  in Claude Code's `if` matching. Closing it means either a handler per
  likely path or dropping `if` and paying a Python start on every Bash
  call — a tradeoff to settle in its own ticket.
