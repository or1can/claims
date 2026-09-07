# 14 — Judgment-agent candidate mechanism

**What to build:** the deterministic half of the judgment-agent — a check
that (1) builds a subject index from code, (2) computes the diff-scoped
touched-subject delta (which subjects were added/removed/renamed by this
diff specifically), and (3) matches prose against that closed set via
citation-shaped token extraction. Registered as an **advisory** check
producing ranked candidates, each carrying both the citing `file:line` and
the diff evidence for why the subject counts as touched.

**Blocked by:** 06.

**Status:** resolved

- [x] Given a fixture repo where a diff renames a symbol, prose citing the
      old name in a file the diff never touched is still surfaced as a
      candidate — not missed the way diff-scoping-by-file would miss it.
- [x] Given a fixture repo where the claim and its subject are edited in the
      same commit, the subject is still surfaced (not scored to zero the
      way churn-ranking would).
- [x] Every candidate carries the citing `file:line` and the commit(s) that
      touched the subject.
- [x] Never issues a clean "nothing to review" verdict when candidates
      exist — it ranks, it doesn't clear.

## Answer

Built as `claims/checks/judgment_agent.py`, registered `judgment-agent`
(advisory, `gate=False`) — not a port, per ticket 04's research: no
surveyed tool computes the diff-scoped touched-subject delta this needs.

Three operations, per ticket 04's Answer:

1. **Subject index** — every name tracked `*.swift`/`*.rs` declares, reusing
   `spliced_docs.SWIFT_DECL_RE`/`RUST_ITEM_RE` (the same "what does this
   repo declare" answer `check-citations` and `spliced-docs` already
   share).
2. **Touched-subject delta** — the subject index built once at `diff_range`'s
   base revision and once at its head (the working tree, for a plain
   single-revision `diff_range`; `A..B`/`A...B` splits at the separator).
   The symmetric difference of the two name sets is the delta — a binary
   before/after set-diff, not a decaying churn score, so a same-commit
   claim-and-subject move is still caught (criterion 2). A rename is an
   unpaired remove-and-add; pairing is left unsolved, matching every
   surveyed tool.
3. **Citation match** — every backtick citation (`check_citations.CITATION_RE`)
   in tracked `*.md` tested for exact membership in the delta — closed,
   code-derived vocabulary, never open keyword search.

Each candidate carries the citing `file:line` (the `Finding`'s own
`file`/`line`) plus, in its message, the subject's declaration site and any
commit(s) already covering the change — or, for the common case (a
`PreToolUse` hook runs *before* `git commit` completes, so the change is
usually still uncommitted), that's named explicitly rather than left as an
empty-looking gap. No filtering step exists that could discard a real
candidate as "probably fine" (criterion 4); removed-subject candidates rank
before added ones.

Tests: `tests/test_judgment_agent.py` (9 cases) — the rename-in-an-untouched-
file case, the same-commit move, uncommitted vs. committed evidence, added-
subject candidates, Rust as well as Swift, an unrelated diff producing no
findings, ranking order, and the CLI never failing on an advisory finding.
111 tests total across the suite, all green.

Post-review (`/code-review`, Standards + Spec axes), fixed before landing:

- The module docstring claimed `git.py`'s `added_lines_by_file` already
  documents the "not a real merge-base" simplification for `A...B` ranges —
  it doesn't; that file only documents its diff-header-prefix limitation.
  Reworded to state the simplification as this check's own choice.
- `check()` called `_commits_touching` once directly and `_evidence` called
  it again internally for the same subject file — the same `git log`
  subprocess ran twice per citation. Fixed by computing it once and passing
  the result into `_evidence`.
- `base_rev`/`head_rev` travelled as a loose pair through three call sites;
  bundled into one `_Endpoints` NamedTuple.
- Documented two known-imprecision edge cases rather than leaving them
  silent: the subject index keeps only a name's first declaration (by
  sorted file path) when more than one tracked file declares the same
  name, and "commit(s) that touched the subject" is scoped to the
  declaration's whole file, not its declaration line. Both bias toward
  showing more evidence, never toward dropping a real candidate.
