Type: grilling
Status: open

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
