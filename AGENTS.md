## Guidelines for AI Agents

### Working principles

Reproduced verbatim (headings demoted to fit this document) from
[andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills/blob/main/CLAUDE.md),
MIT-licensed — see [`NOTICE`](NOTICE) for the attribution — so anyone working in
this repo has them without installing anything.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial
tasks, use judgment.

#### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

#### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

#### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

#### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

### The change loop

**For any change:** specification → suite red → code → suite green → write
prose.

Derive the red **and** the code from the specification, independently. When the
two disagree, the fault may be in the red, the code, or the specification.

Specification first, because otherwise there is nothing to derive from
independently — a red written from unstated intent is the code by another
route. Usually one sentence, not a document; where the handoff or an ADR
already settles it, cite that rather than restate it.

Write the prose from the specification and the code **as delivered** —
re-read and re-run, not remembered; it is also how you reload both. "The code"
includes whatever the prose *names*: a sentence about something is written with
that thing open.

Red is omitted only where the change alters no behaviour; say so out loud when
it is.

### Constant gardening

Read strictly, "touch only what you must" says to leave
every defect you notice in passing, and things left that way rot: the
`load_project` doc comment sat on the wrong function on `main` until a reviewer
found it, and `TODO.md` still described behaviour a release had deleted. So the
rule here is the opposite of leaving it — when you are already working in an
area and you spot something wrong, fix it then, because that is the cheapest
this fix will ever be and nobody is coming back for it.

This does not conflict with surgical changes, because the thing that rule is
actually protecting is the **diff**, not the defect. Give the gardening its own
commit, so every changed line still traces to one intent and the
unrelated fix can be reviewed, bisected or reverted on its own. Fold it into the
feature commit and you have the problem the rule warns about; land it separately
and you have a tidier repo and a reviewable history. What stays out of scope is
work you cannot finish or verify to the same standard as the change you came
for — note that in `TODO.md` instead.

### Typechecking

`pyright claims tests` stays clean:

<!-- verify: pyright claims tests -->
```
0 errors, 0 warnings, 0 informations
```

## Agent skills

### Issue tracker

Issues tracked as local markdown files under `.scratch/`. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical roles, label string equal to name (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — `CONTEXT.md` + `docs/adr/` at repo root. See `docs/agents/domain.md`.
