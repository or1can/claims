Status: ready-for-agent

# Spec: Unified claims-checking skill/agent

Collapsed from the `claims-consolidation` wayfinder map
([map.md](map.md), all five child tickets resolved under
[issues/](issues/)) per `/to-spec`. Full reasoning trail:
[tool-survey.md](tool-survey.md), [prior-art-notes.md](prior-art-notes.md),
[doc-integrity-tooling.md](doc-integrity-tooling.md).

## Problem Statement

Three projects under the same author — `ratect` (public, Apache-2.0) and two
private projects (a Swift application and an MCP-server project) — have each
independently hit the same failure: prose claims in documentation, agent
instructions, and skill files go stale or arrive wrong, and nothing catches
it before a human reviewer does. Each project has rebuilt overlapping tooling
to catch this — marker-based executable claims, churn-ranked staleness,
doc-comment splice detection, verbatim-restatement detection, totalising-
language sweeps, dead-citation and broken-link gates — with real drift
between the copies (different thresholds, different file-type scopes, one
failure class caught in only one project). There is no shared install path:
each project's version lives and evolves independently, and adopting a
sibling project's improvement means manually porting code by hand. A harder
class — claims that describe architecture or intent and that no command can
mechanically settle — has been identified but never built anywhere.

## Solution

A single Claude Code plugin, developed in this repo and installed
identically by any consuming project, consisting of:

- A **skill** covering every mechanical claim-check, invocable on demand.
- A **subagent** for the judgment-requiring residue — claims no command can
  settle — that reads code rather than grepping prose and cites a `file:line`
  or command for every verdict.
- A **`PreToolUse` hook**, gating specifically on a `git commit` (a
  manifest-level `if: Bash(git *)` filter plus a Python-side check
  narrowing "some git command" to "specifically a commit" — see ticket
  37 for why a single `Bash(git commit *)` manifest pattern alone isn't
  enough), that runs the applicable checks automatically before a commit
  completes, blocking on deterministic-gate findings and surfacing
  candidate-list findings as context without blocking.

Distributed as a direct git-URL plugin (no marketplace), pinned at install
with an explicit update step, bundling every language adapter in the one
repo. This repo itself goes public under Apache-2.0 or MIT; nothing from
either private source project is named, linked, or path-referenced anywhere
in it — their relevant logic is ported in and rewritten with the rights
holder's confirmed sign-off.

## User Stories

**Consolidation and consistency**

1. As a developer in `ratect`, I want the same checks I already have today, so that adopting the shared plugin costs nothing in coverage.
2. As a developer in the private Swift project, I want the totalising-language sweep and whole-line restatement detection I built there to keep working after adopting the shared plugin, so that switching costs nothing in coverage.
3. As a developer in the MCP-server project, I want the executable-claims marker gate I already rely on to keep working identically, so that my existing markers don't need rewriting.
4. As a maintainer of any of the three projects, I want a single upstream source for these checks, so that a fix or improvement in one project reaches the others without a manual port.
5. As a developer starting a fourth, future project, I want to install the same plugin and get the same coverage immediately, so that I don't have to rebuild any of this from scratch.

**Executable claims**

6. As a developer, I want a `<!-- verify: cmd -->` marker above a fenced block to run `cmd` and diff its output against the block, so that a claim reducible to a command's output can never silently go stale.
7. As a developer, I want a marker's command to run through a shell (not just `shlex.split`), so that claims requiring a pipe (`| tail -1`, `| sort -u`) are still markable.
8. As a developer, I want a sweep that finds zero markers, or a marker with a malformed block, to be reported as a failure — never a silent clean pass — so that "nothing was checked" is never mistaken for "everything passed."
9. As a developer, I want the marker gate to also fail on a command's non-zero exit code, not just on text mismatch, so that a command reporting failure via exit status alone still fails the claim.

**Staleness ranking**

