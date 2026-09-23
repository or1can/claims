# 0004. `docs/` is the user-facing tree

## Status

Accepted. Spec #56, implemented by ticket #58.

## Context

Every check is already described in four places: `README.md`'s check list
(one bullet, severity and one-line behaviour), `docs/configuration.md` (one
section, `claims.toml` example and key table), the check inventory in
`.scratch/claims-consolidation/spec.md`, and the check's own module
docstring — the authoritative account of what it does and what it misses.
Some also appear in `claims/skill/SKILL.md`. A published documentation site
would make a fifth, in a repo whose whole purpose is catching a claim
restated in one place and drifted in another.

Publishing one means picking an mdBook source root, and mdBook publishes
whatever that root contains. `docs/` here is mixed: `docs/installation.md`
and `docs/configuration.md` are written for a user, while `docs/adr/` and
`docs/agents/` are written for a contributor. There is no source root that
publishes the first pair and not the second without either splitting the
tree or nesting the book inside it.

or1can/ratect — same author, same conventions, a complete working instance
of what is proposed — split it the other way round and states the rule
outright in its own `agents/docs.md`: its `decisions/` directory
"deliberately is *not* `docs/adr/` — `docs/` is the user-facing tree, and
ADRs are for contributors." Its second reason for not moving them does not
transfer: it cites breaking links from already-released changelog sections,
and this repo's `CHANGELOG.md` and all three ADRs contain zero internal
Markdown links. What they contain instead is three backticked bare paths,
two naming an ADR under `docs/adr/` and one naming `docs/configuration.md`,
which `check-file-refs` resolves against the working tree and would gate on
after a move. Only the first two are pointers this decision moves; the
configuration page stays where it is.

`AGENTS.md` asserts a single-context layout with `docs/adr/` at the repo
root, matching the `domain-modeling` skill's own default. That is a
default, not a constraint the tooling enforces.

## Decision

`docs/` holds user-facing pages only, and becomes the mdBook source root
when #56 publishes one; no book exists yet.
Architecture decision records move to `decisions/` at the repo root, and
agent-facing process docs move to `agents/`. `AGENTS.md` is amended to
describe this layout rather than the previous one.

`CHANGELOG.md`'s two ADR pointers are retargeted in the same commit as
the move, which settles a rule this repo had not previously stated: a shipped
changelog entry's prose is never edited, its pointers are retargeted when
the thing they name moves. ADR 0002 anticipated exactly this choice and
declined to make it on a consuming project's behalf — "it is the consuming
project's rule to relax, not this plugin's to assume" — and its second
consequence, that a line a later commit touched must hold as of that
commit, already makes a pointer-only edit re-blame and re-test cleanly.

## Alternatives considered

- **Nest the book instead of moving anything** (`src = "docs/book"`).
  Costs nothing today and breaks no pointer. Rejected because it leaves
  `docs/` meaning two things at once, which is the condition that produced
  the four-surface problem above; the nesting is a workaround for a tree
  that has not been decided rather than a decision.
- **Publish the ADRs as a book section.** Attractive at first: `README.md`
  already links two of them as the explanation of deny-by-default and
  historical-link resolution, so a reader following that link should land
  on a rendered page. Rejected because it makes contributor rationale a
  user-facing surface, and ratect's rule 4 — a user page links out for
  reasoning, never for the fact — is the better shape: the site links to
  an ADR for the why, and the ADR stays a contributor document.
- **Keep `docs/configuration.md` canonical and have the site link to it.**
  Preserves every pointer for free. Rejected because it keeps the surface
  that per-check pages are meant to absorb, so the site becomes the fifth
  copy rather than replacing the second.
- **Give `check-file-refs` a `historical` mode** mirroring ADR 0002, so
  the changelog's pointers resolve at the commit that wrote them and need
  no edit. Rejected here as scope creep — three pointers is not the scale
  that made 0002 necessary for links, and a dead pointer left resolving
  only historically still strands the reader who wants to follow it. The
  asymmetry is real for a consumer citing paths at ratect's scale and is
  filed as its own issue.

## Consequences

- `claims.toml`'s `[check-file-refs] exclude` entry changes from
  `docs/adr/*.md` to the ADRs' new location. Its stated reasoning gains a
  second clause: the directory now also narrates the pre-move layout on
  purpose, this ADR most of all.
- `.scratch/claims-consolidation/` takes the same rule, not an exception.
  Its four pointers — one to ADR 0001 in `spec.md`, three to the issue
  tracker guide under `issues/` — all cite a document that still exists and
  still says what is claimed of it, so all four move. That directory is
  excluded from `check-file-refs` and `check-cli-flags` for what it *says*
  (hypothetical paths, superseded script names), not because it is frozen:
  a resolved ticket's record is amended when it turns out to overclaim, as
  `0dea220` and `2689a17` both did. #56 will declare a freeze; none is in
  force today, and `AGENTS.md` asserts none.
- Two files under `claims/` name a moved path: `executable_claims.py`
  cites ADR 0001 for the residual gap deny-by-default leaves, and
  `check_file_refs.py` uses `docs/agents/` in the worked example of a
  repo-root-anchored mention it deliberately skips. So the move requires a
  `plugin.json` version bump and a `CHANGELOG.md` entry — it is not a
  docs-only change. (`claims/skill/SKILL.md` names only
  `docs/configuration.md`, which does not move.)
- Any future move of a path named in a shipped changelog entry needs the
  same pointer retarget, for as long as `check-file-refs` has no
  historical mode. Cheap at two pointers; the issue above is what
  raises the ceiling.
- This repo's layout now differs from the `domain-modeling` skill's
  default, so an agent running that skill may propose `docs/adr/`.
  `AGENTS.md` naming the real layout is what stops that.
