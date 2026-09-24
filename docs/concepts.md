# Concepts

The words a check page uses without stopping to define them. Each is
defined here by what `claims` does with it, not by what a check's source
calls it.

## Checks and findings

A **check** is one question `claims` asks of the repository: does this
command still produce this output, does this link have a target, does this
cited name still exist. Every check runs on every invocation, each
independently of the rest, and each reports zero or more findings.

A **finding** is one thing a check found, printed on one line: the
severity in brackets, where the finding applies as `file:line`, the mode
in parentheses, and then the message. Every entry point prints the same
line, whether the run came from the commit hook, the on-demand skill, or
the plain CLI.

## Gate versus advisory

A **gate** finding blocks the commit it is attached to. Through the hook,
the `git commit` is denied, with every finding of the run as the reason;
through the CLI, the run exits non-zero. A check is a gate when what it reports is a
claim it has actually disproved: a link with no target, a cited symbol the
repository no longer declares, a bare path mention that resolves to no
tracked file, a command whose real output no longer matches the block
beneath it.

An **advisory** finding is surfaced alongside the commit and never fails
the run. A check is advisory when it ranks, samples, or suspects rather
than decides: a churn-ranked section, a totalising word, a doc comment that
might be spliced. An advisory check can be certain of what it saw and still
be advisory, because what it saw is a place to look rather than a claim
proved false.

Severity belongs to the check, not to the individual finding, and a check
that departs from its own severity for one kind of finding says so. A
command that times out is reported advisory by an otherwise gate check,
because a timeout is no answer rather than a wrong one; a grant file that
has been committed is reported as a gate by an otherwise advisory check,
because that is a compromise indicator whatever the check's own severity.
Each check states its own severity and its own exceptions.

One gate finding belongs to no check at all: a top-level `claims.toml`
table naming no check is reported under the fixed mode `config`.
[Configuring `claims`](configuring.md) covers it.

## Mode

The **mode** is the label in parentheses on a finding line. It names the
matching strategy that fired. For a check with one strategy it is the
check's own name, so `(check-links)` and `(stale-claims)` read as the check.
A check with more than one strategy names the strategy instead, prefixed
with the check's name: `(restatement-ngram)` and `(restatement-whole-line)`
are the same check's two ways of matching, and a consumer can count or
filter by either without parsing the message.

## Diff-scoped and whole-tree

Every check runs against a diff range, and each decides for itself how much
of the range matters. A **diff-scoped** check reads only what the diff
added or removed: `claim-words` sweeps added lines, `restatement` starts
from removed ones, `judgment-agent` computes what the diff touched. A
**whole-tree** check ignores the diff's content and sweeps every tracked
file of the kinds it reads, because what it looks for can be false today
regardless of when it was written: a marker's command, a link, a citation.
A whole-tree check therefore reports a pre-existing defect on a commit that
never touched it. That is the intended behaviour, and the reason a first run
in a project with a history often has more to say than a later one.

## Designated and record-like files

A **record-like** file is one whose sentences are assertions worth holding
to account: a specification, an architecture decision record, a changelog.
A sentence there saying "every check does X" is a claim about the tree,
where the same sentence in a tutorial is an aside.

`claims` does not guess which files those are. A project **designates**
them, by listing them under a check's `files` key, and a check that reads
only designated files reads nothing until the project has. The default is
the empty set, so such a check is inert in a project that has not opted in,
and finds nothing rather than sweeping everything and hoping.

## The retired-quote exemption

A record-like file often quotes a sentence in order to say what was wrong
with it: "we used to say every check gates; that was false." Read
literally, the quoted sentence is still a claim, and a sweep for totalising
words would flag it every time. The **retired-quote exemption** is the rule
that a sentence marked as retired is skipped.

A sentence is marked by how it is written: as a Markdown blockquote, wrapped
whole in italics, or opening with the fixed lead-in "Previously said:". An
unmarked quotation still fires, on the reasoning that an unmarked quotation
is indistinguishable from the claim still being made.

Which of those markers count is decided per check, not once for the whole
tool. A blockquote means retirement in a changelog and a callout in a
reference page, so whether it counts depends on which prose a check reads.
Each check that has an exemption states its own set. The reasoning is in
[ADR 0003](../decisions/0003-retirement-markers-are-scope-dependent.md).

## Candidate, subject, verdict

A **subject** is the code a claim names: a file by path, a symbol in
backticks, a script beside a flag. Resolving the subject is the first thing
most checks do. A claim that names no subject at all is out of their reach,
because there is nothing to execute against; a sweep of designated files
for the words such a claim is made of is as far as a check can go with it.

A **candidate** is a claim a check has put in doubt without deciding it. A
section whose subjects have churned since it was written is a candidate; a
citation of a name the diff added or removed is a candidate. A candidate
list is ranked, never filtered: nothing in it is dropped as probably fine,
because a list that can collapse to "nothing to review" is a verdict in
disguise.

A **verdict** is a decision that a claim is true or false, with the
evidence that decided it. A gate finding is a mechanical verdict on a claim
narrow enough to test. For an architecture-or-intent claim no check can
test, the only verdict comes from the `judgment-agent` subagent, which reads
the cited code one candidate at a time and answers with what it read. No
check produces that verdict, and no part of `claims` treats it as a gate.

## Next

[Configuring `claims`](configuring.md) covers the settings that belong to
no single check: switching the hook off, the unrecognized-table gate, and
the local grant file that governs what may run.
