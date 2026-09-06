# 12 — Port check-citations check (gate)

**What to build:** a check finding a backticked name that cites a symbol the
project once declared (via full commit history) but no longer does.
Registered as a **gate** check.

**Blocked by:** 06.

**Status:** ready-for-agent

- [ ] A citation to a symbol that was removed after being declared is
      flagged.
- [ ] A citation to a symbol that still exists is not flagged.
- [ ] An explicit "was: <name>" marker exempts a deliberately historical
      reference.
- [ ] Run against a shallow clone (insufficient history to answer honestly)
      fails distinctly rather than reporting a false clean pass.
