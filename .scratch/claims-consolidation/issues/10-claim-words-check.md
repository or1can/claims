# 10 — Port claim-words check (advisory)

**What to build:** a diff-scoped sweep over added lines for totalising
words ("every", "only", "never"), spelled-out or digit counts, and words
asserting something "elsewhere" only when adjacent to a citation, scoped to
whole sentences within designated record-like files. Registered as an
**advisory** check.

**Blocked by:** 06.

**Status:** ready-for-agent

- [ ] A totalising claim that generalises past what a nearby table/figure
      actually supports is flagged.
- [ ] A spelled-out or digit count is recognised regardless of magnitude
      (not capped at a fixed ceiling).
- [ ] A document quoting its own retired false claim (the house style for
      retiring a sentence — an italic, a block quote, or a fixed lead-in
      phrase) does **not** fire on the quotation.
- [ ] A number that measures the world (an external count, a byte
      comparison) is not treated the same as a number describing the tree.
- [ ] Never fails the run (advisory).
