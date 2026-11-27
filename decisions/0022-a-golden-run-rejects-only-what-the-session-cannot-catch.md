# 0022. A golden run rejects only what the session cannot catch

## Status

Accepted. Issue #308; supersedes the bar in
`decisions/0021-a-reading-batch-is-only-as-large-as-a-golden-run-proves.md`,
as #287 and its amendments set it, and leaves the rest of 0021 standing.
This relaxes the bar, and it is the first change to it that does. Every
amendment before it tightened the bar or left it as it was.

Written before any run under it. The cap stays at 5 until runs under this
bar set it.

Amended by #308, reopened, before any run under it: each size's batches
now hold all ten of the large root's findings. As written, a size read
alone and batched only its own findings, and `--batch-size` takes the
root's first N, so size 5 was always `01` to `05`. A cap of 5 would have
rested on half the fixture, never on `06` to `10`, among them
`06-hold-length`, the root's only claim that isn't current. Size 5 and
size 10 couldn't be compared, since a failure at 10 could be the five
extra findings as well as the larger batch. And 300 readings alone left
almost no room: two problems not caught alone would have rejected size 5.
`06` to `10` aren't one reading batch either. `06` to `08` name only the
root's ledger, and `09` and `10` only its planner, so the check-claims
skill's step 2 would send them as two.

- **Size 5 is two named batches**, `5a`, of `01`, `02`, `04`, `05` and
  `06`, which all name the ledger, and `5b`, of `03`, `07`, `08`,
  `09` and `10`, joined through `03`, which names both files. Each is
  run 100 times, so size 5 is still 200 calls and 1,000 readings.
  **Size 10 is one batch**, `10`, of all ten, run 200 times.
- **All ten findings are read alone 60 times**, re-runs as the Decision
  sets them, and one set of runs alone serves every size. That is 600
  readings alone, whose bound with none observed is about 0.0050.
- The batches are named once, as the harness's `BATCHES`, and each is run
  with `python3 scripts/run_reading_agent_golden.py --batch <name>`. Each
  batch's `elsewhere` claims are the other findings in that batch.

The Decision's runs are rewritten to say so, since none had been made
under them. The bar is otherwise unchanged: the bound on problems not
caught and the cost comparison, over a size's calls together, against the
same findings alone. This amendment relaxes nothing in it.

## Context

0021's bar rejected a size on any one rejecting problem. The agent
samples, so at any rejecting rate above zero the chance of passing falls
as runs are added. At a true rate of 1%, a size passes 55% of the time
over 60 runs but only 13% over 200. Size 5 passed on 60 runs. Size 10
failed twice on 200, with 2 rejecting problems in 200 batched calls
against none in 600 readings alone, a one-sided Fisher p of about 0.06.
More runs made size 10 harder to pass. They didn't measure it better.

The bar also graded the agent as if its output went straight into a mark.
It doesn't. The check-claims skill checks every reading before marking,
and since #299 `claims.cli check-reading` makes that check a command. Both
of #302's rejecting problems were ones that check flags. `03-planning`
left a named subject out of `read`. `04-audit` listed a note of its own
as a claim, `not checked`. Each costs a re-send or a read of the
session's own, which is tokens, not a wrong mark.

#308's count of 534 real readings, in the maintainer's sessions from 23
to 27 November 2026, found that the session's checks catch a lot, and
that batching didn't make a follow-up more often needed. But 7 marks were
written with a subject only partly read, and 3 with the unit absent from
`read`. Problems the session could have caught still reached a mark when
catching them was left to its attention. So "caught" here means what the
command flags, never what a session might notice.

## Decision

**A problem is caught when the session's own check flags it before any
mark.** That is exactly what `claims.reading.check_reading` flags on the
agent's array, which the harness calls itself, with no copy of its
parsing, plus any claim `not checked`. Every problem the harness finds is
in one of three classes:

- **Not caught, rejecting:**
  - a false claim returned `true` or not reported;
  - a claim the fixture expects that the agent never lists;
  - a current or intended claim called past or superseded;
  - another finding's claim, or another page's, listed (`unit-other`);
  - a file `read` lists in full that no `Read` call opened, or opened only
    in part, and a `true` claim citing a file, or lines of one, that `read`
    gives but `Read` didn't open (`unopened`);
  - a tree file the fixture needs read that `read` doesn't list, which
    `check_reading` doesn't hold `read` to;
  - a `call` failure not from outside the agent, which counts as a
    problem in each finding of its call. Alone, it is also no reading, so
    its finding is run alone again towards the count, as one with no
    report is;
  - any problem in none of these lists, such as a claim that isn't an
    object.
- **Caught, priced:**
  - everything `check_reading` flags: a finding with no object or two, or
    an object for none (`matching`); a unit or named subject missing from
    `read`, or listed with only part of it (`read`); a `true` claim citing
    a file not in `read`, or lines outside its entry (`cited`), or naming
    no file (`no-file`); an object listing no claims (`no-claims`);
  - a claim `not checked` that the fixture doesn't expect so;
  - a claim with no evidence, which counts as naming no file.
