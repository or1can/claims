---
name: check-claims
description: Runs every currently registered claims check against the calling project and reports every finding in one pass. Use whenever the user asks to check claims or verify documentation accuracy at any point mid-task — not only at commit time, which the git pre-commit hook covers once installed.
---

# Check claims

Runs the shared core runner (`claims.runner.run`) via its CLI adapter and
reports the result. This is the on-demand counterpart to the automatic
git `pre-commit` hook — same runner, same checks, just invoked by
request instead of automatically.

## Running it

Run, from anywhere:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m claims.cli --repo-root <path to the project being checked>
```

Add `--diff-range <range>` to check something other than the working tree
against `HEAD` — for example `--diff-range main..feature` to check a whole
branch.

## Reporting the result

Show the user the CLI's output verbatim — every finding line, then its
summary line (`N checked, M finding(s), G gate failure(s)`, then
`, Q quiet while checked` when checked marks kept findings quiet, with
`, P of them partly` after it when partial marks kept some of them,
`, K of them pending` when pending marks did, and
`, A mark(s) added in range` when the range added checked marks, with its
own `, K of them pending` when some of those are pending) —
rather than summarizing or filtering it yourself. Findings that share a citation,
message and severity print as one line listing each mode in its
parentheses, so `M` can exceed the number of finding lines.

The one case to get right: if the runner has zero checks registered, the
CLI prints `0 checked — no checks registered (failure, not a clean pass)`
and exits non-zero. Report that as a failure, exactly as worded — never
read "no findings" or "nothing printed" as a clean pass. This mirrors the
same honesty rule every individual check in this plugin already follows
(most visibly `executable-claims`, which fails a sweep that finds zero
markers for the same reason).

A gate finding (`[GATE] ...` in the output) means something in the checked
project should not be committed as-is; surface it as a blocking problem for
the user to fix, not merely advisory. An `[advisory]` finding is worth the
user's attention but isn't asserting the project is broken.

## A `judgment-agent` finding gets a subagent verdict, not a verbatim line

One exception to "show the CLI's output verbatim": a finding whose `mode`
is `judgment-agent-added` or `judgment-agent-removed` (either name among
the modes in the printed line's parentheses) is a *candidate* for
judgment, not a verdict on its own — `claims/checks/judgment_agent.py` only
computes which claims cite a subject this diff touched, or sit where a
checked mark this diff expired was; it never itself decides whether the
claim is still true. Printing its line and moving on,
the way every other check's finding is handled, would show the user a
data point, not an answer.

For each such finding:

1. Invoke the `claims:judgment-agent` subagent (its plugin-namespaced
   name — e.g. via the Task tool's `subagent_type: "claims:judgment-agent"`)
   once per candidate — never batched, never skipped even when several
   candidates cite the same subject, since each claim earns its own
   reading — passing it the finding's own citation (`file:line`) and
   message verbatim. The message already carries everything the
   subagent's own input contract (`claims/subagent/judgment_agent.md`)
   asks for: the cited subject's name, whether it was added or removed by
   this diff, or that the diff expired its checked mark, and the diff
   evidence for why it counts as touched.
2. The subagent returns exactly one JSON verdict — `confirmed`, `refuted`,
   or `inconclusive`, each with `evidence` (the code actually read, or the
   command actually run) and `reasoning`. Report the verdict back to the
   user alongside the original finding: the citation, what the claim says,
   the verdict, its evidence, and its reasoning — not just the finding's
   own one-line message.
3. This never blocks a commit or the run: like the check that produces
   it, `judgment-agent`'s verdict is advisory only, whatever it says.

This step is the skill's alone: the hook and the command line print the
candidate and invoke no subagent. See "Broadening the search after a refuted
verdict" below for an additional, on-demand step appended to this same
procedure.

### When no subagent can be started

Step 1 needs a way to start a subagent, and an agent that has none — one
running inside a workflow with no Agent or Task tool, for instance —
cannot take it. Such an agent does **not** judge the candidates itself:
it does not read the cited code against the claim in the subagent's
place, and presents no reading of its own as a verdict. Instead it hands
the candidates back unjudged:

- Report every other finding exactly as above; only the judgment step
  changes.
- In place of the verdicts, list every
  `judgment-agent-added`/`judgment-agent-removed` finding together,
  apart from the other findings, under a heading that says they are not
  judged and why — `judgment-agent candidates: not judged (no subagent could be started)`
  — each with its citation (`file:line`) and message verbatim, never
  paraphrased or shortened, since those are exactly what the subagent's
  input contract asks for.
- The caller acts next: whoever invoked this skill, typically a main
  session that does have an Agent tool, dispatches `claims:judgment-agent`
  for each listed candidate, per steps 1–3 above.
- Mark none of these candidates as checked (see "Marking a finding as
  checked" below): a mark written on your own reading would quiet the
  candidate before the caller sees it, which is a verdict by another
  route.

When a subagent can be started, none of this applies.

## Broadening the search after a refuted verdict (on demand)

`judgment-agent` is diff-scoped by design: its candidate list only ever
contains a citation of a subject *this diff* added, removed, or renamed.
Once a candidate's verdict comes back **refuted** (the claim is confirmed
false, per the subagent's own three-way vocabulary above), the subject it
cited may not be a one-off — other prose elsewhere in the tree might cite
that same subject and be equally wrong, without this diff having touched
any of those other citations at all. Nothing in the base procedure above
surfaces them: a citation the current diff never touched never becomes a
candidate, no matter how long it stays wrong.

This step is **on demand only** — invoked when a human or agent chooses to
broaden the search after a refuted verdict, never automatically, and never
for a `confirmed` or `inconclusive` one:

1. Take the refuted candidate's own cited subject name — the same
   backtick token `check_citations.CITATION_RE` already matches (reused
   directly by `judgment_agent.py`, not a second copy of the pattern).
2. Search every tracked Markdown file for every other backtick citation of
   that exact subject name — not just the files or lines this diff
   touched, the whole tree, using the same citation-matching shape
   `check-citations`/`judgment-agent` already use.
3. Feed each newly-found citation through `claims:judgment-agent` for its
   own full verdict, exactly like steps 1–3 of the base procedure above.
   A citation of a subject that's already been refuted once elsewhere is
   **not** itself assumed false by association — that's exactly the
   judgment the subagent exists to make, not something to shortcut.

No new code, no new `Finding` mode, no persisted state (no cache, no
history file, no cross-run memory of verdicts), and no automatic trigger
— this is a documented workflow built entirely from tools an agent
already has (search, then the same subagent invocation from above), not a
new mechanism. Deriving a general shape or pattern from the false claim's
own wording, beyond matching its exact cited subject name, is out of
scope — same-subject citation matching is the concretely implementable
slice of the idea; a fuzzier "same shape" match is a future direction if
this narrower version proves useful in practice.

## Marking a finding as checked

A project can record, in a committed `claims.checked.toml`, that an
advisory finding was read and found true; the finding then stays quiet
until its wording or a file it names changes (the plugin's
`docs/checked-marks.md`). A mark may be written only after the finding
has been read against what it cites — the code, file or section the
sentence names — and what was read found true (all of it, unless the
mark is partial), never on the strength of the finding's own text. A
`judgment-agent` verdict never writes a mark by
itself: when you asked for the verdict, you may mark the finding once you
have read the verdict's evidence, the same as any other finding.

### Reading and marking, step by step

Work through these steps in order, each time you settle findings. Each
step's detail follows it.

1. **Choose the findings to settle.** Settle every finding your own
   pre-commit run shows before you commit: fix a gate finding, which
   can't be marked, and a false advisory one, and read and mark a true
   one from a check that takes marks (the plugin's
   `docs/checked-marks.md` lists them). Any other finding is yours to
   settle only when the user asks. Never mark a finding nobody has read,
   and never mark a false one: fix it instead.

   Commit `claims.checked.toml` in the same commit as the change that
   raises the findings, not in a separate marks commit at the end of a
   branch: the mark then sits beside the edit it is about, and a person
   can fold their approval into that one commit with `fold-approvals`. A
   mark you find missing later, or a rejected mark's fix, goes in a
   `fixup!` commit for the commit it belongs to, so the fold folds it in
   there.

   Each finding's root is the directory holding the tree it was raised
   in. For a `--diff-range` reaching the working tree (`HEAD`, or any
   single ref), that is the project root; for `A..B`, it is a worktree at
   `B`, made outside the project with `git worktree add --detach <dir>
   B` and removed with `git worktree remove <dir>` once its findings are
   read.

2. **Group them into reading batches.** Every markable finding other
   than a `judgment-agent` candidate is read by the
   `claims:reading-agent` subagent, in **reading batches**: findings
   that share a subject go in one reading batch, transitively, so a
   finding sharing a subject with any finding in a reading batch joins
   it. A finding that shares no subject with another is a reading batch
   of one. Never pack unrelated findings together to fill a reading
   batch. A reading batch holds findings from one root only.

   A reading batch holds at most **5 findings**. The cap is set by the
   reading agent's golden runs of whole reading batches: a batch of 5
   passed the bar the plugin's `docs/reading-agent.md` gives, in 60
   runs, and a batch of 10 did not (that page records the runs). A group
   larger than the cap is split, keeping together the findings that
   share the most subjects.

   A `judgment-agent` candidate is never batched, as its own section
   above says: its golden harness has no batched run at all to prove its
   verdicts stay apart, where the reading agent's at least has one to
   raise its cap by.

3. **Dispatch each reading batch.** Hand each reading batch to the
   `claims:reading-agent` subagent (its plugin-namespaced name — e.g.
   the Task tool's `subagent_type: "claims:reading-agent"`), one call
   per reading batch, passing for each finding its finding line
   verbatim, the subjects it names, and its root. When you re-read an
   expired mark, pass its `kind` and `note` from its entry in
   `claims.checked.toml`: the agent infers the kind afresh, with them as
   context. Its input and output contract is
   `claims/subagent/reading_agent.md`; the plugin's
   `docs/reading-agent.md` describes it.

   It returns a JSON array, one object per finding. Each object holds
   one verdict per claim in the finding's unit — `true`, `false` or `not
   checked` — each with the claim's kind (`intended`, `current`,
   `superseded` or `past`) and the evidence for it, the tree it was read
   at and the `file:line` it read, and for the finding as a whole, what
   it read in full, what it only searched, and a draft note. It never
   marks anything.

4. **Check each reading batch's output.** It holds exactly one object
   per finding you sent, matched by its `finding` field, the finding's
   `file:line` and mode. An object naming a finding you didn't send
   counts for none of yours: set it aside. Re-send alone each finding
   with no object or two, and mark nothing from that reading batch
   until every finding in it has exactly one object.

5. **Re-send the findings that need trees.** The agent has no shell, so
   it reads a past or superseded claim in a copy of the tree its kind
   names, which you make. A claim it reports `not checked` with a
   `tree_line` needs one: run

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m claims.cli claim-trees --repo-root <path> --kind past|superseded <tree_line>
   ```

   which prints one tree per line, `<role> <commit> <root>`, with no
   root for `superseded`, the change the claim is read just before, and
   `working-tree` as the commit of a line not yet committed. It makes
   each copy once per commit and reuses it after. `tree-at <REV>` prints
   the root of one commit's copy, for a claim comparing a state the tree
   names to another.

   Hand the agent that finding again with those trees, and the
   `tree_line` each was named from, without the rest of its reading
   batch. Several such findings that share subjects may go together,
   grouped as in step 2. Every other finding's verdicts from the first
   pass stand.

