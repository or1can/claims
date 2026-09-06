# 15 — Judgment-agent subagent

**What to build:** a subagent that takes the ranked candidates from ticket
14, reads the actual code for each, and produces a verdict citing a
`file:line` or the exact command it ran — never grepping the prose
describing the claim. Never blocks a commit on its own judgment.

**Blocked by:** 14.

**Status:** ready-for-agent

- [ ] Given a known-true architectural claim and a known-false one against
      real code, the subagent correctly distinguishes them.
- [ ] Every verdict cites a `file:line` or the command run — a verdict with
      no evidence attached is treated as a failure of the subagent, not an
      acceptable output.
- [ ] The subagent does not grep for vocabulary describing the claim as its
      evidence-gathering method — verified by checking it reads/executes
      the actual code path the candidate names.
- [ ] Tested via behavioral/golden fixtures (known-true/known-false cases),
      not unit tests — this is a different testing shape from every other
      check in this batch, and the ticket's own test suite should say so.
