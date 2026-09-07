# 09 — Port + merge restatement check (advisory)

**What to build:** one restatement check merging the two source tools'
matching strategies as two reported modes — n-gram-run survival and
whole-normalized-line survival — against a diff's removed lines,
registered as an **advisory** check with a configurable file-type scope.

**Blocked by:** 06.

**Status:** resolved

- [x] A short phrase (n-gram run) removed from one file and surviving
      verbatim elsewhere is flagged, with the mode reported as the n-gram
      signal.
- [x] A whole line (≥10 words, normalized) removed from one file and
      surviving verbatim elsewhere is flagged, with the mode reported as the
      whole-line signal.
- [x] A paraphrase (same fact, different wording, no verbatim overlap) is
      confirmed **not** flagged — the check's own output/docs state this
      boundary explicitly rather than implying broader coverage.
- [x] File-type scope is configurable per project; the default is the union
      of both source tools' original coverage (Markdown, Swift, Python,
      Shell, YAML).
- [x] Never fails the run (advisory).

## Answer

`claims/checks/restatement.py` — `NAME = "restatement"`,
`check(repo_root, diff_range, config) -> list[Finding]`, self-registered as
an **advisory** check (`gate=False` on every finding) at import time, wired
into `claims/checks/__init__.py` alongside tickets 07/08's checks.

Merges the two source tools into one check, two reported modes on one
`Finding.mode` rather than two maintained checks: `restatement-ngram` (a
6-word run — `ratect`'s `echoed-claims.py`, Apache-2.0 prior art, same
author, ported directly) and `restatement-whole-line` (a whole normalized
line, ≥10 words — the private Swift project's `split-claims.py`, same
author, re-expressed in Python since the source is Swift). Both modes read
a diff's removed lines and subtract anything the diff also *added* — a
rewrapped paragraph removes and re-adds most of itself, and a thing still
said isn't a thing retracted. The whole-line mode's subtraction checks
against the diff's added *word stream* (not added lines one-for-one), so a
line reflowed across new line boundaries by the same edit still cancels
correctly — the n-gram mode's existing reflow tolerance, generalised to
line-length runs instead of fixed 6-word ones.

Verbatim-only by design, documented in the module's own docstring per
ticket 05's resolution: a paraphrase shares too few consecutive words (n-
gram) and won't match line-for-line (whole-line), and the check's docstring
says so plainly rather than implying broader coverage.

File-type scope: `config["extensions"]` (a list of dotted suffixes) is
*added* to the default union of both source tools' coverage (`.md`,
`.swift`, `.py`, `.sh`, `.yml`), matching ticket 05's resolution — e.g.
`ratect` would add `.rs`.

Tests: `tests/test_restatement.py`, fixture diffs exercising both modes
independently, a paraphrase confirmed not flagged, reflow noise (rewrapped,
not retracted) confirmed not flagged for both modes, advisory-not-gating,
the default scope union, scope outside the union not read, and configured
extensions adding to (not replacing) the default. 43 tests total across the
suite (`python3 -m unittest discover -s tests -p 'test_*.py'`), all green.

Post-review (`/code-review` against this ticket) found one real bug and one
real inefficiency, both fixed before commit: subtraction was computed
across the *whole diff's* merged removed/added word stream, so an unrelated
file's incidental addition in the same commit could cancel a genuine
retraction in a third file — confirmed by direct reproduction — fixed by
scoping subtraction to each file-pair the diff touches (`_diff_by_file`),
with a regression test. Separately, firing both modes swept every tracked
file twice (once per mode); merged into one `_survivors` pass that reads
and normalizes each tracked file once and reports both modes' hits from it.
