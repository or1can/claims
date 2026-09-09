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

**Status:** ready-for-agent

- [ ] A golden fixture derived from the `361b2fb` → `158a56d` `ratect`
      instance (or an equivalent constructed case, if porting the real prose
      verbatim isn't practical) is added under
      `tests/fixtures/judgment_agent_golden/`.
- [ ] The judgment-agent's actual verdict on that fixture is recorded and
      reported — not assumed either way.
- [ ] If it currently misses this shape of claim, that's either fixed or
      documented explicitly as a known limitation — matching this repo's own
      "a tool must measure and publish what it misses" principle
      (`doc-integrity-tooling.md` §5.2), not left as an unremarked gap.