6. **Read the evidence.** Read each object's evidence, the kind
   evidence included: a claim read at an old tree on weak evidence is
   the costly mistake, since it holds there and its mark no longer
   expires with its subjects.

   Then compare each `true` claim's `evidence` with the `read` of the
   same object. The agent sometimes returns `true` from a search alone.
   These are **unsettled**, for step 7 to settle:

   - **a named subject not opened in full:** one the finding names that
     `read` lacks, or gives only part of, whatever its claims cite. A
     subject opened before a step 5 re-send stays opened, and one the
     root no longer holds can't be;
   - **a claim citing a file that isn't in `read`**, at the claim's own
     tree, or lines outside the lines or section its `read` entry gives,
     even where its other cited files were read;
   - **a claim whose evidence names no file;**
   - **a claim that something is absent or unused** ("nothing reads X")
     resting on a search, whatever else was read.

7. **Settle what the agent couldn't reach or didn't open.** For each
   unsettled item from step 6, in this order:

   - **a named subject not opened in full:** hand the agent the finding
     again, alone, with any trees it had, and go back to step 4 with what
     it returns, whose verdict on a claim replaces the earlier one. Or
     read the subject in full yourself, against each claim that rests on
     it, as you do when a re-send leaves it unopened again;
   - **a file or lines it didn't open:** open the cited lines yourself,
     with enough around them to settle the claim;
   - **no file named:** find what settles the claim and open that;
   - **something absent or unused:** search the tracked files yourself,
     such as with `git grep`, which takes a commit for an old tree, open
     every hit, and name the search in the note.

   Work at the claim's own tree. What you find becomes the verdict. A
   claim you find `false` whose `kind_evidence` is a decision record's
   Decision, or wording that decides, has kind `intended`. A claim you
   can't settle is `not checked`.

   A claim the agent itself reports `not checked` is one it couldn't
   read, not one found wanting, and its reasoning says what it would
   need. Route each by that:

   - **a tree:** step 5;
   - **a subject it wasn't given:** hand it the finding again with that
     subject named, and go back to step 4 with what it returns;
   - **a command's output, the history, an issue or the network:** read
     or run it yourself, as the agent would have read a file: `git log`,
     `gh issue view`, the command the claim describes;
   - **nothing you can reach either:** a past run's output you can't
     reproduce, an incident that cites nothing to find it by, a
     repository you can't access, a judgement rather than a fact. Only
     this claim stays `not checked`.

   Where you settled a claim or read a subject yourself, the mark's
   `--by` names you beside the agent, as `claims:reading-agent (<model>),
   with <session or agent name> (<model>)`.

