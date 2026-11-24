# 0021. A reading batch is only as large as a golden run proves

## Status

Accepted. Issue #274; builds on
`decisions/0018-the-reader-and-the-approver-are-recorded-apart.md` and
`decisions/0019-claims-are-intended-current-superseded-or-past.md`.

## Context

The reading agent took one finding per call, and the skill called it
once per finding. The findings one commit raises usually share subjects:
a change to a module raises a finding on every section citing it. Each
call re-read the same files, and each hand-back was another turn of the
calling session re-reading its own long context.

On #264, a one-call-per-finding pass over the commit's 137 findings was
estimated at ~50k tokens each. Read instead in groups sharing subjects,
one agent per group, told to read each finding as if alone and to return
one report per finding, the same findings cost ~14.5k each: 19 agents
for 131 findings, the largest 10 findings and ~170k tokens. The grouped
readings still found 18 claims false, each with file:line evidence.

A reading gets shallower as an agent's context fills, so a group has to
stop somewhere, and the agent's one hard rule, every unit and subject
read in full, has to survive the grouping.

## Decision

**The reading agent takes a list of findings and returns an array.** One
object per finding, of the shape it returned before. A single finding is
a list of one; there is no second mode. Every finding in a list is from
one root. Every rule the agent held one finding to it holds each finding
in the list to, on its own: its unit and every subject read in full,
a verdict and a kind for each claim, and its own trees. One rule is new:
a subject read in full once counts as read for every finding in the list
naming it, at the same tree. The same path at another tree is another
reading.

**The session groups findings by shared subject.** Findings sharing a
subject, transitively, go in one **reading batch**. A finding that
shares none is a reading batch of one, and unrelated findings are never
packed together to fill one. The grouping is the skill's prose; there is
no command for it.

**A reading batch holds at most as many findings as a batched golden run
has passed with on every repeat, and for now that is 1.** The reading
agent's golden harness has a batched run of 10 findings in one call,
including pairs that share a subject and need opposite verdicts, and a
finding passes there only if it comes back as it has to alone. On sonnet
it passed two of four runs. One failed run listed a sentence from beyond
a section as one of its claims; a sentence forbidding that was added to
the contract, a per-finding rule made stricter. The next failed run
reported an undelivered intended claim without its kind. The ten
findings each pass run alone. Optimising the reading cannot come at the
cost of its correctness: a cheaper reading that sometimes strays from
its unit or misreads a kind writes marks that hide false claims. So
every finding is a reading batch of one until a batched run of some size
passes every repeat, and the cap rises to that size. A group larger than
the cap is split, keeping together the findings that share the most
subjects. The cap counts findings, not bytes or tokens: a count is what
the golden run can prove, and what the session can apply without
measuring anything.

**The session reconciles each reading batch before marking from it.**
One object per finding, matched by its `file:line` and mode. An object
for a finding not sent is set aside, a finding with none or two is
re-sent alone, and nothing from that reading batch is marked until each
has one. A finding
needing trees is re-sent with them, without the rest of its reading
batch; the others' verdicts stand.

**`by` is unchanged: `claims:reading-agent (<model>)`.** `by` names the
reader (ADR 0018), and the reader of a batched finding is the same agent
on the same model, held to the same rules. Batching is how the session
dispatched the work. The #264 trial wrote `claims:reading-agent (sonnet),
batched`; that suffix is not carried on.

**The session reports notable readings apart from routine ones.** A
reading is notable when a person approving its mark should see it: a
claim `false`, a claim `not checked`, a claim whose kind isn't current,
a mark written despite a `false` claim, or a verdict resting on a search
alone or on the session's own override. Every other reading is routine.
Approval is unchanged: every mark, routine or not, is `--pending` and
needs a person (ADRs 0014 and 0017).

**The judgment agent stays one candidate per call.** Its rule is left as
it is for now, and revisited with measurements once batched reading has
run.

## Alternatives considered

- **Keep one finding per call, with no list in the contract.** What the
  session does today, at ~3.5 times the tokens per reading on #264. A
  list contract and a batched harness cost nothing while the cap is 1,
  and leave a larger cap one passing run away rather than a contract
  change away.
- **Group by tree.** A commit's findings are mostly current, so this
  makes one or two very large agents, past any cap a golden run could
  prove, and puts findings with nothing in common in one context.
- **Pack unrelated findings up to the cap.** Fewer calls again, but a
  shared subject is what a reading batch saves on; unrelated findings
  save nothing and share a context in which one can leak into another.
- **Set the cap at 10 on the #264 trial and one passing run.** The
  repeats that followed failed, each on a different per-finding rule.
- **A byte or token cap.** Closer to what makes a reading shallow, but
  neither the session nor a golden run can hold one without measuring
  every subject first.
- **Mark a batched reading in `by`**, as the trial did. It records a
  dispatch detail as part of the reader's name, and splits one reader
  into two in every later count of who read what.
- **Batch the judgment agent too.** Its golden harness has no batched
  run, and its contract and the skill's "never batched" rule were set
  apart from this one. Left for a follow-up with its own measurements.

## Consequences

- `claims/subagent/reading_agent.md` takes a list and returns a bare
  JSON array, and the check-claims skill's marking section is a numbered
  procedure: choose, group, dispatch, check, re-send for trees, read
  the evidence, mark, report.
- `python3 scripts/run_reading_agent_golden.py --batched` is the run
  the cap rests on, recorded in `docs/reading-agent.md`. Until it passes
  every repeat at some size, a commit's findings cost what they did
  before.
- `CONTEXT.md` defines **Reading batch** and **Notable reading**.
- Marks written before this from a batched reading keep their `, batched`
  suffix; `claims` puts no format on `by`, and nothing reads the suffix.
