# 14 — Judgment-agent candidate mechanism

**What to build:** the deterministic half of the judgment-agent — a check
that (1) builds a subject index from code, (2) computes the diff-scoped
touched-subject delta (which subjects were added/removed/renamed by this
diff specifically), and (3) matches prose against that closed set via
citation-shaped token extraction. Registered as an **advisory** check
producing ranked candidates, each carrying both the citing `file:line` and
the diff evidence for why the subject counts as touched.

**Blocked by:** 06.

**Status:** ready-for-agent

- [ ] Given a fixture repo where a diff renames a symbol, prose citing the
      old name in a file the diff never touched is still surfaced as a
      candidate — not missed the way diff-scoping-by-file would miss it.
- [ ] Given a fixture repo where the claim and its subject are edited in the
      same commit, the subject is still surfaced (not scored to zero the
      way churn-ranking would).
- [ ] Every candidate carries the citing `file:line` and the commit(s) that
      touched the subject.
- [ ] Never issues a clean "nothing to review" verdict when candidates
      exist — it ranks, it doesn't clear.
