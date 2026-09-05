Type: research
Status: resolved

## Question

[prior-art-notes.md §3](../prior-art-notes.md) left its own candidate-list
question open: what bounds the set of claims the judgment-agent spends a
reader on, given:

- Diff-scoping alone under-selects — a rename in code can falsify prose in a
  file the diff never touches (§1's motivating case).
- Churn-ranking (`stale-claims.py`, both Project A's and Project B's — see
  tool-survey.md) is known blind to the failure mode where claim and code
  move in the same commit — every churn signal reads zero.
- The candidate list must be ranked, never a clean "all good" verdict (§1's
  own finding: a periodic sweep that reports nothing most nights trains
  nobody to read it).

Derive what "prose whose subject the diff touched" is actually made of — i.e.
what a subject-extraction step would need to do that diff-scoping and
churn-ranking both fail to do — reading the existing extractors
(`2389-research/documentation-audit`'s typed-claim recipes,
`rjmurillo/ai-agents`'s `doc-accuracy` Phase 1 symbol index, per
doc-integrity-tooling.md §4) for the shape of a subject, not to adopt them as
dependencies (per the map's Notes — external tools are design influence only).

Two constraints from prior-art-notes.md §3 apply to any answer: it must
execute or read the code, never grep the prose (a prior attempt at a related
classification task grepped log text for expected failure-signature strings
and got the classification backwards, because those strings appear ambiently
in unrelated boilerplate every run loads regardless of outcome); and every
verdict it eventually produces must cite a `file:line` or the command run.

## Answer

Full findings, read against primary sources (fetched `doc-accuracy`'s actual
`doc_accuracy.py` and `documentation-audit`'s actual skill files from GitHub,
not doc-integrity-tooling.md's summary; read Project A's and Project B's
`stale-claims.py`/`claims.py`/`check-citations` source directly — see
tool-survey.md): commit
`1dd432f` on branch `research/judgment-agent-candidate-list`, file
`.scratch/claims-consolidation/issues/04-judgment-agent-candidate-list-findings.md`
(`git show research/judgment-agent-candidate-list:.scratch/claims-consolidation/issues/04-judgment-agent-candidate-list-findings.md`).

Gist: the mechanism factors into three deterministic operations. (1) Build a
subject index from code — already solved, five different ways, across the six
tools surveyed. (2) Compute the diff's touched-subject delta — which subjects
were added/removed/renamed *by this diff specifically* — **nothing in any of
the six tools does this**; `doc-accuracy`'s `--diff-base` scopes only which
doc *files* get read while source symbols stay fully indexed regardless
(`doc_accuracy.py:669-675`), reproducing prior-art-notes.md §1's exact failure
inside a tool built to prevent it. Both `stale-claims.py`s compute a monotonic
churn score, not a binary this-diff-changed-it test, so a same-commit move
reads zero by construction (documented as Project B's own known blind spot —
see tool-survey.md). (3) Match
prose to that closed subject set via citation-shaped token extraction
(backticked names, path literals) plus exact set-membership —
`check-citations`'s `CITATION_RE` + `gone`-set-membership already does this
correctly; `doc-accuracy`'s unguarded substring match (`name in doc_content`)
does not.

Operation 2 is the missing piece and the one to build; operations 1 and 3
already have working reference implementations to draw the *shape* from
(never as a dependency, per map.md's Notes). This reconciles with "never grep
the prose": that constraint governs where the vocabulary and ground truth
come from (code, not guessed keywords), not whether prose is searched at all
— operation 3's closed, code-derived token match is a fundamentally different
operation from the transcript-grep failure the constraint was written against.
Candidates must carry both the citing `file:line` and the diff evidence
(which commit(s) touched the subject) so the downstream judgment-agent's
`file:line` citation requirement doesn't force the reader to re-derive
operation 2 by hand. Full detail, including what still doesn't get solved
(the match step remains a disciplined token search; rename-pairing is a
refinement, not solved by any tool surveyed), is in the findings file linked
above.

**Caveat:** the branch findings file itself names the private source repos
and their absolute local paths verbatim (it was written before the
no-names/no-links decision below). This ticket's Answer above is the scrubbed
summary — safe to keep. The branch is throwaway and must not be merged into
main as-is; if its full detail is ever wanted on main, it needs the same
anonymisation pass prior-art-notes.md and tool-survey.md already got.
