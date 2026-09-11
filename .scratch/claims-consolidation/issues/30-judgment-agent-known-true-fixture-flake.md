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

**Status:** resolved

- [x] Run `known_true` (and ideally `known_false`, as a control) enough
      times in a row (e.g. 10+) to get a real failure-rate estimate, not a
      3-sample anecdote.
- [x] If the failure rate is low/consistent with ordinary model variance,
      document that rate explicitly somewhere durable (this ticket's
      `## Answer`, or a comment near the harness) instead of leaving it as
      an unquantified "sometimes flaky."
- [x] If the failure rate suggests a real prompt-following gap (not just
      variance), tighten `claims/subagent/judgment_agent.md`'s instructions
      (e.g. make "you must Read the cited file before verdicting" more
      explicit/forceful) and re-run to confirm the fix moves the rate.

## Answer

**Failure-rate estimate.** Ran both fixtures via a one-off harness against
`scripts/run_judgment_agent_golden.py`'s own `_run_fixture` (not committed —
pure measurement, `/tmp/judgment_agent_flake_probe.py`). Combined with this
ticket's own reported history:

| fixture | pre-fix runs | failures | rate |
|---|---|---|---|
| `known_true` | 14 (2 from ticket 22's session, 1 sanity re-run this session, 10-run probe) | 3 | ~21% |
| `known_false` (control) | 11 (1 sanity re-run, 10-run probe) | 0 | 0% |

The asymmetry — `known_true` fails intermittently, `known_false` never does,
same claim text, same-sized fixture repo — rules out (a) generic model
variance affecting the harness uniformly and points at (b): a real, if
intermittent, prompt-following gap specific to `known_true`'s shape. Every
observed `known_true` failure was the same mode: no `Read` tool call on
`cache.py`, evidence stitched together from `Grep`/`Glob` context lines
instead — plausible specifically because `cache.py` is 23 lines, small
enough that a wide-context `Grep` can look like it already shows "the whole
file" without an actual `Read`.

**Tightened `claims/subagent/judgment_agent.md`**: "The one hard rule"
now names the tool explicitly — "open every site it touches **with the
`Read` tool**... a `Grep`/`Glob` match, even one shown with several lines
of surrounding context, is a location, not a reading... however short or
simple the file looks" — closing the "small file, wide-context grep feels
like reading" gap the failures shared, rather than leaving it as prose
"read every site" the model could satisfy with a good-enough `Grep`.

**Post-fix re-run**: `known_true` 10/10 passed, `known_false` 10/10 passed
(no regression). `known_true`'s evidence text also shifted qualitatively —
every one of the 10 post-fix runs says "read in full" / "whole file read"
explicitly, versus a roughly even split of that phrasing pre-fix. A single
10-run post-fix batch can't fully rule out the ~21% rate persisting at
lower incidence (P(0/10) at a true 21% rate is ~11%, not negligible) — flagging
that honestly rather than overclaiming the fix is proven. But the change is
low-risk (control fixture unaffected, `/code-review` found nothing), well
targeted at the specific failure mode every observed failure shared, and
moved the observed rate from ~21% to 0% over 10 more runs — reasonable to
ship without further probing.

Verified: full suite (`python3 -m unittest discover -s tests -p
'test_*.py'`) — 137 passed (unaffected — no Python changed).
`uv run pyright claims tests` — 0 errors, 0 warnings, 0 informations.
`/code-review` run on the diff — no findings.
