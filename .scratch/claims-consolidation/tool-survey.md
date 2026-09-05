# Tool survey — claim-checking scripts across three projects

Gathered 2026-09-05 while charting the `claims-consolidation` wayfinder map. Read-only
survey, no code changed. Two of the three source projects are private and not
named or linked here — see map.md's Out of scope. They're described
generically below:

- **Project A** — `ratect`, a Rust project, Apache-2.0, this repo's sibling
  and already public-licensed.
- **Project B** — a private Swift application, same author.
- **Project C** — a private MCP-server project (a different codebase, same
  author, built for a client engagement). Excludes an unrelated
  incident-comparison reporting tool found alongside its claims-checking
  scripts — not part of the claims-checking family.

## 1. Project A's `tools/` (Rust)

| File | ~Lines | What it does |
| --- | --- | --- |
| `verify-docs.py` | 189 | Marker-based executable claims. `<!-- verify: cmd -->` above a fenced block; runs `cmd` via `shlex.split` (no shell), diffs stdout+stderr against the block. Scans all tracked `*.md`. Exit 1 on drift. |
| `stale-claims.py` | 184 | Churn-ranker. Splits `.md` into sections by heading; finds a section's "subject" (Rust file path, or backticked module name); scores by fraction of the file's commit history that postdates the claim's last-touched time (`git blame`). Prints top-N ranked candidates, never fails. |
| `spliced-docs.py` | 197 | Finds Rust `///` doc comments spliced onto the wrong item. Reported only when the stranded prose names (in backticks) an undocumented item in the same file. Candidate list, exits 0. |
| `echoed-claims.py` | 259 | Diffs removed vs added lines in tracked `.md`; any 6-word run present in what was removed but not re-added, still found verbatim anywhere in tracked markdown, is flagged as a surviving echo. Verbatim n-gram, not paraphrase. |
| `test_echoed_claims.py`, `test_verify_docs.py` | ~400 each | Unit tests. |

Candidate-selection: `verify-docs.py` = marker/opt-in (gate, not ranked). `stale-claims.py` = churn-rank. `spliced-docs.py` = structural pattern + same-file cross-reference. `echoed-claims.py` = diff-scoped (removed-not-readded) + whole-tree verbatim search.

## 2. Project B's `tools/` (Swift)

| File | ~Lines | What it does |
| --- | --- | --- |
| `claims.py` | 145 | Shared library: `declared_ever`/`declared_now` (Swift declarations via regex over `git log -p`/working tree), `target_names`, `repo_root`, `git()` helper. |
| `claim-words.py` | 341 | Diff-scoped word-sweep. For every line a diff *adds*, extracts the surrounding prose paragraph, flags STRONG (totalising: "every", "only", "never"), COUNTS (spelled-out/digit counts), WEAK (reported only beside a backticked symbol — "about-elsewhere"). Advisory, exit 0. |
| `spliced-docs.py` | 155 | Swift analogue of Project A's; also flags names resolving to nothing anywhere in the repo. |
| `split-claims.py` | 221 | Diff-scoped whole-line duplicate finder: for every line a diff *removes* (≥10 words, normalized), searches the whole tree for the exact same line surviving elsewhere. |
| `stale-claims.py` | 179 | Port of Project A's churn-ranker, imports `claims.py`, adds shallow-clone warning. |

Candidate-selection: `claim-words.py`/`split-claims.py` = diff-scoped. `stale-claims.py` = churn-rank (ported). `spliced-docs.py` = structural pattern.

## 3. Project B's `scripts/` (same repo, gating tier)

