# 13 — Port check-links check (gate)

**What to build:** a check validating every internal Markdown link,
including heading anchors (GitHub slug algorithm). Registered as a **gate**
check.

**Blocked by:** 06.

**Status:** ready-for-agent

- [ ] A link to a path that doesn't exist is flagged.
- [ ] A link to a heading anchor that doesn't resolve (including a
      multi-word heading's slug) is flagged.
- [ ] A correct relative link with an anchor is not flagged.
