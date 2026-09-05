# Documentation-integrity tooling — notes toward a project

**Status:** working notes, uncommitted, written 2026-09-02 during Ratect 0.26.0.
Not a plan yet.

**Evidence boundary, stated up front:** everything concrete below was observed in
**Ratect only**, mostly across two code-review rounds on one release. Kevin
reports the same classes recurring across three projects, with the same tooling
rebuilt each time. Those two other projects' instances need adding before any of
this is treated as generalised — right now the sample is one repo and one author,
which is exactly the size that makes a pattern look sharper than it is.

---

## 1. The failure classes actually observed

Not a taxonomy invented up front. These are what two adversarial review rounds
found, sorted after the fact.

### A. The unexecuted claim

A factual assertion written into prose, never run against the thing it describes.
Every instance was *plausible* — that is the whole problem. Plausibility is what
generated it.

Instances:

- `ratect-compat --cleanup` — a flag that has never existed. Copied from a
  planning document into three files. The nearest-looking real flag, `--clean`,
  destroys cache volumes, so the advice was actively harmful.
- "run as an MCP server" — a mode neither binary has. Same source, same commit.
- "Ratect never uses the default bridge — it creates a network per task, or uses
  the one `--use-network` names." Self-contradicting once read carefully. Running
  it gave a *better* answer than either the claim or its correction: Ratect
  accepts `--use-network bridge`, and Docker then refuses with `network-scoped
  aliases are only supported for user-defined networks`.
- "`docker network inspect` reports both [subnet and interface name]." It reports
  the subnet. There is no interface name in the output. Written *in the commit
  that fixed a different unexecuted claim*.
- "ratect 0.5.0 ships 0.26.0's two fixes" — it ships three; the third is a
  security fix sitting in the same unreleased changelog section. Written in the
  commit whose stated purpose was to be "the honest record of a version".

Note the last two. Both were introduced **by fixes for review findings**. That is
failure demand, and it means the fixing step needs the same gate as the writing
step.

### B. The echoed claim

One fact stated in five files by design — `README.md` summarising `ROADMAP.md`
summarising `docs/`, plus `CHANGELOG.md` and a doc comment. Behaviour changes,
whoever fixes it fixes the file they had open, and the other four keep asserting
the old thing at full confidence.

Instances: a `ROADMAP.md` headline bullet claiming a proxy rewrite was
macOS/Windows-only, surviving the entire change that made it work everywhere; a
firewall sentence corrected in `docs/config-reference.md` while its twin in
`docs/differences-from-batect.md` stood; a `CHANGELOG.md` entry still scoping a
behaviour to Linux after the roadmap recorded it as all-platform.

The blast radius of a doc claim is N files. **The unit of repair is the claim,
not the file** — and every tool I had operated on files.

### C. The broken cross-reference

`[`loopback_only_ports`]` in a Rust doc comment, pointing at a function the same
commit deleted. Two of three references were updated.

