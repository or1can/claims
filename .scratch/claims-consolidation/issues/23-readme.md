# 23 — README

**What to build:** a top-level `README.md`. None exists today — a visitor
landing on this repo has `plugin.json`'s one-line `description`, `AGENTS.md`'s
"Guidelines for AI Agents" (working principles, not what this project *is*),
and `.scratch/claims-consolidation/` (a project's working notes, not a
front door). Nothing states, in one place, what this checks, why it exists,
and what it isn't.

Should draw on, without duplicating: `.claude-plugin/plugin.json`'s
description (the check inventory — executable-claims, stale-claims,
restatement, spliced-docs, claim-words, check-citations, check-links, the
judgment-agent subagent); `.scratch/claims-consolidation/doc-integrity-tooling.md`
§3's reframe (wrong-on-arrival vs. drifted, why this matters); §5's
principles (gate over reminder, verify by execution not grep). The README
states the *what* and *why* for a reader who hasn't read the working notes;
it doesn't restate their argument in full — link to the relevant working
notes for the reasoning, if this repo goes public with `.scratch/` intact,
or fold the essential parts in if it's pruned before publishing (see ticket
03's licensing note on going public under Apache-2.0/MIT).

**Blocked by:** none directly, but should reflect tickets 07–22's shipped
state (all four consolidated checks plus check-citations/check-links/
claim-words/judgment-agent, the skill+hook+plugin packaging).

**Status:** ready-for-agent

- [ ] States what the plugin does in the first paragraph, without requiring
      `plugin.json` or the working notes to understand it.
- [ ] Lists the checks it ships (mechanical: executable-claims, stale-claims,
      restatement, spliced-docs, claim-words, check-citations, check-links;
      judgment-shaped: the judgment-agent subagent), each in one line —
      what it catches, gate or advisory.
- [ ] Links to or summarizes the licensing/provenance story (Apache-2.0,
      ported prior art from `ratect` and two private projects — see NOTICE
      and ticket 03's Answer) accurately, not just "Apache-2.0" bare.
- [ ] Does not restate installation steps in full if ticket 24 owns that —
      links to it (or the file it produces) instead of forking the story in
      two places.
