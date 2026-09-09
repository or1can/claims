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
- `claims/checks/check_links.py`'s `SLUG_STRIP_RE` (`[^a-z0-9 -]`) strips
  underscores when computing a heading's anchor slug; GitHub's real slugger
  keeps them. Any heading containing one — a backtick-quoted identifier like
  `` `RUST_LOG` ``, or a word like `additional_args` — gets a slug that never
  matches its own real anchor, so a correct link to it is reported as a
  **gate** failure. Confirmed against `ratect`, computing `_slug()` directly
  against the real headings rather than eyeballing the anchor text: 7 of the
  12 `check-links` gate findings on `main` (pinned at `5aded18`) are this one
  root cause. The other 5 are unrelated, real bugs worth naming separately
  rather than lumping in: 2 are genuinely wrong anchors in `ratect`'s own
  `ROADMAP.md`; 2 point at headings that were renamed and never updated to
  match; 1 is `check_links.py` refusing to read through a symlink
  (`CLAUDE.md` → `AGENTS.md`). Noticed while running ticket 19's parity
  validation against `ratect`'s real tree; not fixed here since
  `check_links.py` belongs to ticket 13, not this ticket's scope
  (07/08/09/11).
- `docs/agents/issue-tracker.md`'s Resolve convention says to append a gist
  pointer to `map.md`'s Decisions-so-far. No ticket from 07 onward has done
  this — `map.md` hasn't been touched since ticket 05, and each ticket's own
  `## Answer` carries the gist instead (see this file's ticket-15 entry
  above, which already names `spec.md` as `map.md`'s successor for this
  purpose). Noticed a second time, independently, during ticket 19's
  code-review pass; recording once more here since two independent notices
  is worth more than the first was — still a docs-only clarification
  belonging to whichever ticket next touches `issue-tracker.md`, not a
  regression in any implementation ticket.