8. **Mark by kind, with `--pending`.** For each finding, from its
   verdicts as step 7 left them:

   - **Every claim `true`:** mark the finding, with `--by
     "claims:reading-agent (<model>)"`, `<model>` being the model it ran
     on, or step 7's form. A batched reading names the same reader:
     batching is how you dispatched the work, not who read it.
   - **Any claim `false`:** fix the prose; never mark it. Two
     exceptions, each yours to decide, not the agent's. An intended
     claim that is `false` may not be delivered yet: fix the code, or
     record a change of direction, or, where the pull request's plan
     delivers it later, mark it, saying in the note that it is not
     delivered. A past or superseded claim that is `false` at its tree is
     in a record whose prose is not rewritten: check its kind evidence,
     and settle it with the user.
   - **A claim still `not checked` after step 7:** in a `stale-claims`
     section or a `spliced-docs` doc comment, mark with `--partial` and
     name the unchecked claim in the note, and why nothing could settle
     it, as long as at least one claim is `true`: a mark on which nothing
     was checked records no reading at all. In any other mode, leave the
     finding unmarked. A full mark always means every claim was
     checked.

   Each claim is read at its own kind's tree, and the unit's verdicts
   combine as one claim's would: the unit is fully marked when every
   claim is `true` at its tree, whatever trees they were read at. Pass
   the unit's kind to `mark-checked` with `--kind`, the least settled of
   its claims' kinds: current if any claim is current (no `--kind`),
   else `intended`, else `superseded`, else `past`. For a superseded or
   past unit, pass `--evidence` once for each file or `page.md#anchor`
   section its claims' kinds rest on, such as a decision record's
   `#status`. A superseded unit needs at least one. Put each claim's
   kind, and the commit a past or superseded claim was read at, in the
   note. Marks of different kinds, or with a different `--by`, go in
   separate batches. "Writing the marks" below gives the command.

