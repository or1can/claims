# 08 — Port stale-claims check (advisory)

**What to build:** a churn-ranked staleness check — ranks prose sections by
how much the code subject they name has changed since the claim was last
touched — registered as an **advisory** (candidate-list) check.

**Blocked by:** 06.

**Status:** resolved

- [x] Given a fixture repo, sections are ranked highest where the named
      subject has the most commits since the claim's last edit.
- [x] A claim and its subject edited in the same commit scores at (or near)
      zero — the check's own output documents this as a known blind spot,
      not a silently accepted gap.
- [x] Never fails the run (advisory, exit 0 regardless of findings) — it
      produces a ranked list, not a verdict.
- [x] Demonstrated end-to-end via the CLI against a fixture repo with at
      least one genuinely stale claim and one same-commit-move claim.

## Answer

`claims/checks/stale_claims.py` — `NAME = "stale-claims"`,
`check(repo_root, diff_range, config) -> list[Finding]`, self-registered as
an **advisory** check (`gate=False` on every finding) at import time, wired
into `claims/checks/__init__.py` alongside ticket 07's check.

Ported from `ratect`'s `tools/stale-claims.py` (Apache-2.0 prior art, same
author — `ratect` is the publicly-named source project in spec.md, unlike
the two private ones, so this is a direct port rather than a from-scratch
rewrite). Same scoring method: a claim is a Markdown section (heading to
next heading, whole file if none); its subject is the code it names — an
explicit relative path that exists in the tree, or a backtick bare name
matching a tracked file's stem uniquely (an ambiguous stem is dropped
rather than guessed at); score is the largest fraction of any subject's
commit history that lands strictly after the section's `git blame`
last-touch time. `CHANGELOG.md` is excluded (its entries describe a release
as it shipped; their subjects moving afterwards is expected).

Generalised past the Rust-specific original: no `*.rs`-only path pattern,
and no per-project directory allowlist restricting where a bare backtick
name counts as a subject (ratect only trusted `decisions/` and
`AGENTS.md`). Both prices — matching any tracked file's extension, and
bare-name noise outside a curated directory list — are paid deliberately;
folding a directory allowlist back in would be embedding one project's
domain knowledge into a generic checker, which the check inventory's
per-check split (spec.md) keeps out of the shared tools.

The same-commit blind spot is real and documented in the module's own
docstring, not just in spec.md: two edits sharing a commit — or even just a
committer *timestamp*, since the comparison is by `git blame`'s
second-resolution `committer-time` — can't be told apart from one, so a
claim rewritten to match a same-commit code change scores zero for that
subject and is invisible to this check. `register_check` never runs a
gate, so this and every other blind spot only ever produces a shorter
candidate list, never a wrong pass/fail verdict.

Tests: `tests/test_stale_claims.py`, a fixture git repo with commit
timestamps under test control (`GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE`) —
one subject churned 3 of 4 commits after its claim's only touch (ranks
first), one churned 1 of 2 (ranks second, proving the ordering is by score
and not discovery order), one edited in the same commit as its claim
(produces no finding at all, proving the blind spot rather than just
asserting a low score), plus `CHANGELOG.md` exclusion and a CLI
end-to-end test asserting exit code 0 regardless of findings. 30 tests
total across the suite (`python3 -m unittest discover -s tests -p
'test_*.py'`), all green.

Post-review (`/code-review` against this ticket) found two real bugs, both
fixed: `git ls-files` output was split on all whitespace
(`.stdout.split()`), which shreds a tracked filename containing a space
into two bogus paths and crashes `read_text` on the nonexistent half — an
advisory check crashing violates its own "never fails the run" contract;
fixed by splitting on newlines instead, with a regression test. Git
subprocess output was decoded with strict UTF-8 (`text=True` with default
error handling) while file reads two lines below already used
`errors="replace"` — inconsistent, and `git blame` can echo non-UTF-8
commit-author bytes from history; fixed by adding `errors="replace"` to
the shared `_git` helper. A third finding — the same-commit docstring
claim being imprecise about timestamp- vs. commit-granularity — is folded
into the docstring wording above. `executable_claims.py`'s identical
`ls-files`-split latent bug is out of this ticket's scope; noted in
`TODO.md`.
