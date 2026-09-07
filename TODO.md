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
- `claims/checks/check_citations.py`'s `_declared_ever` re-walks the whole
  repository's history (`git log -p` over every `*.swift` commit) on every
  invocation, with nothing persisted between runs. Fine at this repo's
  scale; on a large, long-lived Swift repo run as a pre-commit hook, this
  cost is paid in full on every single commit. Noticed while implementing
  ticket 12; a fix would need a cache keyed on the last-seen commit SHA,
  which is a bigger change than this ticket's scope.
- `claims/checks/check_citations.py`'s `_findings_in` doesn't de-duplicate:
  the same dead name cited twice in one line produces two identical
  `Finding`s (same file/line/message). Harmless noise for an advisory
  check, but this one is a **gate** check, so a commit gets blocked with a
  duplicated reason for what is really one problem. Noticed while
  implementing ticket 12; not fixed there since it's cosmetic, not a
  correctness gap.
- `docs/agents/issue-tracker.md`'s Resolve convention ("append a context
  pointer to the map's Decisions-so-far in `map.md`") describes the
  5-ticket wayfinder phase (tickets 01–05), already fully resolved and
  superseded by `spec.md` via `/to-spec`. No implementation ticket since
  (06 through at least 15) touches `map.md` on resolve, and none should —
  the map no longer tracks their state, `spec.md` and each ticket's own
  `## Answer` do. The doc's wording doesn't say this convention stopped
  applying once the map was collapsed, which reads as a live requirement
  every later ticket is silently skipping. Noticed while implementing
  ticket 15 (a `/code-review` finding flagged the "violation" against the
  literal text); not fixed here since it's a docs-only clarification
  belonging to whichever ticket next touches `docs/agents/issue-tracker.md`.
