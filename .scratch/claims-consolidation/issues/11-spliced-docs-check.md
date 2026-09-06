# 11 — Port spliced-docs check (advisory)

**What to build:** a structural check finding a doc comment spliced onto the
wrong declaration (an edit landing between the comment and its item),
reported only when the stranded prose names an undocumented item in the same
file (or resolves to nothing anywhere in the repo). Registered as an
**advisory** check, ported for whichever language(s) the source tools
already covered — no new language-adapter interface designed in this
ticket.

**Blocked by:** 06.

**Status:** ready-for-agent

- [ ] A doc comment separated from its declaration by an intervening item is
      flagged when the stranded prose names an in-file undocumented item.
- [ ] A doc comment naming something that resolves to nothing anywhere in
      the repo is flagged.
- [ ] A doc comment correctly attached to its declaration is not flagged.
- [ ] Never fails the run (advisory).
