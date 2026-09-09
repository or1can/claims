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

**Status:** resolved

- [x] States what the plugin does in the first paragraph, without requiring
      `plugin.json` or the working notes to understand it.
- [x] Lists the checks it ships (mechanical: executable-claims, stale-claims,
      restatement, spliced-docs, claim-words, check-citations, check-links;
      judgment-shaped: the judgment-agent subagent), each in one line —
      what it catches, gate or advisory.
- [x] Links to or summarizes the licensing/provenance story (Apache-2.0,
      ported prior art from `ratect` and two private projects — see NOTICE
      and ticket 03's Answer) accurately, not just "Apache-2.0" bare.
- [x] Does not restate installation steps in full if ticket 24 owns that —
      links to it (or the file it produces) instead of forking the story in
      two places.

## Answer

Added a top-level `README.md`: first paragraph states what the plugin does
and why (the wrong-on-arrival vs. drift distinction from
`doc-integrity-tooling.md` §3), a "What it checks" section listing all seven
mechanical checks plus the judgment-agent subagent (one line each, tagged
gate/advisory), a "What it isn't" line, a short "Installing" paragraph
(mechanism only — pinned git-URL plugin, hook opt-out — not full steps,
since ticket 24 owns those and hasn't landed a target file yet to link to
without creating a dead link), and a "License" section.

**Correction to this ticket's own citation:** the checklist item above
points at "ticket 03's Answer" for the licensing story, but ticket
03 (`03-distribution-mechanism.md`) is entirely about the distribution
mechanism and contains no licensing note. The actual licensing decision
(Apache-2.0, `ratect` already Apache-2.0, the private Swift project's rights
holder confirming relicensing, neither private project named/linked/pathed
anywhere in this repo) is `map.md`'s "Decisions so far", not ticket 03. The
README links `NOTICE` and summarizes `map.md`'s decision inline rather than
citing ticket 03. Flagging this rather than quietly propagating a wrong
citation, given what this repo checks for.