- **Counted, recorded only:** `format`, `unit-own-page`, a true claim
  returned `false`, and any other error of kind.

The compared class is retired, and its margin against the alone rate
with it. Everything that was in it is now caught or not caught.

**A caught problem costs a reading alone of its finding.** A finding with
one or more caught problems in a call is priced as one re-send, at the
mean tokens of that finding's readings alone, since the session re-sends
a finding once however many items it flags. An object for no finding sent
is set aside, so it costs nothing.

**The bar has two parts:**

1. The rate of problems not caught, per finding read, has a one-sided
   95% upper bound of at most 1%. The bound is computed by resampling
   whole calls, since one call's readings share a context. It is never
   below the bound for none observed, the rate per reading with a 5%
   chance of none in that many readings. The same bound holds for the
   same findings each read alone.
2. A batch's mean tokens per finding, input, cache and output, plus its
   caught re-sends priced as above, is below the mean tokens per finding
   read alone. This is a point estimate, with no bound. Readings alone
   are priced at their own tokens, with no re-sends of their own, and a
   run alone with no report, no reading, prices nothing.

**The runs are fixed now, before any of them:**

- 200 batched calls per size, no more and no fewer, split evenly between
  its named batches: 100 each of `5a` and `5b` for size 5, and 200 of
  `10` for size 10. A call with no object for a finding is still one of
  them. Its other findings are readings.
- Each of the large root's ten findings is read alone 60 times, as 0021
  set out through #304, and one set of runs alone serves every size: a
  reading alone with no report is no reading, and the finding is run
  alone again, at most 120 times in all. That is 600 readings alone,
  whose bound with none observed is about 0.0050.
- Size 5 is run first, and size 10 only if 5 passes. The cap becomes the
  largest size that passes, or 1 if 5 fails. Until then it stays at 5.
- Pins as #302 set them: `claude-sonnet-5-5`, Claude Code 2.1.311 or the
  version installed when the runs start, recorded with them, effort
  medium, auto-update off, and one contract digest. Chunks and re-runs as
  #302 set them, each in its own `--output-dir`.
- Only fresh runs count. #296's and #302's runs stay in
  `docs/reading-agent.md` as history, and are evidence for nothing here.
- A pause never ends the runs early. A call that fails on a usage limit
  is discarded and run again.

**The harness grades saved runs again.** `--saved` and `--alone` grade
each run from its final message and `Read` calls, not by the problems it
was saved with, so runs saved under an earlier bar can be summarised
under this one. Whoever holds #302's runs may grade them again to check
the code. That is not evidence on this bar.

## Alternatives considered

- **Keep the zero bar.** Any one rejecting problem rejects a size, so
  the more runs a size gets, the less likely it is to pass. The bar would
  punish measuring a size well. It also rejects a size for a problem the
  session's check would catch before any mark, which costs tokens, not
  correctness.
- **Keep the compared margin.** It compared a batched rate with the alone
  rate, and allowed up to double the alone rate. Under this bar every
  problem it covered is caught or not caught. A caught one has a real
  cost, and the cost comparison weighs it. A not-caught one goes into a
  bound with a fixed limit. A margin relative to the alone rate would
  let a batch read worse wherever reading alone already does badly.
- **A rate per call, not per finding read.** A call of 10 holds 10
  readings, so a rate per call makes a larger batch look worse for the
  same quality of reading. With 200 calls and none observed, its bound is
  1.5%, over any 1% limit, so no size could pass. The bound still resamples
  whole calls, which keeps one bad call from counting as many independent
  failures.
- **Price each caught item, not each finding.** One finding with a
  missing subject and the claim citing it has two items, but the session
  re-sends it once. Pricing per item would overstate what batching costs.
- **Price re-sends alone too.** Fairer to a batch, but leaving them out
  keeps the alone cost the plain mean of its calls, and is the stricter
  test of a batch.

## Consequences

- `scripts/run_reading_agent_golden.py` classes every problem as
  rejecting, caught or counted. Its summary gives the bound on problems
  not caught, batched and alone, and the tokens per finding, batched with
  re-sends and alone. It exits 1 when the bar isn't met, or, with no runs
  alone given, on any problem not caught. A saved run now records its
  root, and one saved without it has its root worked out from its `Read`
  calls.
- `claims.reading.Flag` names the file a `read` flag is about, so the
  harness can tell a file `read` lists in full from one it doesn't.
- `docs/reading-agent.md`'s bar is this one. `CONTEXT.md` defines
  **Caught problem**.
- Running the golden runs, and a large-unit fixture or a cap counted in
  claims or trees (#298), are left for later. Their result goes in an
  amendment here.
