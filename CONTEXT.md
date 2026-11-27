# claims

Checks whether what a repository's prose says about its code is true, by
executing against the thing the prose describes. This glossary is the
vocabulary shared across checks; `docs/concepts.md` gives the behavioural
account of most terms, and the check pages, `docs/configuring.md` and
`docs/checked-marks.md` give the rest.

## Language

**Check**:
One question asked of the repository, answered independently of every other
check.

**Finding**:
One thing a check found, cited to a `file:line`.
_Avoid_: Error, warning, violation

**Gate**:
The finding severity that no reading settles, only a change: to the
text, a fix or a marker beside the claim, or to the configuration
scoping the check. It always fails the run.
_Avoid_: Failure, blocker

**Advisory**:
A finding severity that a reading may settle, by a checked mark, as well
as a fix. An unmarked one fails the run only where the caller asks for
that.
_Avoid_: Warning, info, soft failure

**Mode**:
The matching strategy that produced a finding; a check's own name where it
has only one.

**Diff-scoped**:
A check that reads only what the diff added or removed.

**Whole-tree**:
A check that sweeps every tracked file it reads, regardless of the diff.

**Claim**:
A statement in prose about the code, narrow enough that something can be
executed against it.
_Avoid_: Assertion, statement

**Intended claim**:
A claim stating a decided state as though it holds, read against the
tree as it stands for whether it has been delivered.
_Avoid_: Dated, Record-like

**Current claim**:
A claim saying what is, read against the tree as it stands.
_Avoid_: Live, Record-like

**Superseded claim**:
A claim that was meant to hold and no longer is, superseded by a later
replacement or by its withdrawal, and read against the tree just before
the change that superseded it.
_Avoid_: Record-like; Retired, which is a quote's; Abandoned

**Past claim**:
A claim saying what was, as a record, read against the tree as it was
at its writing or just before.
_Avoid_: Dated, Record-like

**Subject**:
The code a claim names.
_Avoid_: Target, reference

**Append-only file**:
A file that only grows, such as a changelog, so that as a subject a line
added to it is not its content changing; only a line changed or removed
is.
_Avoid_: Historical, which is how a line *in* a file is judged

**Navigation page**:
A page linked to point the reader at it rather than to claim anything
about all of it, so that named without an anchor it is no subject; a
link with an anchor into it still names that section.
_Avoid_: Hub page, which says how much it is linked, not how

**Candidate**:
A claim in doubt but not yet decided.
_Avoid_: Suspect, hit

**Verdict**:
An evidenced decision on a claim. Each agent that reads claims names its
own values.
_Avoid_: Result

**Designated file**:
A file a project has opted into a check's scope.
_Avoid_: Configured file, included file

**Retired quote**:
A sentence quoted in order to say what was wrong with it, rather than to
assert it.
_Avoid_: Retracted claim, old wording

**Retired-quote exemption**:
The per-check rule that a marked retired quote is skipped by a sweep.

**Retirement marker**:
The typographic form that marks a sentence as a retired quote; which
markers count is each check's own decision.

**Verify marker**:
The annotation above a fenced block naming the command whose output the
block pins.

**Grant**:
An exact command string a machine's owner has allowed or denied.
_Avoid_: Permission, allowlist entry

**Execution-capable check**:
A check that runs a command the project's own prose names.

**Checked mark**:
A record that someone read an advisory finding, which keeps it quiet until
what it depends on changes.
_Avoid_: Suppression, baseline, ignore

**Reader**:
Whoever read a finding against its subjects so that it could be marked:
a person, an agent session, or a subagent, named with its model. Never
the approver, though one person can be both.
_Avoid_: Marker, author, checker

**Reading batch**:
Findings that share subjects, handed to one reader at once, each read as
if alone.
_Avoid_: Batch (alone: a set of marks written together), group

**Notable reading**:
A reading a person should see before approving its mark: one that found a
claim false or unsettled, read a claim at an old tree, or that the session
had to correct.
_Avoid_: Interesting finding, flagged finding

**Caught problem**:
A problem in a reading that the session's own check of the reader's output
flags before any mark is written, so it costs a re-send or a read rather
than a wrong mark. A problem that check can't see is **not caught**.
_Avoid_: Detected problem, minor problem

**Partial mark**:
A checked mark whose reader read only part of its section or doc comment,
and said so.
_Avoid_: Spot-check mark, narrow mark

**Pending mark**:
A checked mark written without a person's review, which keeps its finding
quiet until a person approves it or it expires.
_Avoid_: Unapproved mark, provisional mark, draft mark

**Approve**:
What a person does to a pending mark they have reviewed, ending its
pending state.
_Avoid_: Sign off, confirm

**Fold**:
Approving a pending mark inside the commit that wrote it, by rewriting the
branch, not in a commit of its own.
_Avoid_: Squash approval, approval rebase

**Unmarked finding**:
An advisory finding, from a check whose findings can be marked, that no
checked mark keeps quiet.
_Avoid_: Unread finding, unchecked finding
