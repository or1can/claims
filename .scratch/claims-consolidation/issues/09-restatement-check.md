# 09 — Port + merge restatement check (advisory)

**What to build:** one restatement check merging the two source tools'
matching strategies as two reported modes — n-gram-run survival and
whole-normalized-line survival — against a diff's removed lines,
registered as an **advisory** check with a configurable file-type scope.

**Blocked by:** 06.

**Status:** ready-for-agent

- [ ] A short phrase (n-gram run) removed from one file and surviving
      verbatim elsewhere is flagged, with the mode reported as the n-gram
      signal.
- [ ] A whole line (≥10 words, normalized) removed from one file and
      surviving verbatim elsewhere is flagged, with the mode reported as the
      whole-line signal.
- [ ] A paraphrase (same fact, different wording, no verbatim overlap) is
      confirmed **not** flagged — the check's own output/docs state this
      boundary explicitly rather than implying broader coverage.
- [ ] File-type scope is configurable per project; the default is the union
      of both source tools' original coverage (Markdown, Swift, Python,
      Shell, YAML).
- [ ] Never fails the run (advisory).