10. As a developer, I want prose sections ranked by how much the code they name has changed since the claim was last touched, so that I have a prioritised list of what to re-read rather than the whole document.
11. As a developer, I want to know this ranking is blind to a claim and its subject moving together in the same commit, so that I don't mistake a clean ranking for a clean repo.

**Restatement**

12. As a developer, I want a diff that removes a phrase to be checked against every other tracked file for the same phrase surviving verbatim, so that a correction made in one place is flagged everywhere it wasn't also made.
13. As a developer, I want both a short-run (n-gram) match and a whole-line match reported as two modes of one check, so that neither a partial-phrase survival nor a whole-sentence survival goes uncaught because only one matching strategy was chosen.
14. As a developer, I want to know this check only catches verbatim or near-verbatim restatement, not paraphrase, so that I don't rely on it for a class of duplication it cannot see.
15. As a developer, I want the file-type scope this check runs over to be configurable per project (seeded with a sensible default), so that a language neither source tool covered (e.g. Rust) can be added without forking the check.

**Totalising and count language**

16. As a developer, I want every line a diff adds to be swept for totalising words ("every", "only", "never"), spelled-out or digit counts, and words asserting something "elsewhere" only when they sit beside a citation, so that a claim generalised past what was actually checked gets flagged before a reviewer has to find it by hand.
17. As a developer, I want this sweep scoped to whole sentences within specifically-designated record-like files rather than every paragraph everywhere, so that a document that quotes its own retired false claims (to explain what was wrong with them) doesn't fire on its own corrections.

**Structural checks**

18. As a developer, I want a doc comment spliced onto the wrong declaration (by an edit landing between the comment and its item) to be flagged when the stranded prose names an undocumented item in the same file, so that a misattached comment doesn't silently describe the wrong thing.
19. As a developer, I want a backticked name that cites a symbol my project once declared but no longer does to be flagged, so that a stale reference to a renamed or removed symbol is caught even without a mechanical drift signal.
20. As a developer, I want every internal Markdown link and heading anchor to be validated, so that a broken cross-reference is caught the same way a language-native doc-link checker would catch it.

**Judgment-requiring residue**

21. As a developer, I want claims that describe architecture or intent — which no command can settle — to be checked by a subagent that reads the actual code, never greps the prose describing it, so that the check isn't fooled by vocabulary that occurs in unrelated boilerplate regardless of outcome.
22. As a developer, I want every verdict this subagent produces to cite a `file:line` or the exact command it ran, so that "looks fine" with nothing behind it can never be the output.
23. As a developer, I want the subagent's candidate list bounded by which code subjects a diff actually added, removed, or renamed — not by which files the diff touched, and not by code churn since a claim was last edited — so that a rename falsifying prose in an untouched file is still caught, and a claim-and-code move in the same commit doesn't score zero.

**Invocation and gating**

24. As an agent working in a consuming project, I want to invoke the skill on demand at any point in my work, so that I can check claims mid-task rather than only at commit time.
25. As an agent about to run `git commit`, I want the applicable checks to run automatically via a `PreToolUse` hook, so that I don't have to remember to invoke the skill myself every time.
26. As an agent whose commit trips a deterministic gate check (e.g. an executable-claims failure), I want the commit blocked with the reason visible to me, so that a known-false claim never lands.
27. As an agent whose commit trips only advisory/candidate-list findings, I want those surfaced as context without blocking the commit, so that a ranked list of "look here" doesn't stop me from committing on a true sentence the check merely couldn't distinguish from a false one.
28. As a project maintainer, I want to disable the automatic hook via a config toggle while keeping the on-demand skill installed, so that I can opt out of auto-gating without losing the ability to run checks manually.

**Distribution and updates**

29. As a project maintainer, I want to install this plugin from a git URL without needing a marketplace listing, so that adoption doesn't depend on a publishing process.
30. As a project maintainer, I want the plugin pinned to a specific version at install time, so that an unreviewed upstream change can't silently alter what blocks my commits.
31. As a project maintainer, I want every language adapter bundled in the single install, so that I get full coverage regardless of which language(s) my project uses.

