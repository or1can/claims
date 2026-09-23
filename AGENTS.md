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

`uv run pyright claims tests` stays clean — pinned via `pyproject.toml`'s
`dev` dependency group and `uv.lock`, not whatever `pyright` happens to be
on `PATH`. `PYRIGHT_PYTHON_IGNORE_WARNINGS=1` silences the pyright-python
wrapper's own "a newer pyright exists on PyPI" nag, which would otherwise
print to stdout and break this exact-match check the moment PyPI ships a
release past the pin:

<!-- verify: PYRIGHT_PYTHON_IGNORE_WARNINGS=1 uv run pyright claims tests -->
```
0 errors, 0 warnings, 0 informations
```

### Versioning

Bump `.claude-plugin/plugin.json`'s `version` in any ticket-resolution
commit that changes `claims/` — `claude plugin update` in a consuming
project gates its cache refresh on that string, not the git SHA, so an
unbumped version means the fix never reaches an installed copy no matter
how many commits land upstream. Discovered stuck at `0.1.0` through
tickets 19–36 before this was written; `epr-wrench`'s own install was
still running pre-ticket-27 code as a result. A patch-level bump
(`0.1.0` → `0.1.1`) is enough for an ordinary fix; use judgement for
anything that changes a consuming project's own required setup.

Add a matching entry to `CHANGELOG.md` in the same commit — a version
bump with no changelog entry gives a consumer reading it after `claude
plugin update` nothing to go on beyond a bare number, which is exactly
the "reading the source to understand what changed" cost this file
exists to remove. One or two bullet points, from a consuming project's
own point of view (what they'd notice), not an implementation narrative
— the commit message and PR already carry that.

### Shipping a change

`main` is protected by a repository ruleset — no direct push lands there,
not even from a repo admin (`current_user_can_bypass: never`); this is
deliberate, not a gap to work around. Land a change by pushing a branch
and opening a pull request:

```sh
git checkout -b <branch>
# commit(s), each git commit -s'd — see CONTRIBUTING.md's DCO section
git push -u origin <branch>
gh pr create --title "..." --body "..."
```

The PR can't merge until its own commit — not a stale earlier one, the
branch must be up to date with `main` — has three required status checks
green: `Typecheck`, `Test` (both from `.github/workflows/ci.yml`), and
`Signed-off-by` (`.github/workflows/dco.yml`, the DCO check — fires on
`pull_request` only, never on a plain push, so it never shows up outside
a PR). No required-reviewer count is set (this project's sole maintainer
would otherwise be blocked from merging their own work), so a green PR is
sufficient — merge it yourself once CI passes, the same way any other
merge lands.

### Check severity: recall over precision

When a check is genuinely torn between two thresholds — a duplication
count, a churn cutoff, how loosely a match pattern should be drawn — the
one that misses less should generally win, even at the cost of more
noise: a missed claim stays invisible forever, where a false positive is
at least visible and can be dismissed. `check-config-defaults`,
`check-env-vars`, and `check-cli-flags` each shipped with severity
explicitly marked provisional rather than a threshold reasoned to a
guessed-perfect balance — advisory until real usage gives an actual
false-positive rate to argue from beats tuning tight upfront and never
seeing the claims a stricter pattern would have silently dropped.

Not a blanket license to skip judgment: cite this principle for a real,
already-reasoned-through precision/recall tradeoff, not instead of
reasoning about one.

## Agent skills

### Issue tracker

Issues tracked as GitHub issues. See `docs/agents/issue-tracker.md`.

### Triage labels

Five canonical roles, label string equal to name (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`). See `docs/agents/triage-labels.md`.

### Domain docs

Single-context layout — `docs/adr/` at repo root, plus a root `CONTEXT.md`
added lazily if and when a cross-cutting term needs one. See
`docs/agents/domain.md`, which says to proceed silently when either is
absent rather than create it upfront.
