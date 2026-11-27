# 0021. A reading batch is only as large as a golden run proves

## Status

Accepted. Issue #274; builds on
`decisions/0018-the-reader-and-the-approver-are-recorded-apart.md` and
`decisions/0019-claims-are-intended-current-superseded-or-past.md`.

Amended by #281, which corrects the account of the batched runs in the
Decision. All four packed ten findings from eight unrelated roots into
one call, which the Decision forbids of a reading batch, so they don't
show how a real one does, and the harness reported only the first
problem it met. The failed run that listed a sentence from beyond a
section also returned a false claim `true`: it gave two findings that
share a subject and need opposite verdicts each other's verdict. The
other failed run returned the undelivered claim `false`, but of kind
current. The cap stays at 1. "Passed with on every repeat" means no
failed run in 20 of that size, where any failure rejects the size,
whether verdict, kind, unit or other. The `--batched` run the
Consequences name is now `--stress`, and never sets the cap; the runs
the cap rests on are `--batch-size`'s, of findings from one root that
share subjects.

Amended by #284, which measured them and leaves the cap at 1: on sonnet
(`claude-sonnet-5-5`, Claude Code 2.1.311) a batch of 2 failed on its
fifth run, and no larger size was run. One finding listed a sentence from
past the end of its own section, with every verdict right; the sentence
was not the other finding's, and that finding alone had no failed run in
20, so the batch isn't shown to have caused it. The stress pack of
unrelated findings failed 16 of 20. `docs/reading-agent.md` holds the
runs.

Amended by #290: a `true` verdict resting on a search alone, a claim of
absence included, is settled or made `not checked` before its finding is
marked, not only reported, and so is one citing lines the agent didn't
open, or no file. A finding whose named subject wasn't
opened in full is re-sent, or the session reads the subject. Each such
reading is notable, beside those the Decision lists.

Amended by #287, which replaces the bar. It was changed after #284's
result was known, and departs from #281's rule that any failure rejects a
size, so #284's runs don't count towards it. No rule of the agent's
contract is relaxed. The cap stays at 1, and no size has been measured
against the new bar. A problem now weighs what it would do to a mark:

- **Rejecting**, any one of which rejects a size: a false claim returned
  `true` or not reported; another finding's claim listed; a current or
  intended claim called past or superseded; and the unit, a named subject
  or a needed tree not opened, or only partly read. So is any problem in
  none of these lists, such as missing evidence or a `not checked` that
  should have been settled.
- **Compared** with its rate alone: a `true` verdict none of whose cited
  files was opened with `Read`, or citing lines of an opened one that no
  `Read` covered. Evidence that names no file there is, or lines of one
  that isn't, is reported apart. It weighs against the reading batch as
  this does, and not for the rate alone.
- **Counted**, and only recorded: a sentence from the finding's own page
  outside its unit; a true claim returned `false`; any other error of
  kind; and a `matching` error, a finding with no object or two or an
  object for none.

A `call` failure from outside the agent is still discarded and run again,
and any other is rejecting. A size passes with no rejecting problem in at
least 60 runs that each return an object for every finding, and with the
compared problem's rate no worse than its margin allows. That rate is
measured per finding read, on the same findings each read alone equally
often, at least 60 readings in all. The one-sided 95% upper bound on the
batched rate less the alone rate, resampling whole calls, has to be
within the alone rate itself, so at most double, or within 5 percentage
points where the alone rate is below 5%. Resampling bounds a few rare
problems too low, and none at all at 0, so the bound is never below the
one for none, where the batched rate is the highest with a 5% chance of
seeing none in that many calls. Too few runs to reach the margin is a
size not accepted. Claims listed per finding are recorded, batched and
alone, and effort is pinned. No cap above 1 rests on the small root
alone.

Amended by #289, before any of its runs: the cap rises only to 5 or 10.
Size 5 is run first and 10 only if 5 passes, each at a fixed 60 runs, so
2 and 3 are not measured and set no cap. This tightens #287's bar and
relaxes nothing in it.

Amended again by #289's runs, which set the cap at 5. On sonnet
(`claude-sonnet-5-5`, Claude Code 2.1.311, effort medium), the large
root's ten findings were each read alone 30 times, with no rejecting or
`unopened` problem, so each size's margin is 5 percentage points. A
batch of 5 then passed in 60 runs, with no rejecting problem and a
bound of 0.049 on the compared problem's difference. A batch of 10 had
no rejecting problem in 60 runs, but its bound of 0.052 is over the
margin, so it isn't accepted. Every compared problem was one finding's
absence claim returned `true` on evidence citing a file without its
directory, or no line.
`docs/reading-agent.md` holds the runs.

