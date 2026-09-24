# Introduction

`claims` checks whether what your documentation says about your code is
actually true. It decides by executing against the artifact the prose
describes — running the command, resolving the symbol, walking the git
history — never by matching words that happen to sit near a claim.

## The failure it is built for

Most doc-integrity tooling watches for *drift*: a document and the code it
describes agreed once, then diverged, and the tool's job is to notice the
divergence. That model has a blind spot, and it is the more common failure.
Prose is very often wrong the day it is written — a flag that was renamed
before the sentence naming it was typed, a default copied from a sibling
project, a "runs in under a second" nobody ever timed. Nothing diverged,
because the two were never together. A drift detector has nothing to compare.

So `claims` does not ask whether the code changed since the prose was
written. It asks whether the prose is true now, and it finds out the only
way that answer is available: by going and looking.

## What it does with an answer

Twelve checks run over a commit's own diff. Most of what they report is
*advisory*: surfaced alongside the commit and never failing the run,
because the check ranks, samples or suspects rather than decides. A finding
that names a claim the tool has actually disproved — a link with no target,
a cited symbol the repository no longer declares, a command whose real
output differs from the block beneath it — is a *gate*, and blocks the
commit it is attached to, because it is both certain and cheapest to fix
while you are still holding the context.

One advisory check hands off rather than deciding at all: it works out
which architecture-or-intent claims a diff has put in doubt and surfaces
each as a candidate for an agent to judge against the cited code.

## Where it runs

`claims` installs into a project as a Claude Code plugin: a hook that fires
on `git commit`, and a skill that runs the same checks on demand mid-task.
The checks are also a plain CLI, so the same run works as a git pre-commit
hook or a CI step in a project that has never seen Claude Code.

## Next

[Installation](installation.md) has the commands, for a plugin install and
for a standalone checkout alike.
