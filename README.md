# claims

[![CI](https://github.com/or1can/claims/actions/workflows/ci.yml/badge.svg)](https://github.com/or1can/claims/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

**Documentation: <https://claims.apps.orican.eu>**

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

Each check has a page of its own. A gate finding blocks the
commit it is attached to; an advisory finding is surfaced but never fails
the run — [`docs/concepts.md`](docs/concepts.md) defines both.

Gate:

- [executable-claims](docs/checks/executable-claims.md)
- [check-citations](docs/checks/check-citations.md)
- [check-links](docs/checks/check-links.md)
- [check-file-refs](docs/checks/check-file-refs.md)

Advisory:

- [check-config-defaults](docs/checks/check-config-defaults.md)
- [check-env-vars](docs/checks/check-env-vars.md)
- [check-cli-flags](docs/checks/check-cli-flags.md)
- [stale-claims](docs/checks/stale-claims.md)
- [restatement](docs/checks/restatement.md)
- [spliced-docs](docs/checks/spliced-docs.md)
- [claim-words](docs/checks/claim-words.md)
- [judgment-agent](docs/checks/judgment-agent.md)

[`docs/configuring.md`](docs/configuring.md) covers the settings no single
check owns.

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
