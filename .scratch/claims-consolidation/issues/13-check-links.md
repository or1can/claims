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
- [ ] A link ending `...md#anchor)` (path plus anchor, not just a bare
      `.md)`) is checked, not silently skipped — the source tool's first
      version required a link to end in `.md)` and so never validated any
      anchored link while still claiming full coverage; this is a named
      regression case, not just implied by the anchor-resolution bullet
      above.
