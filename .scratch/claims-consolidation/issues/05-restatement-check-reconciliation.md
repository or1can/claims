Type: grilling
Status: resolved

## Question

`echoed-claims.py` (`ratect`) and `split-claims.py` (the private Swift project
— see tool-survey.md's Project B) both catch the same
failure class — a correction made in one place while the same fact survives
uncorrected elsewhere — but by different mechanisms: `echoed-claims.py` matches
verbatim 6-word runs surviving from a diff's removed lines; `split-claims.py`
matches whole normalized lines (≥10 words) surviving from a diff's removed
lines, over a wider file-type set (`*.md,*.swift,*.py,*.sh,*.yml` vs
markdown-only).

Decide: merge these into one "restatement" check in the consolidated core (and
if so, on which matching strategy — n-gram run, whole-line, or both kept as
separate signals within one check), or keep them as two distinct checks that
both ship. Whichever is chosen, note it as a resolved answer for the
"language-agnostic core" fog item on the map, since this is the concrete case
that decision needs to generalise past.

## Answer

**Merge into one `restatement` check, running both signals as two reported
modes**: n-gram-run survival (Project A's threshold, 6 words — empirically
tuned; doc-integrity-tooling.md records 8-word runs missing a real case that
6 caught) and whole-normalized-line survival (Project B's threshold, ≥10
words). One tool, one CLI entry point, no coverage lost from either parent —
a finding reports which mode fired rather than the two staying separate
maintained tools.

**Verbatim-only scope, kept deliberately, blind spot documented rather than
solved.** Project C independently evaluated adopting Project A's tool for
exactly this problem and declined it: "deliberately verbatim-only," and its
actual failures that session were paraphrase, not verbatim duplication — it
"would have caught none of them" (see tool-survey.md's Lineage section for
the full account). This check inherits that same limit by design, and its
own output/docs must say so plainly, per this repo's own principle "a tool
must measure and publish what it misses" (doc-integrity-tooling.md §5).
Paraphrase detection is a judgement-shaped problem, not a mechanical one —
out of scope here, arguably in the judgment-agent's territory (ticket 04)
rather than this check's.

**Output is the finding only, no architectural nudge.** The check reports
"this fact is duplicated at X and Y," not a suggested fix. Project C's own
practice where it has hit verbatim duplication — replace both sites with one
canonical constant they both reference, rather than relying on a checker —
and an external symbol-binding drift detector surveyed in
doc-integrity-tooling.md formalise the same idea (bind a claim to a symbol
so restatement is prevented by construction). Worth documenting as
recommended practice for this project's users; not baked into every
finding's output as an assertion the detector isn't positioned to make.

**File-type scope: configurable per consuming project, seeded with the union
of both source tools' coverage as the default** (Markdown, Swift, Python,
Shell, YAML). A project adds its own extensions via config — e.g. `ratect`
would add `.rs`, not currently covered by either source tool. This is the
concrete answer the map's "language-agnostic core + per-language adapter
design" fog item needed: the core's file-type scope is a config surface, not
a hardcoded list per language.