| File | ~Lines | What it does |
| --- | --- | --- |
| `check-citations` | 158 | Gates. Backticked names in tracked `.md`/`.swift` comments that cite a Swift symbol the repo *once declared* (full `git log -p` history) but no longer has. Exempts `<!-- was: name -->` markers. Exits 2 on shallow clone (refuses to under-report). |
| `check-invariants` | 335 (sh) | Gates. ~10 hand-written grep/sed structural invariants specific to this app's domain rules (e.g. exactly 2 calls to a specific escaping function, a review-field-write-count matching a stamp-count elsewhere). Bespoke, not reusable. |
| `check-links` | 59 (sh) | Gates. Validates every internal Markdown link (path + `#anchor`), including GitHub heading slugs. |
| `slugs.sh` | 29 (sh) | Shared heading-slug helper for `check-invariants`/`check-links`. |
| `verify` | 84 (sh) | Orchestrator: check-links, check-invariants, check-citations, Swift tests (native + Linux/Docker), both platform builds. |

Candidate-selection: N/A — exhaustive/deterministic gates over all tracked files, not ranked candidates.

## 4. Project C's claims-checking scripts (Python MCP server)

| File | ~Lines | What it does |
| --- | --- | --- |
| `verify_claims.py` | 220 | Port of Project A's `verify-docs.py` (explicit Apache-2.0 attribution back to Project A). Runs markers through a shell (`shell=True`, needed for pipes like `\| tail -1`); excludes a local scratch/history directory; checks return code as well as text; `verdict()` treats "0 checked, 0 failures" as a failure, not a clean pass. |
| `tool_names.py` | 141 | Reads the MCP server's entry point as an AST, extracts every tool-decorated function + args. `--used-by <dir>` mode scans a skill's markdown for tool-shaped tokens, classifies each `ok`/`argument`/`MISSING` against the surface. Meant to be invoked *from* a verify-marker, not directly. |
| `secret_refs.py` | 79 | Finds tracked files containing a complete credential-reference URI (vault/item/field shaped). Also meant to be invoked from a marker. |

Candidate-selection: none — fixed, small, hand-curated marker set in always-loaded files (an agent-instructions file and per-skill files). Deliberately not diff-scoped (the reasoning: the sweep is cheap enough that bounding the worklist buys nothing, and diff-scoping would miss the motivating failure — a rename falsifying prose in a file the diff never touches).

## Lineage

Chronological order: the shape of these tools originated in Project A
(`ratect`); relevant ones were ported and extended in Project B next; Project
C came later and adopted from Project A directly (its port of
`verify-docs.py` is attributed to Project A, not routed through Project B) —
so the order across projects is A, then B, then C, even though not every
individual tool's ancestry is a straight A→B→C chain.

- `verify-docs.py` (Project A) → `verify_claims.py` (Project C): direct port, attributed.
- `stale-claims.py` (Project A) → `stale-claims.py` (Project B): direct port, Swift-adapted.
- `spliced-docs.py` (Project A) → `spliced-docs.py` (Project B): direct port, Swift-adapted, stronger evidence rule.
- `echoed-claims.py` (Project A) and `split-claims.py` (Project B) solve the same restatement problem independently — n-gram-run vs whole-normalized-line — not a fork of each other.
- `claim-words.py` (Project B) has no analogue elsewhere — a failure class (totalising/quantifying language unsupported by the artifact) not in this repo's own prior taxonomy (see doc-integrity-tooling.md).
- `check-invariants`/`check-citations`/`check-links`/`verify` (Project B's gating tier) have no analogue in Project A; Project C's `tool_names.py`/`secret_refs.py` are narrow, MCP-specific extractors built to be called from a verify-marker, filling the same "cited name still exists" role as `check-citations` but purpose-built rather than general.
- The judgment-agent residue (claims no command can settle) is unbuilt in all three projects.

## External OSS surveyed (design influence only — see doc-integrity-tooling.md for full detail)

- A diff-scoped, six-phase documentation-accuracy skill with gated exit codes
  and per-file-group agent verification.
- A typed-claim extraction tool with a per-claim-type verification recipe and
  a "pattern-expansion from one false claim" step.
- An AST-fingerprint symbol-binding drift detector (`drift.lock`, exit-1
  gate).

None of these are adopted as dependencies — see map.md's standing decisions.
