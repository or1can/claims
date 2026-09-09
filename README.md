# claims

A Claude Code plugin that checks documentation and agent-instruction claims
against the code they actually describe. Most doc-integrity tools watch for
*drift* — a doc and code that agreed once, then diverged. This one is built
for a different, more common failure: prose that was **wrong on arrival**,
never true, no drift required (see `.scratch/claims-consolidation/doc-integrity-tooling.md`
§3 for the full argument). It verifies claims by executing against the
artifact — running a command, resolving a symbol, walking git history —
never by grepping for words that happen to appear near a claim.

It ships as a `PreToolUse` hook that runs automatically on `git commit`
(some checks gate the commit, some are advisory-only — see below), plus an
on-demand skill and a judgment subagent for checking claims mid-task,
outside of commit time.

## What it checks

Seven mechanical checks, plus one judgment-shaped subagent:

- **executable-claims** (gate) — runs the command in a `<!-- verify: -->`
  marker and diffs its real output against the fenced block underneath.
- **check-citations** (gate) — flags a backticked name, in Markdown or
  Swift comments, that cites a symbol this repo once declared but no longer
  has.
- **check-links** (gate) — flags an internal Markdown link (to another
  tracked file, or a `#anchor`) whose target or heading doesn't exist.
- **stale-claims** (advisory) — ranks prose sections by how much the code
  they name has changed since the section was last touched; a churn-ranked
  candidate list, not a verdict.
- **restatement** (advisory) — flags prose a diff retracted that's still
  asserted, verbatim, somewhere else in the tree.
- **spliced-docs** (advisory) — flags a doc comment that's been pushed onto
  the wrong declaration by an insertion above it (Swift and Rust).
- **claim-words** (advisory) — sweeps added lines in files a project opts
  in as record-like for totalising words ("every", "never") and counts,
  which are claims a check can't itself verify.
- **judgment-agent** (advisory) — a subagent that verifies the
  claims none of the above can settle mechanically (an architecture or
  intent claim), by reading the cited code directly rather than pattern-matching
  its wording. Never blocks a commit.

A gate finding blocks the commit it's attached to; an advisory finding is
surfaced but never fails the run. See each check's module docstring
(`claims/checks/`) for what it does and, as importantly, what it misses.

## What it isn't

Not a paraphrase detector (`restatement` is verbatim-only by design), not a
general prose linter, and not a push-time or CI check — it currently only
gates `git commit`.

## Installing

Distributed as a direct git-URL Claude Code plugin — no marketplace listing
— pinned at install rather than always-latest, so an unreviewed upstream
change can't silently start gating a commit differently mid-project. The
automatic hook can be disabled per project without uninstalling, via
`[hook]\nenabled = false` in that project's `claims.toml`.

## License

Apache-2.0 (see `LICENSE`). Several checks port prior art from `ratect`
(already Apache-2.0, same author) and from two private projects whose rights
holder — same author — has confirmed the relevant code can be relicensed and
ported in; neither private project is named, linked, or referenced by path
anywhere in this repo. Separately, `AGENTS.md`'s working principles section
is reproduced verbatim from the MIT-licensed
[andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) — see
[`NOTICE`](NOTICE) for that attribution.
