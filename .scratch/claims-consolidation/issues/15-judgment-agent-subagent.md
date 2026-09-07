# 15 — Judgment-agent subagent

**What to build:** a subagent that takes the ranked candidates from ticket
14, reads the actual code for each, and produces a verdict citing a
`file:line` or the exact command it ran — never grepping the prose
describing the claim. Never blocks a commit on its own judgment.

**Blocked by:** 14.

**Status:** resolved

- [x] Given a known-true architectural claim and a known-false one against
      real code, the subagent correctly distinguishes them.
- [x] Every verdict cites a `file:line` or the command run — a verdict with
      no evidence attached is treated as a failure of the subagent, not an
      acceptable output.
- [x] The subagent does not grep for vocabulary describing the claim as its
      evidence-gathering method — verified by checking it reads/executes
      the actual code path the candidate names.
- [x] Tested via behavioral/golden fixtures (known-true/known-false cases),
      not unit tests — this is a different testing shape from every other
      check in this batch, and the ticket's own test suite should say so.

## Answer

Built as `claims/subagent/judgment_agent.md` — a Claude Code subagent
definition (frontmatter `name`/`description`/`tools`, then the system
prompt body). Ticket 18 (plugin packaging, not yet built) is expected to
move or copy this file into wherever the plugin's actual agent-discovery
path ends up; this ticket only needed the prompt/spec itself, per spec.md's
Further Notes ("the subagent's own instructions are not yet written").

The prompt's one hard rule, stated explicitly: never grep for the claim's
own descriptive vocabulary as evidence — `Grep`/`Glob` may only *locate* the
subject by exact symbol/path, never search for words like "thread-safe" or
"always" that appear in the prose. Evidence is mandatory in every verdict,
including `inconclusive`, and the output contract is one JSON object per
candidate: `{candidate, verdict, evidence, reasoning}`.

**Testing** — per spec.md's Testing Decisions, this is "a different testing
shape... behavioral/golden-fixture evaluation... not a unit test." Built
accordingly, not as a `unittest` case:

- `tests/fixtures/judgment_agent_golden/{known_true,known_false}/` — the
  same claim text ("every method acquires `self._lock` before touching
  `self._store`") against two versions of a five-line `Cache` class, one
  where `clear()` actually takes the lock and one where it doesn't. Chosen
  specifically so a grep for `_lock`/"thread-safe" hits in *both* fixtures
  — only reading `clear()`'s body distinguishes them, exercising the "don't
  grep the prose" rule directly rather than by assertion.
- `scripts/run_judgment_agent_golden.py` — shells out to a live
  `claude -p --append-system-prompt <this file's body> --output-format json`
  per fixture, extracts the verdict JSON, and checks it against
  `expected_verdict.json` plus a non-empty `evidence` field. Deliberately
  not under `tests/` and not named `test_*.py`, so
  `unittest discover -s tests -p 'test_*.py'` never collects it — it costs a
  real API call per run and isn't deterministic across model versions,
  unlike every other check's fixture-based test in this batch. Run by hand:
  `python3 scripts/run_judgment_agent_golden.py`.

Ran it: both fixtures passed — `known_true` confirmed citing `cache.py:8-22`
(read every method body); `known_false` refuted citing `cache.py:20-21`
(`clear()` calls `self._store.clear()` with no `with self._lock:`). 111
pre-existing `unittest` tests unaffected and still green.

Post-review (`/code-review` against this ticket) found one real bug, fixed
before commit: both `claim.md` fixtures cited `repo/cache.py:4`, but the
harness runs the subagent with `cwd` already set to the fixture's `repo/`
directory — a literal `Read repo/cache.py` from inside that cwd 404s, one
directory too deep. Reworded the claims to `cache.py:4`, matching the cwd
the harness actually sets; re-ran, both fixtures still pass. The review's
second finding — that resolving this ticket should append a context
pointer to `map.md`'s Decisions-so-far, per `docs/agents/issue-tracker.md`
— was checked against actual practice and not applied: no implementation
ticket since 06 touches `map.md` on resolve (that convention belongs to the
5-ticket wayfinder phase, already superseded by `spec.md`), so doing it
here alone would be inconsistent with the whole batch. Logged the doc/
practice drift in `TODO.md` instead.

Second `/code-review` pass (Standards + Spec axes, against the resolved
ticket), fixed before a follow-up commit:

- Standards flagged `_extract_verdict`'s greedy `re.compile(r"\{.*\}",
  re.DOTALL)` — first-`{`-to-last-`}` silently grabs the wrong span if the
  model ever wraps its verdict object in extra text. Replaced with a
  balanced-brace scan from the first `{`.
- Spec flagged that checkbox 3 ("verified by checking it reads/executes
  the actual code path") was earned only indirectly — the harness checked
  the final verdict string, never the subagent's actual tool calls, so a
  lucky grep-and-hallucinate could pass undetected. Switched the harness to
  `--output-format stream-json`, which exposes every tool call the
  subagent made; it now asserts no `Grep` call's pattern matches the
  claim's own descriptive vocabulary (as opposed to a citation's exact
  symbol/file name, which is a legitimate Grep target) and that some tool
  call actually referenced the cited file. Re-ran both fixtures against
  the strengthened harness — both still pass, `known_true` and
  `known_false` each confirmed to have read `cache.py` directly rather
  than matched on vocabulary.
- Standards also noted (judgement call, not a hard violation — no prior
  subagent file in this repo to set a narrower convention) that the
  subagent's `Bash` grant has no tool-level restriction stopping a mutating
  command, so "advisory only" is enforced by the prompt's own Scope
  section alone. Documented this explicitly in
  `claims/subagent/judgment_agent.md` as a known limitation, rather than
  leaving it an implicit gap — a caller needing a stronger guarantee scopes
  tools per invocation instead, which is exactly what the golden harness
  itself already does (`--allowedTools Read,Glob,Grep`, no `Bash`).

111 pre-existing tests still green throughout.

**Two design decisions surfaced to the user before building, both taken as
recommended:** (1) the subagent file's location, given ticket 18 hasn't
built the plugin scaffold yet — `claims/subagent/judgment_agent.md`,
mirroring `claims/checks/`'s layout, over a root-level `.claude/agents/`
that risks colliding with ticket 18's actual plugin layout; (2) the golden
harness shells out to a real `claude -p` call rather than stubbing the
model behind an injectable interface, so the ticket's "correctly
distinguishes them" criterion is actually proven now rather than deferred.