Amended by #296, before any of its runs. The agent's contract is
tightened: every path it writes, in every field of its report, is given
from the root, never as a bare file name, and a path in a tree is the
same relative path. The harness still counts a bare file name as
evidence naming no file. The cap of 5 stands under that contract. Size
10 is measured again, over 200 batched calls, against each of the large
root's ten findings read alone 60 times, all on `claude-sonnet-5-5`,
Claude Code 2.1.311, the version installed when this was written, at
effort medium with auto-update off, every run saving the same contract
digest. The runs are made in chunks: each finding's 60 readings alone
as one chunk, then size 10 as ten chunks of `--repeat 20`, each chunk in
its own `--output-dir`, and all are summarised together. The count is
fixed in advance: a pause never ends the runs early, and a call that
fails on a usage limit is a `call` failure from outside the agent,
discarded and run again. This relaxes nothing in #287's bar.

Amended again by #296's runs, which leave the cap at 5. All 800 ran on
`claude-sonnet-5-5`, Claude Code 2.1.311, effort medium, under one
contract digest, and no call failed. Size 10 was run in three chunks
of 20, 20 and 160 rather than ten of 20, the count unchanged. Its 200
calls each returned a report for every finding, with no rejecting
problem and a bound of 0.015 on the compared problem's difference,
within the 0.050 margin. It still doesn't pass: one of the privacy
finding's 60 readings alone returned a bare object rather than an array,
a counted `matching` problem leaving no reading, so the findings weren't
each read alone equally often. Nothing was run again and no part of the
bar was changed after the result. The tightened contract left no
evidence naming a file without its directory; the 4 compared problems
cited a search alone. #302 tracks the output slip, and how the bar
counts a reading alone with no report, before size 10 is measured again.
`docs/reading-agent.md` holds the runs.

Amended by #304, before any of the next runs, settling #302's first two
items. It relaxes nothing in #287's bar:

- A reading alone that returns no report still records its `matching`
  problem. It is not counted as a reading, and the finding is run alone
  again until it reaches the fixed count, so every finding is still read
  alone equally often. The count is fixed in readings, not calls. The
  harness takes it as the most readings any of the findings has alone.
- Each finding is run alone at most twice the fixed count. A finding
  that can't reach the count within that leaves the size not accepted.
- A batch of one that returns a bare object stays a `matching` problem.
  The contract is not relaxed to accept it.
- A final message that holds the array but isn't only the array, fenced
  or with prose before or after it, is a new counted problem, `format`,
  recorded only. The array is still read from it.
- #296's runs don't count towards the amended bar. Size 10 is measured
  again with fresh runs under the amended contract, as #287 set out for
  its own bar.

The contract's output example was a fenced, pretty-printed single object.
It is now an unfenced array of one object, beside a sentence saying the
reply carries no fence, and the contract ends by restating that the final
message is the array alone. The prompt the harness sends is unchanged, as
it has to stay the session's own dispatch.

Amended by #302, before any of its runs. The cap of 5 stands under
#304's contract. Size 10 is measured again as #296 measured it: 200
batched calls, against each of the large root's ten findings read alone
60 times, all on `claude-sonnet-5-5`, Claude Code 2.1.311, at effort
medium with auto-update off, every run saving the same contract digest.
Each finding's readings alone are one chunk, and size 10 is run in
chunks of `--repeat` adding up to 200, each chunk in its own
`--output-dir`, all summarised together. A finding short of 60 readings
alone, by a run that returned no report, is run alone again with
`--only`, each re-run in its own `--output-dir`, until it has 60, and
never more than 120 times in all. The count is fixed in advance: a pause
never ends the runs early, and a call that fails on a usage limit is a
`call` failure from outside the agent, discarded and run again. This
relaxes nothing in #287's bar.

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
- **Enforce the output's shape with `--json-schema`** (#304). The CLI's
  structured output would hold the agent to an array, but the harness
  doesn't use it: the plugin's real path is the Agent tool, which takes no
  schema, so the golden runs would measure a call the session never makes.
- **Batch the judgment agent too.** Its golden harness has no batched
  run, and its contract and the skill's "never batched" rule were set
  apart from this one. Left for a follow-up with its own measurements.

## Consequences

- `claims/subagent/reading_agent.md` takes a list and returns a bare
  JSON array, and the check-claims skill's marking section is a numbered
  procedure: choose, group, dispatch, check, re-send for trees, read
  the evidence, settle what the agent couldn't reach, mark, report.
- `python3 scripts/run_reading_agent_golden.py --batched` is the run
  the cap rests on, recorded in `docs/reading-agent.md`. Until it passes
  every repeat at some size, a commit's findings cost what they did
  before.
- `CONTEXT.md` defines **Reading batch** and **Notable reading**.
- Marks written before this from a batched reading keep their `, batched`
  suffix; `claims` puts no format on `by`, and nothing reads the suffix.
