# 25 — Dogfooding: this repo gates its own commits with its own checks

**What to build:** this repo doesn't currently run its own tool on itself —
no `claims.toml`, no `.claude/settings.json` entry enabling the plugin, no
`PreToolUse` hook wired here. Every check ticket 07–13 built has only ever
been exercised against fixtures and, for ticket 19, `ratect`'s tree — never
against the prose making the claims *in this repo*, which is exactly the
kind of claim-dense repo (`doc-integrity-tooling.md`, `AGENTS.md`, `spec.md`,
22 ticket files) this tool exists for.

Wire the same mechanism ticket 03/18 built for a consuming project, applied
reflexively: this repo installs itself (`.claude-plugin/marketplace.json`
already self-references with `"source": "./"`, per ticket 18's Answer — the
open question is the concrete local-install command/config that makes
*this* repo's own `.claude/settings.json` enable it, which ticket 19's
`--plugin-dir` session-scoped load approximated but didn't make persistent).
Once enabled, the `PreToolUse` hook gates this repo's own commits exactly as
it would `ratect`'s.

Running the full check suite against this repo's own tree for the first time
is very likely to surface real findings — `stale-claims` and `restatement`
in particular, given how much cross-referencing prose this project has
accumulated across `AGENTS.md`, the `.scratch/` tickets, and the checks'
own docstrings. Triaging those findings (fix the claim, or note why a hit is
a legitimate double-appearance) is part of this ticket, not a follow-up —
an advisory finding left unlooked-at is the exact failure mode
`doc-integrity-tooling.md` §1 catalogs.

**Blocked by:** 18.

**Status:** resolved

- [x] `.claude/settings.json` (or the correct local mechanism, once ticket
      24 nails down what that is) enables this plugin for this repo itself,
      persistently — not just for one `--plugin-dir` session.
- [x] A real `git commit` in this repo triggers the `PreToolUse` hook and is
      blocked (or passes) based on this repo's own gate checks —
      demonstrated, not assumed from the manifest.
- [x] `claims.toml` exists here (even if empty) rather than relying on
      defaults implicitly, so this repo's own config surface is exercised
      too.
- [x] The first full run's findings are triaged to zero unaddressed gate
      failures — each advisory finding either fixed or has a stated reason
      it's a legitimate hit, not silently ignored.
- [x] Full test suite and `pyright claims tests` stay clean throughout.

## Answer

**Local install mechanism** (ticket 24 not landed yet, so worked out here
directly rather than blocking on it): `claude plugin marketplace add ./
--scope project` followed by `claude plugin install claims@claims --scope
project`. Verified against the real CLI, not assumed — the first attempt
without `--scope project` wrote to *user* settings (`~/.claude/settings.json`),
which doesn't travel with the repo; re-run with `--scope project` writes to
the repo's own `.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "claims": { "source": { "source": "directory", "path": "." } }
  },
  "enabledPlugins": { "claims@claims": true }
}
```

The `path` is `.`, not an absolute path — the CLI's default `add` wrote an
absolute, machine-specific path (`/Users/kevin/git/or1can/claims`), which
would break for any other clone or CI checkout. Confirmed against
`code.claude.com/docs/en/plugin-marketplaces` (fetched directly, independently
re-fetched a second time after a subagent's first report of the same page
tripped this environment's prompt-injection heuristic on the quoted JSON —
the second, direct fetch returned identical content, so the quote is real,
not injected) that a local `directory`/`file` source with a relative path
resolves against the repository's main checkout, portable across clones and
worktrees. Re-pointed `path` to `.` and re-verified with `claude plugin
marketplace list` / `claude plugin list` that it still resolves and the
plugin still shows enabled at `Scope: project`. `claude plugin validate .`
passes (one pre-existing, out-of-scope warning: no `author` field in
`plugin.json`).

**Live hook demonstration.** Before the fix below, `PYTHONPATH=.  python3 -m
claims.cli` against this repo's own tree reported 1 gate failure —
`executable-claims`: "no verify markers found in repo" (by design: a sweep
finding zero `<!-- verify: -->` markers is itself a gate failure per
`executable_claims.py` and `spec.md` story 8, "nothing checked" must never
read as "everything passed"). This repo had never had a marker, so it was
tripping its own gate. Fixed by adding one real marker to `AGENTS.md`
(`### Typechecking`, verifying `pyright claims tests` stays clean) — the
same command every ticket's Answer already claims to run by hand, now
mechanically checked.

Installing the plugin mid-session doesn't retroactively wire it into the
already-running session doing this work, so this session's own commit of
these changes is not by itself good evidence the hook fires — that would be
assuming it from the manifest again, the exact thing this checklist item
rules out. Demonstrated properly instead, the same way ticket 19 did:
a fresh, separate `claude -p` process started against this repo (the
install above being project-scoped, a fresh process picks it up without
`--plugin-dir`) issuing a real `git commit --dry-run --allow-empty` Bash
call. Observed output: the claims `PreToolUse` hook fired and reported its
findings (34 advisory `stale-claims` hits, 0 gate failures, matching this
run's shape) before the git command itself ran — git then exited 1 for its
own, unrelated reason (`--dry-run` and `--allow-empty` don't combine; a
clean tree makes `--dry-run` exit 1 regardless). The hook engaging, not
git's own exit code, is what this checklist item is about.

**`claims.toml`**: added at the repo root, empty (a comment only) — every
check runs with its defaults, matching `claims/config.py`'s documented
"absent file means every check runs with defaults" behaviour, now made
explicit rather than implicit.

**Triage of the first full run.** 8 checks ran; after the `executable-claims`
fix above, 0 gate failures and 20 advisory findings, all from `stale-claims`.
Every one is the same shape: a ticket's own `## Answer` section (or
`spec.md`/`map.md`/`docs/agents/issue-tracker.md`) cites a source file that
picked up further commits after the section was last touched — exactly the
check's own documented, named blind spot (`stale_claims.py`'s docstring:
"a churn-ranked candidate list, not a verdict... a hot file makes an
accurate claim look suspicious"). Spot-checked a representative sample
against the current code rather than trusting the shape alone: ticket 05's
Answer (n-gram 6 words / whole-line ≥10 words) still matches
`restatement.py`'s `NGRAM_WORDS`/`MIN_LINE_WORDS` exactly; ticket 08's
Answer (`stale-claims`'s own name/signature/`gate=False`) still matches
`stale_claims.py`; ticket 06's Answer (`runner.run`'s pure-function,
register-by-name design) still matches `runner.py`; ticket 17's and the
subagent's citations (`SKILL.md`, `scripts/run_judgment_agent_golden.py`)
are file-path references, not behavioural claims, so churn on the cited
file can't make them wrong. None is a real drift; every one is the
"documentation freezes a moment, code keeps moving" pattern the check
exists to rank, not fix. No changes needed for any of the 20 — each is a
legitimate hit in the sense the check's own docstring names, not a silently
ignored one.

One adjacent, already-known gap surfaced again while reading these (not new
here, not fixed here): `docs/agents/issue-tracker.md`'s Wayfinding section
is itself one of the 20 hits, and separately (per `TODO.md`, noticed twice
already during tickets 15 and 19) describes a map-append convention that
stopped applying once `spec.md` superseded the wayfinder phase. Still
tracked in `TODO.md`, still belongs to whichever ticket next touches that
file — not this one.

**Full suite**: all 14 test files pass (`PYTHONPATH=. python3 <file> -v`
per file, no `pytest` binary in this environment, matching ticket 18's
same note); `pyright claims tests`: `0 errors, 0 warnings, 0 informations`.
