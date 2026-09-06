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
- Invocation launches as an on-demand skill/subagent plus a `PreToolUse` hook
  matched on `Bash(git commit *)`, gate-vs-advise split by check type
  (see ticket 02) — commit-time only, no push checkpoint.
- Distribution is a direct git-URL Claude Code plugin (no marketplace),
  pinned at install with an explicit update step, bundling every language
  adapter in the one plugin repo, with a config toggle to disable the
  auto-hook without uninstalling (see ticket 03).

Skills to consult: `/grilling` and `/domain-modeling` for `grilling` tickets,
`/research` for `research` tickets.

## Decisions so far

- [Invocation-mechanism survey](issues/01-invocation-mechanism-survey.md) —
  none of the consuming projects has any hook wired today; git hooks, Claude
  Code hook events, and pure on-demand all reach a live agent turn under some
  condition, each with a different feedback shape and setup cost — ticket 02
  now unblocked to choose between them.
- [Invocation-mechanism decision](issues/02-invocation-mechanism-decision.md)
  — launches as an on-demand skill/subagent plus a `PreToolUse` hook matched
  on `Bash(git commit *)`, split gate-vs-advise by check type (deterministic
  checks block, candidate-list checks only inform), uniform across consuming
  projects, commit-time only (no push checkpoint). How the hook actually gets
  installed per project is deferred to ticket 03.
- [Distribution mechanism](issues/03-distribution-mechanism.md) — a direct
  git-URL plugin (no marketplace), pinned at install with an explicit update
  step, all language adapters bundled in one repo, hook opt-out via a config
  toggle rather than uninstalling. Resolves the map's former
  versioning/update fog item.
- [Judgment-agent candidate-list](issues/04-judgment-agent-candidate-list.md)
  — the missing operation is a diff-scoped subject delta (which code subjects
  this specific diff added/removed/renamed); none of the six tools surveyed
  computes it, though all the primitives to build it exist. Prose is matched
  against that closed, code-derived subject set via citation-shaped token
  extraction (backticked names/paths), not open keyword grep — reconciling
  the mechanism with the "never grep the prose" constraint
  (prior-art-notes.md §3).
- [Restatement-check reconciliation](issues/05-restatement-check-reconciliation.md)
  — `echoed-claims.py` and `split-claims.py` merge into one `restatement`
  check running both matching signals (n-gram-run, whole-line), verbatim-only
  by design with the paraphrase blind spot documented rather than solved (a
  third project found verbatim-only matching caught none of its real
  failures — see tool-survey.md), reports the finding only with no
  architectural nudge, and file-type scope is configurable per project,
  seeded with the union of both source tools' coverage as the default.

## Not yet specified

- Language-agnostic core + per-language adapter **design** — the internal
  interface between the core and each language's check scripts (Rust/Swift/
  Python). Partially answered by ticket 05: file-type scope is a config
  surface, not a hardcoded list (seeded with a sensible default). Still
  open: the actual interface a check uses to invoke a language-specific
  symbol/AST resolver (needed by, e.g., spliced-docs and check-citations),
  which has no concrete case yet to generalise from. Distinct from ticket
  03's packaging decision (all adapters ship bundled in one plugin repo) —
  that's settled; this is about the interface between them, not where they
  live.
- Orchestrator design/value — acknowledged unclear even to the person driving
  this map; revisit once the core components are consolidated and there's
  something to orchestrate.
- Extension-point mechanism for bespoke per-repo checks (app-specific
  invariant-style) — shape not yet specified.
- Judgment-agent subagent's exact spec/prompt, and the candidate-list question
  prior-art-notes.md §3 itself left open — depends on ticket 04 resolving
  first (partially answered — see Decisions so far).

## Out of scope

- CI/PR-gate as the primary invocation trigger — ruled out; by the time CI
  runs, the commit/push already happened, which is the failure demand this
  effort exists to cut. (A raw git hook was considered and not chosen —
  ticket 02 picked a Claude Code `PreToolUse` hook instead, since it reaches
  the agent natively rather than only a human terminal.)
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
