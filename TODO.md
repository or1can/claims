# TODO

- `claims/git.py`'s `added_lines_by_file` (ticket 10, promoted from
  `claim_words.py`'s own diff parser in the follow-up gardening commit)
  only recognizes git's default `+++ b/<path>` diff-header prefix —
  inherited as-is from Project B's `tools/claim-words.py`, its source. A
  repo with `diff.mnemonicPrefix` or `diff.noprefix` set produces a
  different prefix, and `claim-words` silently sees zero added lines for
  the whole run rather than erroring. Not fixed here — out of ticket 10's
  scope.
- `claims/runner.py`'s `run()` has no per-check exception isolation: a
  check that raises (a malformed check-specific config value, a `git diff`
  against an unborn `HEAD`) propagates straight out of `run()` and crashes
  the whole CLI invocation, including any gate checks that would otherwise
  have passed. This contradicts an advisory check's "never fails the run"
  promise at the runner level, not just within each check's own logic.
  Noticed while implementing ticket 10; belongs to whichever ticket next
  touches `runner.py`/`cli.py`.
- `claims/checks/claim_words.py`'s `_is_retired_quote` (the "is this a live
  claim or a retired quotation" house style — blockquote, whole-sentence
  italics, or a fixed lead-in phrase) is private to that one check. If a
  future check (e.g. ticket 11's `spliced-docs`) needs the same judgment,
  promote it to a shared module instead of reimplementing it.