**Extensibility**

32. As a project maintainer with app-specific structural rules (e.g. an exact-count invariant check), I want to register my own bespoke check into the same runner and gate, so that my project-specific rules run alongside the shared ones without needing to become part of the shared core.

## Implementation Decisions

**Core seam.** Every check is a pure function of shape
`run(repo_root, diff_range, config) -> list[Finding]`. A `Finding` carries at
minimum: the citing `file:line`, a human-readable message, a `mode`/signal
name (for checks with more than one matching strategy), and a `gate: bool`
indicating whether this finding's check type blocks a commit. The CLI, the
`PreToolUse` hook adapter, and the on-demand skill are all thin callers of
this one shape — no separate logic duplicated per entry point.

**Check inventory and gate/advisory split** (per-check-type, not unified —
map.md standing decision):
- `executable-claims` — **gate**. Marker-based; runs a named command through
  a shell, diffs output, also fails on non-zero exit code; a sweep finding
  zero markers or a malformed marker is itself a failure, never a silent
  pass. A command chaining/backgrounding (`;`, `&&`, `||`, `&`),
  substituting (`` ` ``, `$(`), or piping through `sed`/`awk`/`grep` is
  rejected before it ever runs — a fixed blocklist, no config needed; a
  project may additionally restrict markers to a literal-prefix allowlist
  of its own commands via `permitted_prefixes` (ticket #11).
- `stale-claims` — **advisory**. Churn-ranked candidate list; explicitly
  documented as blind to same-commit claim-and-code moves.
- `restatement` — **advisory**. Merged from the two source tools into one
  check reporting two modes (n-gram-run survival, whole-normalized-line
  survival) against a diff's removed lines. Verbatim-only by design; the
  paraphrase blind spot is documented in the check's own output/docs, not
  solved. File-type scope is a config surface, seeded with the union of both
  source tools' coverage as the default.
- `claim-words` — **advisory**. Diff-scoped sweep over added lines for
  totalising words, counts, and citation-adjacent "elsewhere" words; scoped
  to whole sentences within designated record-like files to avoid firing on
  a document's own quoted, retired false claims.
- `spliced-docs` — **advisory**. Structural pattern match for a doc comment
  landing on the wrong declaration, reported by default only when the
  stranded prose names an undocumented item in the same file; the stronger
  variant (a name resolving to nothing anywhere in the repo) is opt-in via
  `modes` in `claims.toml` — too noisy to run by default on dense,
  cross-referencing doc comments (ticket #9).
- `check-citations` — **gate**. Backticked names citing a symbol the project
  once declared (via full history) but no longer does; exits distinctly when
  it can't see enough history to answer honestly, rather than reporting a
  false clean pass.
- `check-links` — **gate**. Every internal Markdown link and heading anchor
  resolves.
- `judgment-agent` — **advisory candidate list feeding a subagent verdict**.
  Deterministic half (subject-index build → diff-scoped touched-subject
  delta → citation-shaped token match against that closed set) is itself a
  check conforming to the same seam, producing ranked candidates. The
  subagent then reads code for each candidate and produces a verdict citing
  `file:line` or a command — never blocks a commit on its own judgment.

**Judgment-agent candidate mechanism** (from ticket 04): three deterministic
operations — (1) build a subject index from code (per-language, e.g. AST/
declaration extraction); (2) compute the diff's touched-subject delta
(added/removed/renamed subjects between two revisions — the operation no
surveyed tool already does; built from the same subject-index logic run
twice and set-diffed); (3) match prose against that closed set via
citation-shaped token extraction (backticked names/paths), never open
keyword search. Each candidate carries both the citing `file:line` and the
diff evidence (which commit(s) touched the subject).

**Invocation**: on-demand skill/subagent call, plus a `PreToolUse` hook
gating specifically on a `git commit` (see ticket 37). Commit-time only
for launch — no `git push`
checkpoint. Hook opt-out is a config toggle the hook script checks before
running, independent of whether the plugin itself is installed.

**Distribution**: direct git-URL Claude Code plugin, no marketplace — a
consuming project adds one `extraKnownMarketplaces` entry pointing at this
repo's URL and enables it. Pinned at install (a specific commit/tag), not
always-latest; updated via an explicit step. All language adapters ship
bundled in the one repo.

**Extension point** (shape open — see Further Notes): the runner accepts a
registration for project-specific bespoke checks (matching the private Swift
project's app-specific invariant style), which run through the same gate
mechanism without becoming part of the shared core's check inventory.

**Licensing and naming discipline carries into the shipped product, not
just this repo's planning docs.** The skill, subagent, hook, and any
generated output must never name or link either private source project —
same rule this repo's own planning artifacts already follow.

## Testing Decisions

A good test here exercises the `run(repo_root, diff_range, config)` seam
against a fixture repository state (a real or synthetic git history with a
known-true and a known-false claim), asserting on the returned `Finding`
list — never on internal parsing helpers in isolation, mirroring what the
source tools already do successfully.

- **Prior art, direct**: `test_echoed_claims.py`, `test_verify_docs.py`
  (both Apache-2.0, portable directly), and the equivalent per-tool test
  suites in the two private source projects (ported under the same
  relicensing sign-off as their check code) — reuse these as the starting
  fixtures for `restatement` and `executable-claims` respectively rather
  than writing new fixtures from scratch.
- **`executable-claims`**: fixture markers with a true and a false claim,
  a malformed marker, and a zero-marker sweep — asserting the exact `verdict`
  behaviour (0 checked ≠ clean pass).
- **`restatement`**: fixture diffs exercising both matching modes
  independently and confirming a paraphrase (no verbatim overlap) is
  correctly *not* flagged, documenting the boundary rather than hiding it.
- **`claim-words`**: fixture prose confirming a quoted/retired false claim
  in a record-like file does not fire, per the "house style for retiring a
  sentence" suppression rule.
- **Judgment-agent's deterministic half** (subject-index/delta/citation-
  match): tested at the same `run(...)` seam as any other check — a fixture
  repo with a renamed symbol and prose that cites the old name in a file
  the diff didn't touch, asserting the rename is still surfaced as a
  candidate.
- **Judgment-agent's verdict half**: a different testing shape — behavioral/
  golden-fixture evaluation (a known-true and known-false architectural
  claim against real code), not a unit test, since the subagent's output is
  LLM-driven rather than a pure function.
- **`PreToolUse` hook adapter**: tested by feeding it fixture JSON on stdin
  matching Claude Code's hook contract and asserting the JSON it emits on
  stdout (`permissionDecision`/`additionalContext`) — no live Claude Code
  session required.

## Out of Scope

- CI/PR-gate as the primary invocation trigger.
- Test/build orchestration as part of any shared orchestrator.
- Adopting external OSS tools (a diff-scoped accuracy-checking skill, a
  typed-claim extraction tool, a symbol-binding drift detector) as
  dependencies — design influence only.
- App-specific bespoke domain rules themselves becoming part of the shared
  check inventory — only the registration mechanism is in scope.
- Paraphrase detection within the `restatement` check.
- A `git push` invocation checkpoint.
- Naming or linking either private source project, or their private issue
  trackers, anywhere in this repo or the shipped plugin.

## Further Notes

Three questions remain open from the map, carried forward as implementation-
time questions rather than blockers:

- **Orchestrator design/value** — unclear even to the person driving this
  effort whether a claims-only orchestrator (beyond the core runner calling
  each check) adds anything; revisit once the check inventory is built and
  there's something concrete to orchestrate.
- **Extension-point mechanism's exact shape** — how a project registers a
  bespoke check into the runner is not yet designed.
- **Adapter interface design** — the internal interface a check uses to
  invoke a language-specific symbol/AST resolver (needed by `spliced-docs`
  and `check-citations` at minimum) has no concrete case yet to generalise
  from; file-type scope (a different, already-settled question) is not to be
  confused with this.
