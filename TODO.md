# TODO

- `stale-claims` has no output cap (`top = N`) or churn floor
  (`min_percent`). Diff-scoping it (#155,
  `decisions/0009-stale-claims-is-diff-scoped.md`) removed the fixed
  per-commit ranking that prompted them; revisit if a wide-range audit
  is too long to read. A short history ranks high too: "100% of its
  history" for a file with seven commits (#199,
  `.out-of-scope/generated-subjects-and-history-weighting.md`).
- `stale-claims` scores a subject on `git log` of its current path,
  without `--follow`. A section naming a file by bare name (`` `a` ``,
  `` `notes.txt` ``) resolves to the new path of a rename, whose history
  starts at the rename, so the rename alone ranks the section at 100%:
  in the commit hook too, which counts the pending change as one more
  commit (#248). An explicit path names the old path too, and is
  unaffected. Following
  renames would change every subject's score. Found reviewing #230.
- `stale-claims` counts an uncommitted insertion just after a linked
  section's last line as a change to that section, even when the
  inserted lines open with a heading of their own. Once committed, those
  lines belong to the new section, so `git log -L` over the linked one
  doesn't count them. The pre-commit run over-counts by one, which is the
  direction that misses less. Found reviewing #248.
- `restatement` reads an extension with no row in its built-in comment
  table (`.ts`, `.go`) whole-line, code included, so a removed line of
  code there is still reported as a retraction. A `claims.toml` key that
  adds a row of the same shape (line-comment tokens, block delimiters,
  nesting, docstrings) is the likely fix.
- `claim-trees --kind superseded` finds the superseding change by
  following the Status note's line back through every edit to where it
  was first added. A note written onto the end of an older line, such as
  `Accepted.`, is followed back to that line's own commit, so the claim
  is read at a tree older than the change. Every "Amended by" note in
  `decisions/` is its own paragraph, so none is affected, though ADR
  0004's `Accepted.` line, later extended, has that shape; following the
  words that name the replacement, not the line, would cover it. A claim
  over several lines is named from one of them, so a past claim whose
  lines came in different commits is read at that line's commit alone.
  And a note line edited in the working tree has no history to follow,
  so it supersedes there, at `HEAD`; its unedited lines still name the
  change.
- `claims.markdown.SENTENCE_RE`'s fallback for a paragraph's unterminated
  tail is `\S.+$`, so a one-character tail is dropped: `It runs. X`
  yields only `It runs.`. Found reviewing #154; out of that ticket's
  scope.
- `spliced-docs`'s Rust walk back from an item to its doc comment looks
  for a doc marker only at the start of a line, and for an attribute
  only where `#[` starts one. So `/* x` / `*/ /** doc */` / `fn a() {}`
  and `/** Doc.` / `*/ #[inline]` / `fn a() {}` both read `a` as
  undocumented, though rustdoc documents it. rustfmt never writes
  either shape. Fixing the first needs `_rust_code` to report doc
  openers partway along a line; the second needs the attribute scan,
  shared with Swift, to read the comment-free view. Found reviewing
  #168.
- Checks read git's output with `subprocess.run(text=True)`, whose
  universal-newline mode turns a lone `\r` into `\n` before
  `claims.lines.git_lines` or `iter_diff` sees it, while git ends a line
  at `\n` only. A diff, blame or blob (`blob_text`, which `stale-claims`
  numbers a section from) holding a lone `\r` still shifts every later
  line's number against git's. The fix is decoding git's bytes without
  translation. Files in the working tree are read through
  `claims.lines.tracked_text` since #191. Found working on #185.
- Re-reading an expired mark is always a full re-read of its unit and
  subjects (#259). Where only a subject changed, reading just that
  subject's diff against the recorded reading would be cheaper, but the
  saving is unmeasured and a narrower reading is exactly the gap marks
  exist to close; deferred as an early optimisation. It may wait on
  ratect's settle-design/ready work.
- `claims.markdown.slug` drops every character outside `[a-z0-9 _-]`
  after lowercasing, so a non-ASCII letter is dropped where GitHub's own
  anchor rule keeps it: `## Café` is `#caf` here and `#café` on GitHub,
  and `check-links` reports a link GitHub resolves. Found by the reading
  agent reading `docs/checks/check-links.md` on #259.
- A git merge driver for `claims.checked.toml` in ordinary branch
  merges, deferred from #241. `fold-approvals` has one for its own
  rebase only, where the replayed commit winning is right (ADR 0017);
  an ordinary merge has no such side. Sorting the file by key keeps two
  branches marking different files from conflicting; one is worth
  building if ratect's next milestone still shows marks-file conflicts
  after sorting. Known design points: it is installed per clone with
  `git config merge.<name>.driver`, since `.gitattributes` alone can
  only name one; it merges three-way against the base, so an entry one
  side pruned stays deleted; and a mark has no timestamp to decide
  which is newer when both sides marked the same key.
- The reading agent's verdicts (`true`, `false`, `not checked`) and
  `judgment-agent`'s (`confirmed`, `refuted`, `inconclusive`) line up
  one to one, and `CONTEXT.md`'s **Verdict** names neither set
  (`decisions/0019-claims-are-intended-current-superseded-or-past.md`). Merging them
  changes `judgment-agent`'s output contract and its page; worth doing
  if a session handling both agents' results keeps translating between
  them.
- `historical` has two meanings
  (`decisions/0019-claims-are-intended-current-superseded-or-past.md`): to
  `check-file-refs` and `check-links` a mention resolves at the commit
  that wrote it, a past claim's tree; to `restatement` and
  `judgment-agent` only the lines a diff adds are read. Worth splitting
  into two keys (#264). The first is a file-level stand-in for a
  claim's kind, so a current claim in a `historical` file, such as a
  decision's link, passes if it held at its writing; a split could
  narrow that.
