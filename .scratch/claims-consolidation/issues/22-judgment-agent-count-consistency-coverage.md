# 22 — Confirm (or close) the judgment-agent's coverage of count-consistency claims

**What to build:** ticket 19 routed `ratect`'s fourth named historical
failure — "ratect 0.5.0 ships 0.26.0's two fixes", actually three
(`361b2fb` → `158a56d`) — to the judgment-agent (ticket 15) by elimination:
none of the four mechanical checks (`executable-claims`, `restatement`,
`stale-claims`, `spliced-docs`) claims to reconcile a count across two
documents, and `doc-integrity-tooling.md`'s own §4 coverage table doesn't
list it as covered by anything built there either. That routing was never
actually tested — "belongs to the judgment-agent" was an argument from what
the mechanical checks structurally can't do, not a confirmed capability of
what the judgment-agent structurally can.

Port the real instance into a golden fixture, the same way
`tests/fixtures/judgment_agent_golden/known_true`/`known_false` already
work: a claim ("this release ships N changes") against a small repo/changelog
fixture where the true count is known, and check what verdict the
judgment-agent actually returns.

**Blocked by:** 15.

**Status:** resolved

- [x] A golden fixture derived from the `361b2fb` → `158a56d` `ratect`
      instance (or an equivalent constructed case, if porting the real prose
      verbatim isn't practical) is added under
      `tests/fixtures/judgment_agent_golden/`.
- [x] The judgment-agent's actual verdict on that fixture is recorded and
      reported — not assumed either way.
- [x] If it currently misses this shape of claim, that's either fixed or
      documented explicitly as a known limitation — matching this repo's own
      "a tool must measure and publish what it misses" principle
      (`doc-integrity-tooling.md` §5.2), not left as an unremarked gap.

## Answer

Ported an equivalent case, not the literal `ratect` prose — the real
instance lives in a foreign repo's history, not this one, and the shape
(a count stated in one doc, the list it's counting in another) is what
matters, not the exact wording. New fixture:
`tests/fixtures/judgment_agent_golden/count_consistency_known_false/`:

- `claim.md`: "`CHANGELOG.md`'s Unreleased section lists the bug fixes
  release 0.5.0 ships from upstream 0.26.0 — two of them, per
  `ROADMAP.md`." (`CHANGELOG.md` cited first deliberately — see below.)
- `repo/ROADMAP.md`: states "two bug fixes".
- `repo/CHANGELOG.md`: an Unreleased/Fixed section listing **three**
  entries — the same "stated count disagrees with the actual list"
  shape as the real `361b2fb`→`158a56d` instance (two claimed, three
  actual).
- `expected_verdict.json`: `refuted`.

Ran `scripts/run_judgment_agent_golden.py` (real `claude -p` call, per its
own docstring — not assumed):

```
[PASS] count_consistency_known_false: verdict='refuted' evidence='CHANGELOG.md:7-9 (three entries under Unreleased ### Fixed: #101, #102, #103); ROADMAP.md:5'
```

`/code-review` caught a real gap in the first draft: the harness's
mandatory-`Read` check (`_cited_file` in `run_judgment_agent_golden.py`)
only requires the *first* backticked filename in `claim.md` to be read,
and the first draft cited `ROADMAP.md` first — the file that just restates
"two," not `CHANGELOG.md`, the file whose three-entry list is the actual
disproof. As written, the fixture could have passed on a verdict grounded
in nothing but the claim's own restated number. Fixed by reordering the
citation (`CHANGELOG.md` first), re-verified live:

```
verdict='refuted' evidence='CHANGELOG.md:7-9 (three bullets under Unreleased/Fixed) vs ROADMAP.md:5 ("Ships upstream 0.26.0's two bug fixes.")'
```

Evidence cites both files, and the tool-call transcript shows a `Read` of
`CHANGELOG.md` — now mechanically enforced, not just observed this once —
before the verdict, not a lucky grep. **The judgment-agent does not miss
this shape of claim**; ticket 19's elimination-based routing (no
mechanical check reconciles a count, so it falls to the judgment-agent) is
now a tested, not just argued, capability. No fix needed; nothing to
document as a limitation for this shape.

Incidental, unrelated finding while running the harness (both existing
fixtures ran alongside the new one in the same invocation): the
pre-existing `known_true` fixture failed twice in a row in this session —
the model produced the correct `confirmed` verdict but with zero `Read`
tool calls in its transcript, exactly the un-grounded-verdict failure mode
ticket 15's harness exists to catch. A third, manual run of the same
fixture *did* call `Read` and passed. This is the harness's own documented
nondeterminism (`run_judgment_agent_golden.py`'s module docstring: "not
guaranteed deterministic across model versions"), not a regression
introduced here and not this ticket's scope — recorded in `TODO.md`
instead, belonging to whichever ticket next touches ticket 15's fixtures
or the subagent prompt.
