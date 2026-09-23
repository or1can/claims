# claims

[![CI](https://github.com/or1can/claims/actions/workflows/ci.yml/badge.svg)](https://github.com/or1can/claims/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Most doc-integrity tools watch for
*drift* — a doc and code that agreed once, then diverged. `claims` is built
for a different, more common failure: prose that was **wrong on arrival**,
never true, no drift required (see `.scratch/claims-consolidation/doc-integrity-tooling.md`
§3 for the full argument). It verifies claims by executing against the
artifact — running a command, resolving a symbol, walking git history —
never by grepping for words that happen to appear near a claim.

A Claude Code plugin — the checks themselves also run standalone as a CLI,
outside Claude Code entirely — that checks documentation and
agent-instruction claims against the code they actually describe.

## What it checks

Eleven mechanical checks, plus a judgment-shaped twelfth that hands off to
an agent rather than deciding by itself:

- **executable-claims** (gate) — runs the command in a `<!-- verify: -->`
  marker and diffs its real output against the fenced block underneath. A
  command that times out (30s default, `timeout` in `claims.toml`) reports
  advisory instead — a timeout means the check never got an answer, not
  that the claim is false. A marker chaining or backgrounding commands
  (`;`, `&&`, `||`, `&`), redirecting file I/O (`>`, `>>`, `<`), substituting
  one (`` ` ``, `$(`), or piping through `sed`/`awk`/`grep` is rejected
  outright, never run — except safe `N>&M` file-descriptor duplication
  (`2>&1`, `1>&2`), permitted since a real file write via `>&file` is the
  actual risk being pinned, not fd-duplication; a project can further
  restrict markers to its own commands via a literal-prefix
  `permitted_prefixes` list in `claims.toml`.
  Beyond that, a command only runs once it's been explicitly, locally
  granted by exact string in `claims.local.toml` (git-ignored, per-machine
  — not committed config) — see
  [`decisions/0001-executable-claims-deny-by-default.md`](decisions/0001-executable-claims-deny-by-default.md).
- **check-citations** (gate) — flags a backticked name, in Markdown or
  Swift comments, that cites a symbol this repo once declared but no longer
  has.
- **check-links** (gate) — flags an internal Markdown link (to another
  tracked file, or a `#anchor`) whose target or heading doesn't exist. A
  project can name its append-only records (`historical` in `claims.toml`)
  so a link there is instead held to the tree as of the commit that wrote
  its line — see
  [`decisions/0002-historical-links-resolve-at-their-own-commit.md`](decisions/0002-historical-links-resolve-at-their-own-commit.md).
- **check-file-refs** (gate) — flags a bare, unmarked prose mention of a
  path (not real `[text](path)` link syntax — that's `check-links`' job)
  whose extension is in a recognized set and that doesn't resolve to a
  tracked file.
- **check-config-defaults** (advisory) — flags a claim shaped `` `NAME`
  defaults to `value` `` (both backticked) whose stated value doesn't
  appear at the project-mapped `file:line` holding that setting's real
  default. A setting name with no mapping entry in `claims.toml` is
  entirely out of scope, not flagged.
- **check-env-vars** (advisory) — flags a backtick-quoted
  `ALL_CAPS_WITH_UNDERSCORES` name that doesn't appear anywhere in a
  project-configured scope of files (`.env.example` by default, if
  tracked). No scope configured and no `.env.example` present means the
  check is genuinely inert, not a sweep of everything.
- **check-cli-flags** (advisory) — flags a claim naming both a script and
  a CLI flag together where running `<script> --help` doesn't actually
  list the flag. `claims`' second execution-capable check alongside
  `executable-claims`, sharing its deny-by-default local-grant mechanism
  (`claims.local.toml`) — see
  [`decisions/0001-executable-claims-deny-by-default.md`](decisions/0001-executable-claims-deny-by-default.md).
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
(`claims/checks/`) for what it does and, as importantly, what it misses —
or `docs/configuration.md` for every `claims.toml` key mentioned above (and
a couple not), its default, and when to reach for it.

## Using it

Four invocation surfaces, same underlying checks:

- **Automatically, on commit.** A `PreToolUse` hook fires on `git commit`
  and runs every check above; a gate finding blocks the commit, an advisory
  finding is reported alongside it.
- **On demand, mid-task.** The `check-claims` skill runs the same checks
  outside of commit time — ask an agent to check claims, or invoke it
  directly, and it reports every finding the same way the hook would. The
  same skill also has a separate, explicit-ask-only capability: reviewing
  whether a project's own `claims.toml` values are actually doing
  anything (a stale `exclude` glob matching nothing, say) — reasoned
  prose with cited evidence, not a `Finding`, and never run automatically.
- **The `judgment-agent` subagent.** Fed one candidate at a time from the
  `judgment-agent` check above, it reads the cited code (or runs the
  command a claim implies) and returns a verdict with cited evidence —
  never by pattern-matching the claim's own wording. Advisory only: like
  every check it feeds, it never blocks a commit.
- **Outside Claude Code entirely, as a plain git pre-commit hook or a CI
  step.** `claims.cli` is the same `run()` seam the automatic hook itself
  calls, with the same exit code a shell script or CI job already expects
  — see [`docs/installation.md`](docs/installation.md)'s "Using it outside
  Claude Code" section for the setup (it needs a checkout of this repo,
  not a pip install) and what's different without an LLM present:
  `judgment-agent`'s own candidates are still computed and reported, but
  never resolved into a verdict, and the skill's on-demand config review
  doesn't run at all.

## What it isn't

Not a paraphrase detector (`restatement` is verbatim-only by design), not a
general prose linter, and not automatically a push-time or CI check — the
automatic gate only fires through Claude Code's own hook. See "Using it"
above to wire the same checks into a plain git pre-commit hook or a CI job
instead.

## Installing

Distributed as a direct git-URL Claude Code plugin — no marketplace listing
— pinned at install rather than always-latest, so an unreviewed upstream
change can't silently start gating a commit differently mid-project. The
automatic hook can be disabled per project without uninstalling, via
`[hook]\nenabled = false` in that project's `claims.toml`. See
[`docs/installation.md`](docs/installation.md) for the actual commands —
including "Using it outside Claude Code", the setup for running the same
checks as a plain pre-commit hook or CI step (a repo checkout, not a plugin
install or a pip install).
See [`CHANGELOG.md`](CHANGELOG.md) for what changed in a given version,
after a `claude plugin update`.

## License

Apache-2.0 (see `LICENSE`). Several checks port prior art from `ratect`
(already Apache-2.0, same author) and from two private projects whose rights
holder — same author — has confirmed the relevant code can be relicensed and
ported in; neither private project is named, linked, or referenced by path
anywhere in this repo. Separately, `AGENTS.md`'s working principles section
is reproduced verbatim from the MIT-licensed
[andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills) — see
[`NOTICE`](NOTICE) for that attribution.
