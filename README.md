# claims

[![CI](https://github.com/or1can/claims/actions/workflows/ci.yml/badge.svg)](https://github.com/or1can/claims/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

A Claude Code plugin that checks documentation and agent-instruction claims
against the code they actually describe. Most doc-integrity tools watch for
*drift* — a doc and code that agreed once, then diverged. This one is built
for a different, more common failure: prose that was **wrong on arrival**,
never true, no drift required (see `.scratch/claims-consolidation/doc-integrity-tooling.md`
§3 for the full argument). It verifies claims by executing against the
artifact — running a command, resolving a symbol, walking git history —
never by grepping for words that happen to appear near a claim.

## What it checks

Seven mechanical checks, plus a judgment-shaped eighth that hands off to an
agent rather than deciding by itself:

- **executable-claims** (gate) — runs the command in a `<!-- verify: -->`
  marker and diffs its real output against the fenced block underneath. A
  command that times out (30s default, `timeout` in `claims.toml`) reports
  advisory instead — a timeout means the check never got an answer, not
  that the claim is false.
- **check-citations** (gate) — flags a backticked name, in Markdown or
  Swift comments, that cites a symbol this repo once declared but no longer
  has.
- **check-links** (gate) — flags an internal Markdown link (to another
  tracked file, or a `#anchor`) whose target or heading doesn't exist.
- **stale-claims** (advisory) — ranks prose sections by how much the code
  they name has changed since the section was last touched; a churn-ranked
  candidate list, not a verdict.
- **restatement** (advisory) — flags prose a diff retracted that's still
  asserted, verbatim, somewhere else in the tree. Text duplicated on
  purpose across more than `duplication_threshold` other files (1 by
  default, `claims.toml`) — a shared license header, a generated banner —
  is suppressed rather than flagged every time one copy changes.
- **spliced-docs** (advisory) — flags a doc comment that's been pushed onto
  the wrong declaration by an insertion above it (Swift and Rust). Only
  flags a break naming an undocumented declaration in the same file by
  default; naming a term absent from the whole repo (noisier on
  cross-referencing doc comments) is opt-in via `modes` in `claims.toml`.
- **claim-words** (advisory) — sweeps added lines in files a project opts
  in as record-like for totalising words ("every", "never") and counts,
  which are claims a check can't itself verify.
- **judgment-agent** (advisory) — computes which architecture-or-intent
  claims have a subject touched by the diff and surfaces each as a
  candidate. It never itself judges true or false; the `judgment-agent`
  subagent (see below) does that, one candidate at a time.

A gate finding blocks the commit it's attached to; an advisory finding is
surfaced but never fails the run. See each check's module docstring
(`claims/checks/`) for what it does and, as importantly, what it misses.

## Using it

Three invocation surfaces, same underlying checks:

- **Automatically, on commit.** A `PreToolUse` hook fires on `git commit`
  and runs every check above; a gate finding blocks the commit, an advisory
  finding is reported alongside it.
- **On demand, mid-task.** The `check-claims` skill runs the same checks
  outside of commit time — ask an agent to check claims, or invoke it
  directly, and it reports every finding the same way the hook would.
- **The `judgment-agent` subagent.** Fed one candidate at a time from the
  `judgment-agent` check above, it reads the cited code (or runs the
  command a claim implies) and returns a verdict with cited evidence —
  never by pattern-matching the claim's own wording. Advisory only: like
  every check it feeds, it never blocks a commit.

## What it isn't

Not a paraphrase detector (`restatement` is verbatim-only by design), not a
general prose linter, and not a push-time or CI check — it currently only
gates `git commit`.

## Installing

Distributed as a direct git-URL Claude Code plugin — no marketplace listing
— pinned at install rather than always-latest, so an unreviewed upstream
change can't silently start gating a commit differently mid-project. The
automatic hook can be disabled per project without uninstalling, via
`[hook]\nenabled = false` in that project's `claims.toml`. See
[`docs/installation.md`](docs/installation.md) for the actual commands.

## License

Apache-2.0 (see `LICENSE`). Several checks port prior art from `ratect`
(already Apache-2.0, same author) and from two private projects whose rights
holder — same author — has confirmed the relevant code can be relicensed and
ported in; neither private project is named, linked, or referenced by path
anywhere in this repo. Separately, `AGENTS.md`'s working principles section
is reproduced verbatim from the MIT-licensed
[andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) — see
[`NOTICE`](NOTICE) for that attribution.
