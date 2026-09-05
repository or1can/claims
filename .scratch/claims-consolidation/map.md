# Map: Unified claims-checking skill/agent

## Destination

A Claude Code skill covering the mechanical claim-checks (executable-claims,
stale-claims churn-rank, spliced-docs, restatement [echoed-claims/split-claims],
claim-words totalising-sweep, check-citations, check-links) paired with a
subagent for judgment-requiring residue — claims no command can settle, every
verdict citing a `file:line`, never grepping prose (see
[prior-art-notes.md](prior-art-notes.md) §3). Consolidated from `ratect`'s
`tools/` directory plus two other private projects' equivalent tooling
(a Swift project and an MCP-server project, both this repo's author's own
work — not otherwise named or linked here; see [tool-survey.md](tool-survey.md))
into this repo, installable by any consuming project so an agent working
there can invoke it on demand before a commit and cut code-review failure
demand. Bespoke per-repo domain-pinning (the Swift project's app-specific
invariant checks) stays out of the shared core but gets a
registration/extension point in the shared runner.

## Notes

Domain: consolidating existing claim-checking tooling — see
[tool-survey.md](tool-survey.md), [doc-integrity-tooling.md](doc-integrity-tooling.md)
(this repo's own prior working notes — Ratect-only evidence, external OSS
survey, failure-class taxonomy), and [prior-art-notes.md](prior-art-notes.md)
(a condensed, anonymised synthesis of design lessons from one of the source
projects' own issue tracker — that tracker itself is private and not linked).

Standing decisions carried into every ticket:
- Consolidate home-grown tools as the base. External OSS tools (a diff-scoped
  accuracy-checking skill, a typed-claim extraction tool, a symbol-binding
  drift detector — see tool-survey.md) are design influence only —
  diff-scope, AST-binding, extract/verify separation, exit-code gating —
  never a dependency.
- Per-check-type candidate-selection strategy kept; no strategy forced across
  all checks.
- Judgment-agent (the "claims no command settles" class) in scope, shaped as
  the skill+subagent pairing above.
- Licensing: this repo is going public under Apache-2.0 or MIT. The private
  Swift project's rights holder (same author as this repo) has confirmed its
  relevant code can be relicensed and ported in; `ratect` is already
  Apache-2.0. Nothing from either private source project is referenced by
  name, linked, or pointed at by path anywhere in this repo — content is
  ported in and rewritten, never linked out.
- Orchestrator scope, if built at all, is claims-checks only — never test/build
  orchestration.
- Invocation is on-demand/agent-invoked to start.

Skills to consult: `/grilling` and `/domain-modeling` for `grilling` tickets,
`/research` for `research` tickets.

## Decisions so far

- [Invocation-mechanism survey](issues/01-invocation-mechanism-survey.md) —
  none of the consuming projects has any hook wired today; git hooks, Claude
  Code hook events, and pure on-demand all reach a live agent turn under some
  condition, each with a different feedback shape and setup cost — ticket 02
  now unblocked to choose between them.
- [Judgment-agent candidate-list](issues/04-judgment-agent-candidate-list.md)
  — the missing operation is a diff-scoped subject delta (which code subjects
  this specific diff added/removed/renamed); none of the six tools surveyed
  computes it, though all the primitives to build it exist. Prose is matched
  against that closed, code-derived subject set via citation-shaped token
  extraction (backticked names/paths), not open keyword grep — reconciling
  the mechanism with the "never grep the prose" constraint
  (prior-art-notes.md §3).

## Not yet specified

- Language-agnostic core + per-language adapter design (Rust/Swift/Python) —
  too coarse until the restatement-check reconciliation (ticket 05) settles
  what the core components actually are.
- Orchestrator design/value — acknowledged unclear even to the person driving
  this map; revisit once the core components are consolidated and there's
  something to orchestrate.
- Extension-point mechanism for bespoke per-repo checks (app-specific
  invariant-style) — shape not yet specified.
- Judgment-agent subagent's exact spec/prompt, and the candidate-list question
  prior-art-notes.md §3 itself left open — depends on ticket 04 resolving
  first (partially answered — see Decisions so far).
- Versioning/update mechanism for consuming repos once packaged — depends on
  ticket 03 (distribution) resolving first.

## Out of scope

- CI/PR-gate as the primary invocation trigger — ruled out; by the time CI
  runs, the commit/push already happened, which is the failure demand this
  effort exists to cut. (Local git hook stays open — see tickets 01/02.)
- Test/build orchestration inside the shared orchestrator — stays each
  consuming repo's own CI concern.
- Adopting external OSS tools as literal dependencies — considered and
  superseded by the decision to consolidate home-grown tooling instead (see
  tool-survey.md's "Worth adopting" section for what was considered).
- App-specific bespoke domain rules (e.g. exact-count structural invariants)
  themselves becoming part of the shared core — the registration mechanism is
  in scope, the rules are not.
- Naming or linking either private source project, or their private issue
  trackers, anywhere in this repo — content is ported in as local, rewritten
  files (prior-art-notes.md, tool-survey.md) instead.