Instructive detail: I *did* check for this, with `grep 'loopback_only_ports\]'`.
It found nothing, because the text ends `` loopback_only_ports`] `` — backtick
before bracket. The check was the wrong shape for the question and reported
clean. `cargo doc` finds it in one line, with no cleverness.

### D. The handoff transcription

Class A's most reliable source: a planning document or issue describes intended
behaviour, and its names get carried into docs and error messages as though they
described shipped behaviour. A specification cannot see the gap between intent
and binary — that gap is its entire subject matter.

---

## 2. Why they recurred despite rules existing

Ratect's contributor guide already prohibited all four. Guideline 15 says execute
claims rather than grep them; guideline 16 says fix the class and report the
sweep. Both are well-written. Both failed, twice, in one release, with the author
having read them that same day.

Diagnosis:

- **The rules are negative and aspirational.** "Don't write an unverified claim"
  has no failure mode. Nothing goes red. Compliance is unobservable, including to
  the person complying.
- **The instruction file grows on every lesson.** Guideline 15 reached eight
  bullets. Each addition is evidence the previous seven didn't hold, but reads
  like diligence. Growth in that file is a **failure signal**, not a maturity
  signal — and nothing measures it.
- **Verification defaulted to the cheapest available motion**, which is grep.
  Grep answers "does this string appear", never "is this true".

The guide itself contains the correct principle — *"A repeated process error is a
defect in the process, not in the attempt. Resolving to be more careful is not a
fix: change the method, then write it down here."* — and the failure was
following the second half (write it down) while skipping the first (change the
method).

---

## 3. The reframe: drift is not the problem here

Almost every tool in this space defines the problem as **drift** — documentation
and code agreeing once, then diverging as code changes. Detection is therefore
change detection: watch the code, flag the docs bound to it.

**Most of the failures in §1 involved no drift at all.** `--cleanup` never
existed. `docker network inspect` never reported an interface name. "MCP server"
was never a mode. Nothing changed underneath these; they were **wrong on
arrival**. A drift detector watching for code movement is silent on all of them,
because there is no movement to see.

Two distinct problems, needing two mechanisms:

| | Wrong on arrival | Drifted |
| --- | --- | --- |
| Question | "is this true *now*?" | "did the thing this describes move?" |
| Mechanism | verify the claim against the artifact | bind claim to symbol, detect change |
| Trigger | when prose is written | when code changes |
| Catches | classes A, D | classes A (partially), B |

Anything shipping only the right-hand column cannot help with this repo's
dominant class. That single distinction reorders the whole survey below, and it
is the thing I'd want a reusable package to get right that the field mostly
doesn't.

## 4. Survey of existing tools

Thirteen candidates; the ones below were actually read. The reasons matter more
than the verdicts. **Two are worth adopting**, which is a change from the first
pass through this file — and the change came from reading a repo's skill files
rather than its marketing.

### Worth adopting

**`rjmurillo/ai-agents` — `.claude/skills/doc-accuracy`** — the most complete
thing in the survey, and the closest to what §6 sketches. Read it before
building anything.

Six phases, the first three **deterministic scripts with no LLM calls**:

| Phase | Mechanism | Output |
| --- | --- | --- |
| 1 Assessment | enumerate docs + sources, regex-extract public symbols, map doc→source | `assessment.json` |
| 2 Claim extraction | parse Markdown, emit claims with file, line, type, referenced symbols | `claims.json` |
| 3 Compilability | resolve type/method/parameter names in doc examples against the symbol index | `compilability-findings.json` |
| 4 Behavioral | one agent per file group, source read **first**, claims verified against it | `behavioral-findings.json` |
| 5 Cross-document | group quantitative/behavioural claims by topic, resolve conflicting values | `consistency-findings.json` |
| 6 Structure | indexes, navigation, 20% sample of source comments | `structure-findings.json` |

Its axiom is the right one and the one every failure in §1 violated: *"Code
compiles and runs. Documentation describes what code does. When they disagree,
the code is right."* It reads code first and builds a verified model, rather than
reading the doc and asking whether it seems plausible.

What makes it better-engineered than the rest:

- **`--diff-base main`** — incremental, changed files only. The expensive moment
  is the paragraph just written, and this is the only tool here that scopes to it.
- **`--severity-threshold critical` sets the exit code**, with `gate-result.json`
  carrying the verdict. A real gate, tunable, not a report.
- **It knows when it couldn't answer.** If Phase 1 finds no source symbols, Phase
  3 reports `DID_NOT_RUN` with zero findings rather than declaring every doc
  reference unresolved. Almost nothing gets this right; the failure mode it avoids
  is the one that makes people disable a check.
- **Phase 5 is class B, directly** — "same fact, different values across files",
  grouped by topic. Strictly better than `echoed-claims.py`'s n-grams, because it
  compares *values*, not wording.
- **Reconciliation is approval-gated** before any file is modified.
- Its **`Replaces` table publishes measured recall of the skills it supersedes**
  — `incoherence` at 15.8% recall on critical issues, `doc-coverage` at 0% on
  actionable ones. That is principle #2 below, practised, in public, with numbers,
  about the author's own prior work. The most credible single artifact found.

Two real limits, stated because the name oversells one of them:

- **"Compilability" is symbol resolution, not compilation.** Phase 3 looks names
  up in a regex-built index; it does not build or run anything. So a claim that is
  *syntactically* fine and *behaviourally* false — `--use-network bridge` being
  accepted and then refused by Docker — is Phase 4's problem, i.e. an agent
  reading code, not a machine running it. **Nothing in this entire survey executes
  the artifact.** `verify-docs.py`, with its single marker, remains the only
  executing check found anywhere, which is a strange result worth sitting with.
- Symbol extraction is **regex over source**, and the repo is .NET-leaning (its
  domain plugins are OTel/Prometheus). Rust support would need checking, not
  assuming.

**`2389-research/documentation-audit`** — the second-strongest match to §1, and
almost exactly the `claim-extract` component sketched below before I'd read it.

Typed claims with a verification recipe per type:

| Type | Example | Verification |
| --- | --- | --- |
| `file_ref` | `scripts/foo.py` | file exists? |
| `config_default` | "defaults to 'AI Radio'" | check schema/code |
| `env_var` | `STATION_NAME` | in `.env.example` + code? |
| `cli_command` | `--normalize` flag | script supports it? |
| `behavior` | "runs every 2 minutes" | check timers/code |

Tier 1 (`file_ref`, `config_default`, `env_var`, `cli_command`) is auto-verifiable.
That tier alone would have caught `ratect-compat --cleanup`, the worst instance
here, by the obvious means: ask the binary whether the flag exists.

Two design choices worth stealing outright:

- **"Low recall is worse than false positives — missed claims stay invisible."**
  Correct for this problem, and the opposite of how I'd have tuned it.
- **Pass 2A, "expand patterns from false claims to find similar issues"** — this
  is guideline 16's *fix the class, not the instance* as an automated step. Find
  one false claim, derive its shape, search for siblings. The exact step I keep
  performing badly by hand.

Caveats: report-only, no gate; LLM-driven extraction; and its own README is an
install stub with no mechanism documented, which for a documentation-accuracy
tool is a data point about the field.

**`fiberplane/drift`** — the best *mechanical* gate found, and the answer to §8's
open question about claim-to-file manifests.

`drift link` binds a doc region to a file + optional symbol; signatures are
tree-sitter AST fingerprints (node kinds + token text, whitespace and position
normalised away), XxHash3'd into `drift.lock`. `drift check` recomputes and
**exits 1** when a bound doc is stale. CI job or pre-push hook. Supports Rust
among others. No LLM anywhere, no code execution.

Why it matters here: bind all five files that state one behaviour to the same
symbol, and changing that symbol flags all five. That is the declared manifest I
speculated about — mechanised, with change detection for free, and strictly
better than `echoed-claims.py`'s n-grams for the maintenance half of class B.

Its limit is the reframe above: it is a drift detector by construction. Silent on
wrong-on-arrival. It also needs explicit `link` calls, so coverage is opt-in and
un-bound claims are invisible — the same shape as `verify-docs.py`'s one marker.

**Together they cover both columns**: `doc-accuracy` and `documentation-audit`
for "true now?", `drift` for "did it move?". None covers class C, which
`cargo doc -D warnings` already does absolutely — and none *executes*, which is
the gap `verify-docs.py` fills and the one a reusable package should own.

Order to try them, if trying: `doc-accuracy` first (broadest, gated, incremental,
and its Phase 5 may retire `echoed-claims.py`), then `drift` for the bindings,
then `documentation-audit`'s Pass 2A pattern expansion if the first two leave the
class-sweep step unmechanised.

### Not worth adopting, and why

**`BigDanTheOne/docalign`** — closest to a hybrid, and the near-miss. Three tiers:
regex syntactic checks (file paths, deps, CLI commands, API routes, env vars,
config values); LLM extraction of behavioural claims stored with **stable IDs**;
re-verification of those claims against changed source. PostToolUse hook at
commit time, `.docalign.yml` scoping.

The stable-ID claim store is a manifest, and tier 1 is absolute rather than
drift-shaped — both right. But tier 1's checks are npm-shaped (`package.json`
scripts, JS import paths), verification is LLM-reading-code rather than
execution, and it doesn't state whether it fails a build. Worth revisiting; not
worth adopting into a Rust repo as-is.

**`xiaolai/docs-guardian-for-claude`** — its gate fires on *code changed, docs
didn't*. Every defect in §1 shipped in a commit that **did** change docs; it would
have been green throughout. Component-wise: staleness by git timestamp is weaker
than ranking by churn in the code a claim names; coverage-of-public-symbols is
noise in a repo that over-documents by policy; auto-generation is unwanted where
docs are hand-written rationale; its link check is subsumed by a language-native
one. Accuracy-checking against API signatures is the closest part, but signatures
are silent on runtime behaviour, which is where these failures live.

**`Zarl-prog/doc-drift-detector`** — LLM semantic comparison of docstrings and
examples against static analysis; `.doc-drift.yml` with `fail_on: critical` can
fail a build. Python-first, TypeScript "noted but not detailed"; git-diff scanning
and PR pre-flight are beta. Mechanism is "ask a model to compare", which is what
the review agents here already do, with less structure than `documentation-audit`.

**`machug/fact-checker`** — wrong domain (Microsoft/Azure pricing, licensing,
compliance) and wrong mechanism: claims triaged across 2–3 LLMs, disagreements
deep-verified against web/MCP sources. The claims that failed here were about
*this binary and this daemon*; no external source adjudicates them, and a model
panel would converge on the plausible answer — which is how the errors were
produced. **Consensus among models sharing a prior is not verification; it is the
same guess, repeated.** Also wants third-party API keys and ships document
content off-machine. Its step 2 — separating extraction from verification — is
the good idea, and `documentation-audit` implements it better and locally.

**`dosu.dev` documentation-upkeep** — hosted service, monitors GitHub/GitLab/
Slack/Confluence/Notion, generates and updates docs from PRs and discussions. Out
of scope on three counts: hosted (content egress from a private repo),
generative (against ADR 0006's hand-written rationale), and aimed at knowledge
capture rather than claim accuracy.

**`gyujeongion/claude-code-rootcause` — `rethink`** — diagnosis exactly right and
arrived at independently in §2: convert a negative rule into a positive gate,
route to the narrowest layer. Two problems: its layer list (hook/skill/memory/
instructions) **omits tooling and CI**, which is where every one of these
belongs and all four listed layers are still instruction surfaces; and it
delivers the cure for instruction bloat as more instructions. Take the routing
*question*, with a layer list where a mechanical check outranks every
instruction layer.

**`gyujeongion/claude-code-rootcause` — `deusex`** — root-cause redesign for
recurring bugs with a recurrence-impossibility proof. Doesn't fit: these failures
aren't architectural — the proxy *code* drew zero correctness findings across two
review rounds; only its prose did. Take the recurrence-impossibility bar as the
acceptance test for a proposed gate: a CI job that fails is such a proof, a
guideline bullet is not.

### Not read

`mcpmarket.com`'s `documentation-accuracy-auditor` turned out to be
`rjmurillo/ai-agents`' `doc-accuracy`, read above from source. The other four
`mcpmarket.com` skill listings (`documentation-drift-checker`, `documentation-reviewer-6`,
`documentation-accuracy-reviewer`, `documentation-audit-validation`) returned
HTTP 429 and were **not** fetched — no opinion recorded rather than a guessed
one. `aj604/toolshed` and `NathanMaine/memoriant-docforce-skill` not yet read.
The accuracy-auditor in particular was flagged as interesting and still needs a
look.

### `rethink` (gyujeongion/claude-code-rootcause)

Converts "add a rule: never do X" into a positive gate, then routes the fix to a
layer: hook, skill, memory, or instructions.

**The diagnosis is exactly right** and matches §2 independently. Two problems:

1. Its layer list **omits tooling and CI**, which is where every one of these
   belongs. Hook/skill/memory/instructions are all still instruction surfaces.
   The layer that actually worked here was a CI job that fails a build.
2. It's a skill, so the fix for instruction bloat is delivered as more
   instructions. Self-undermining at the margin.

**Take:** the routing question ("what's the narrowest layer that makes this
impossible?") with an extended layer list where *mechanical check* outranks every
instruction layer. That question is the single most valuable thing in the survey.

### `deusex` (same repo)

Root-cause redesign for recurring bugs, with a recurrence-impossibility proof.

Doesn't fit: these failures aren't architectural. The proxy *code* drew zero
correctness findings across two rounds; only its prose did.

**Take:** the recurrence-impossibility bar as an acceptance test for a gate. A CI
job that fails is such a proof. A guideline bullet is not, and asking "would this
have failed?" is a good filter on proposed fixes.

### `docs-guardian-for-claude` (xiaolai)

Five agents (staleness, accuracy, coverage, quality, generation), plus a
PreToolUse hook that can warn or block a commit when code changes ship without
doc updates.

**Its gate is the wrong shape.** It fires on *code changed, docs didn't*. Every
defect above shipped in a commit that **did** change docs. It would have been
green throughout. The problem here is not absent doc updates; it is confident
wrong ones — arguably the harder and more common case in a well-disciplined repo.

Component-wise: staleness by git timestamp is weaker than ranking by churn in the
code a claim *names*; coverage-of-public-symbols is noise in a repo that
over-documents by policy; auto-generation is actively unwanted where the docs
are hand-written rationale; the broken-link check is subsumed by a language-native
one. Accuracy-checking against API signatures is the closest, but it reads
signatures — and the failures here were runtime, where a signature is silent.

**Take:** "documentation drifts like code and needs continuous maintenance" is
right. The gate has to trigger on *content*, not on *whether a file was touched*.

### `fact-checker` (machug)

Extract claims → triage across 2–3 LLMs in parallel → deep-verify disagreements
against web/MCP sources → report → optionally apply corrections.

Wrong domain (Microsoft/Azure pricing, licensing, compliance) and, more
importantly, **wrong mechanism for this class**. The claims that failed were about
*this binary and this daemon*. No external source can adjudicate whether
`ratect-compat --use-network bridge` works. A model panel asked that question
would have converged on the plausible answer — which is exactly how the errors
were produced. **Consensus among models sharing a prior is not verification; it's
the same guess, repeated.** Also wants third-party API keys and ships document
content off-machine.

**Take — and this is the best idea in the survey:** its step 2. **Claim
extraction is a separate operation from claim verification**, and separating them
is what stops the writer from verifying only the assertions that happen to occur
to them. Keep extraction; replace the LLM-panel backend with **local execution**.

---

## 4. What was built here, and what each actually covers

Honest coverage, including misses. A sweep tool trusted past its range is worse
than no tool.

| Thing | Mechanism | Covers | Misses |
| --- | --- | --- | --- |
| `Rustdoc` CI job (`RUSTDOCFLAGS=-D warnings cargo doc`) | language-native, deterministic, fails the build | class C, absolutely | anything not a doc-comment link |
| `tools/verify-docs.py` | executes commands marked `<!-- verify: -->`, diffs real output | class A **exactly**, where the claim is a command's output | prose assertions; needs a fenced block; 1 marker exists in the whole repo |
| `tools/echoed-claims.py` (new) | n-grams of deleted prose vs surviving tracked Markdown | class B, verbatim half | restatement — measured, not assumed: finds the firewall twin, misses the ROADMAP bullet |
| `tools/stale-claims.py` | ranks prose by churn in the code it names | pointing attention | scores class B zero (no code churn involved) |
| `tools/spliced-docs.py` | doc comment attached to the wrong item | structural drift | content |

Three implementation lessons from `echoed-claims.py`, all found by running it,
none anticipated:

1. **Reflow looks like deletion.** Editing a paragraph removes and re-adds most
   of it. Without subtracting the added text, the tool reports what the commit
   *kept*. First run: three hits, all noise, real one absent.
2. **Claims don't respect line wraps.** Hard-wrapped prose split the target
   phrase across two lines; per-line matching found *nothing at all*. Match over
   a word stream, report the line a run starts on.
3. **Threshold is empirical.** 8-word runs missed "for every network *it*
   creates" vs "for every network *Ratect* creates". 6 catches it. Nothing but
   running it against real history would have said so.

And a live demonstration while writing the guide entry for the tool: I typed a
sentence claiming it caught **both** motivating cases, having measured ten minutes
earlier that it catches one. Caught before commit. The person building the gate
committed the class the gate exists for — which is the strongest available
argument that the gate belongs somewhere other than in a person's discipline.

---

## 5. Principles falling out

1. **Prefer a gate that fails over a rule that reminds.** Acceptance test: would
   it have gone red on the actual defect? If not, it's a note.
2. **A tool must measure and publish what it misses.** Ideally by running it
   against the historical instances it was built for and reporting the ones it
   doesn't catch, in its own header.
3. **Verification is execution against the artifact.** Not grep, not signature
   reading, not model agreement.
4. **Extraction and verification are separate steps.** Enumerate the falsifiable
   assertions first, as a list, then discharge each. Writers verify what occurs
   to them; lists don't have that bias.
5. **Route to the narrowest mechanical layer.** Ranked: language-native check >
   project check in CI > local script > checklist > instruction file. Instructions
   are the layer of last resort, and their growth should be tracked as a defect
   rate.
6. **Candidate lists exit 0; deciders need tests.** Ratect's convention and a good
   one — a wrong verdict from a decider blocks a release; a bad ranking costs a
   skim.
7. **The unit of repair is the claim, not the file.** Every existing tool operates
   on files, which is why class B survives all of them.
8. **The fixing step needs the same gate as the writing step.** Two of the worst
   instances were introduced by fixes for review findings.

---

## 6. Sketch of the reusable thing

Language-agnostic core, thin per-language adapters. Nothing here is built beyond
what §4 lists.

- **`claim-extract`** — given a diff, emit every falsifiable assertion in changed
  prose, each with a proposed *executable* discharge (a command to run, a symbol
  to resolve, a file to stat) or an explicit "not mechanically checkable". The
  output is a checklist a human or an agent works through.

  **Largely exists**: `2389-research/documentation-audit`. Adopt or fork rather
  than rebuild. What it lacks for this use is (a) a *diff* scope — it audits
  whole docs, where the expensive moment is the paragraph just written; (b) any
  gate, it reports; (c) verification by **execution** rather than by reading code
  (its `cli_command` recipe asks "script supports it?", which for a `clap` binary
  should be `--help`, not source inspection). Its typed-claim table and its
  Pass 2A pattern expansion are the parts to keep.
- **`echoed-claims`** — as built, generalised past Markdown, with an honest
  restatement story (open question below). **Reconsider first**: `fiberplane/drift`
  solves the maintenance half of class B better, by binding docs to symbols and
  detecting AST change, and a declared binding beats an n-gram guess. This stays
  only if the *un*bound case matters — prose nobody thought to link.
- **`executable-claims`** — `verify-docs.py` generalised: mark a claim, bind it to
  a command, diff. Needs to work for prose assertions, not just fenced output
  blocks — probably by letting a marker assert a *predicate* over output rather
  than equality with it.
- **Reference gates, per language** — adapters onto whatever the language already
  has (`cargo doc -D warnings`, `mkdocs --strict`, TypeScript project references,
  Sphinx nitpicky). Wrap, don't reimplement.
- **`route-the-lesson`** — a checklist, not a skill: given a defect about to
  become a rule, which layer kills the class? Refuses "add a bullet" until the
  mechanical layers have been ruled out, and tracks instruction-file growth as
  the failure rate it is.

## 7. Open questions

- **Restatement detection.** The commonest shape of class B and the one nothing
  catches by inference. **Partly answered**: `drift`'s explicit bindings are the
  declared manifest this question was reaching for, and they sidestep restatement
  entirely — a binding doesn't care how the prose is worded. The cost moves to
  coverage: an unbound claim is invisible, so the open question becomes *how do
  you know what you failed to bind?*, which is the same question `verify-docs.py`
  has with one marker in the whole repo. Possibly: measure binding coverage and
  treat it like test coverage — a number to look at, not a target.
- **Keeping extraction honest without a model panel.** Extraction is inherently a
  language task; verification must not be. Where exactly does that line sit, and
  what stops the extractor from quietly grading its own work?
- **What stays human.** Reading a summary against its source and noticing they've
  diverged in meaning while sharing no phrases is, right now, the thing only a
  reviewer does. Worth being explicit that the goal is to shrink the reviewer's
  surface, not to remove them.
- **Is the wrong-on-arrival/drifted split the right axis?** §3 asserts it from
  one repo's instances. If it holds elsewhere it should reorder any survey, since
  most of the field builds only for the second column. If it doesn't, this whole
  file is over-fitted to a repo whose docs are unusually claim-dense.
- **Does any of this survive contact with the other two projects?** Sample size
  one. The next step before building is to write down their instances and check
  whether the same five classes appear, or whether Ratect's doc-heavy conventions
  (ADR 0006) make it unrepresentative.

## 8. Provenance

Ratect commits `c9f1b23` (the two gates), and the review rounds over
`1889a18...HEAD` on 2026-09-01/02 that produced the evidence. Surveyed:
`gyujeongion/claude-code-rootcause`, `xiaolai/docs-guardian-for-claude`,
`machug/fact-checker`.
