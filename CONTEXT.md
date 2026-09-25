# claims

Checks whether what a repository's prose says about its code is true, by
executing against the thing the prose describes. This glossary is the
vocabulary shared across checks; the behavioural account of each term is
`docs/concepts.md`.

## Language

**Check**:
One question asked of the repository, answered independently of every other
check.

**Finding**:
One thing a check found, cited to a `file:line`.
_Avoid_: Error, warning, violation

**Gate**:
The finding severity that stops a commit.
_Avoid_: Failure, blocker

**Advisory**:
A finding severity that is surfaced and never fails the run.
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

**Live claim**:
A claim meant to be re-verified against the tree as it stands.
_Avoid_: Record-like

**Dated claim**:
A claim true at its writing and not meant to be re-read against today's
tree.
_Avoid_: Record-like

**Subject**:
The code a claim names.
_Avoid_: Target, reference

**Candidate**:
A claim in doubt but not yet decided.
_Avoid_: Suspect, hit

**Verdict**:
An evidenced decision that a claim is true or false.
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