9. **Report.** Tell the user which readings are **notable**, the ones a
   person should see before approving a mark. A reading is notable if
   any of these hold:

   1. a claim came back `false`, so the prose was fixed: say what it
      said, what the subject holds, and the fix;
   2. a claim stayed `not checked` after step 7, so the finding got a
      partial mark or none: say why nothing could settle it;
   3. a claim's kind isn't current (past, superseded, or an intended
      claim held as not delivered): give its kind evidence and the tree
      it was read at;
   4. a mark was written despite a `false` claim, the intended "not
      delivered yet" exception;
   5. step 6 found something unsettled, or you overrode, re-read or
      settled a verdict yourself: say what was opened, by you or by the
      agent when re-sent, and what it showed. Reporting it doesn't settle
      it: step 7 does.

   Every other reading is routine. List the notable readings first, each
   with its reason, then the routine ones as a count and one line each.
   When the marks go in a pull request, put the notable list in its
   body's evidence, where the person approving the marks sees it.
   Routine marks are `--pending` like any other, and need a person's
   approval just the same.

When no subagent can be started, read each finding yourself, to the same
rules: the whole unit and every subject it names, each opened in full,
a search hit being a location rather than a reading. Then `--by` names
you and your model, as `<session or agent name> (<model>)`. That
`<name> (<model>)` shape is this skill's convention for `by`; `claims`
itself puts no format on it. A mark written from a `judgment-agent`
verdict names `judgment-agent (<model>)`.

A mark that has expired is read again in full, the same way, its kind
and note passed as context, never as a verdict.

### Writing the marks

