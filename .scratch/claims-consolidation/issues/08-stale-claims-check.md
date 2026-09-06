# 08 — Port stale-claims check (advisory)

**What to build:** a churn-ranked staleness check — ranks prose sections by
how much the code subject they name has changed since the claim was last
touched — registered as an **advisory** (candidate-list) check.

**Blocked by:** 06.

**Status:** ready-for-agent

- [ ] Given a fixture repo, sections are ranked highest where the named
      subject has the most commits since the claim's last edit.
- [ ] A claim and its subject edited in the same commit scores at (or near)
      zero — the check's own output documents this as a known blind spot,
      not a silently accepted gap.
- [ ] Never fails the run (advisory, exit 0 regardless of findings) — it
      produces a ranked list, not a verdict.
- [ ] Demonstrated end-to-end via the CLI against a fixture repo with at
      least one genuinely stale claim and one same-commit-move claim.
