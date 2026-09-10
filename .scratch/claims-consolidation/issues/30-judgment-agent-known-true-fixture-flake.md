# 30 — Investigate `known_true` golden fixture's ungrounded-verdict failures

**What to build:** `tests/fixtures/judgment_agent_golden/known_true`
(ticket 15) failed twice in a row during ticket 22's session
(`python3 scripts/run_judgment_agent_golden.py`, then a standalone rerun
of just that fixture) with **zero `Read` tool calls** in the subagent's
transcript — even though its final `confirmed` verdict happened to be
correct. That's the exact ungrounded-verdict failure mode
`run_judgment_agent_golden.py` exists to catch (see its module docstring
and the harness's `cited_file`/`Read` check), not a false alarm in the
harness — it correctly failed the fixture both times.

A third, manual run of the same fixture *did* call `Read` and passed. So
this is either (a) genuine model nondeterminism the harness's own
docstring already warns about ("not guaranteed deterministic across model
versions"), or (b) a real, if intermittent, prompt-following regression in
`claims/subagent/judgment_agent.md` worth tightening. Undetermined from
three runs — needs a real investigation, not another single anecdotal run.

**Blocked by:** 15.

**Status:** ready-for-agent

- [ ] Run `known_true` (and ideally `known_false`, as a control) enough
      times in a row (e.g. 10+) to get a real failure-rate estimate, not a
      3-sample anecdote.
- [ ] If the failure rate is low/consistent with ordinary model variance,
      document that rate explicitly somewhere durable (this ticket's
      `## Answer`, or a comment near the harness) instead of leaving it as
      an unquantified "sometimes flaky."
- [ ] If the failure rate suggests a real prompt-following gap (not just
      variance), tighten `claims/subagent/judgment_agent.md`'s instructions
      (e.g. make "you must Read the cited file before verdicting" more
      explicit/forceful) and re-run to confirm the fix moves the rate.