Mark a batch, one entry per line, each with a note saying what was
verified, over the same `--diff-range` the findings were reported for:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m claims.cli mark-checked --pending --repo-root <path> --diff-range <range> --by "claims:reading-agent (<model>)" - <<'EOF'
docs/guide.md:3 claim-words-totalising src/cache.py has one reader, get, and nothing else reads the store
EOF
```

One bad entry fails the whole batch and nothing is written; the command
names each bad entry. If you read only part of a `stale-claims` section
or a `spliced-docs` doc comment, say so with `--partial` rather than
only in the note; it is refused for any other mode, and for a finding
whose full mark is still current. Add `--prune` to also remove every
orphaned mark, one reported as `checked-mark` because its sentence was
reworded or removed; it needs no entries and no note, and keeps every
other mark.

Always pass `--pending`, as above, unless the user tells you the reading
is theirs: it records the mark as awaiting a person's review. A pending
mark quiets its finding just the same, so it doesn't hold you up.

### Approving the marks

Approving is a person's step, not yours: never run `approve-marks` or
`fold-approvals --apply` unless the user asks you to. `pending-marks`
lists what awaits their review, each mark with its `by` and its kind. Approving
writes the approver in `approved_by` and leaves `by`, the reader, as it
is.

## Coverage

`claims.cli` imports `claims.checks`, which registers every built-in check
at import time — so the command above always exercises whatever is
currently registered. A later addition to that package reaches this skill
automatically; nothing here needs to change. This is specific to the
normal check pass above — the config-review capability below reads two
hand-maintained maps in `claims/config_review.py`, not the live check
registry, so a new check's own glob-shaped config key needs those maps
updated by hand (a test in `tests/test_config_review.py` fails loud if
that's missed).

## Reviewing whether config actually fits (on demand only)

A second, separate capability (ticket #22) — invoke it only when explicitly
asked to review, sanity-check, or audit the calling project's `claims.toml`
(phrasing like "review my claims.toml", "does my config actually do
anything", "am I missing coverage from a stale exclude"). **Never** run
this as part of the normal check pass above, the automatic hook, or CI —
it produces reasoned prose, not `Finding`s, and has no gate/advisory
severity to report through that pipeline.

A validly-shaped `claims.toml` entry can still be silently inert — a glob
that matches zero tracked files, an `extensions` entry no tracked file
has — and nothing in the normal check pass surfaces that; it only means
whatever that entry was supposed to opt in or out of is quietly not
happening.

1. Load the project's config and compute the mechanical facts — never
   approximate this by re-deriving matching semantics from the raw TOML
   yourself. `repo_root` must be the project's own repo root, not a
   subdirectory — `config_value_matches` raises `ValueError` otherwise,
   rather than silently computing matches against the wrong, narrower set
   of tracked files:

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -c "
   from pathlib import Path
   from claims.config import load_config
   from claims.config_review import config_value_matches

   repo_root = Path('<path to the project being reviewed>')
   for m in config_value_matches(repo_root, load_config(repo_root)):
       if m.error is not None:
           print(f'[{m.check}] {m.key} = {m.value} -> unreadable: {m.error}')
       elif not m.matched_files:
           print(f'[{m.check}] {m.key} = {m.value!r} -> matches nothing')
   "
   ```

   Each printed line names the check, the config key, and the configured
   value that currently matches nothing in the tracked tree. A `-> unreadable`
   line means the value itself couldn't be read as a list of strings (e.g.
   `exclude = 5`) — that's already a hard gate-crash finding on any normal
   run through the hook/CLI, so just note it in passing rather than
   reasoning about typo-vs-deliberate for it. A value that does match
   something prints nothing at all; silence for the rest of the config is
   the expected, boring case.

2. For every `ConfigValueMatch` with `matched_files == ()`, reason about
   whether that's likely a typo/stale entry or a plausible deliberate,
   forward-looking choice (e.g. a project adding `.rs` to
   `restatement.extensions` before its first Rust file lands) — using the
   project's actual file layout and language mix as evidence, and
   that check's own page under `docs/checks/` — shipped in the plugin
   root beside `claims/`, so no network is needed — for what the key is
   supposed to accomplish. This is
   the same evidence-citing standard `judgment-agent`'s subagent already
   holds itself to: a verdict with cited reasoning, never a bare
   pattern-match flag.
3. Report conversationally — the check, the key, the value, what you
   found, and your reasoned judgment — not as `Finding` lines and not with
   a pass/fail summary line. A value that does match something needs no
   mention; only a zero-match value is worth surfacing.

Not covered by this step (tracked separately, not this capability's job):
an unrecognized top-level table name is a mechanical hard error the
runner itself already gates on (ticket #21, no judgment involved); a
typo'd key *within* an otherwise-correctly-named check section isn't
detected at all yet, pending schema-declaration infrastructure that
doesn't exist (`[subjects]`, which no check owns, is the exception: the
runner gates on a key it doesn't take);
and this never recommends settings for a project with no `claims.toml` at
all — it reviews what's already there, it doesn't onboard from scratch.
