# 36 — no config-driven path exclusion for `executable-claims` or `check-links`

**What to build:** `executable_claims.py`'s and `check_links.py`'s `check()`
both accept a `config: Mapping[str, object]` argument (per-check section of
`claims.toml`) and ignore it entirely — there's no wired-up way for a
consuming project to exclude a path (e.g. its own append-only issue-history
directory) from either check.

Found during ticket 35's fix, noted there rather than folded in — a
different concern from that ticket's actual bug (no fence-depth tracking
in `_blocks()`), and the two turned out not to share a fix: `stale_claims.py`
was assumed, going in, to have a config-driven exclusion mechanism this
could copy the shape of — checked and it doesn't; `CHANGELOG.md` is
excluded by a hardcoded filename check
(`Path(rel).name.lower() != "changelog.md"`), not anything config-surfaced.
So there is no existing pattern in this codebase to reuse here — this
needs its own design, not a copy.

Motivating case (ticket 35's own): a project's `.scratch/`-style
append-only ticket-history directory can contain a `<!-- verify: -->`
marker shown as a documentation example inside a fence (ticket 35 fixes
that specific false-positive), but a project may still reasonably want to
exclude that whole directory from either check outright — e.g. if it
contains genuinely stale/historical executable-claims markers that are
deliberately never meant to be re-run, or broken links to since-removed
pages that are intentionally left as a historical record.

**Blocked by:** none.

**Status:** resolved

- [x] Decide the config shape (e.g. `exclude = ["path/glob", ...]` under
      each check's own `claims.toml` section) — consistent between
      `executable-claims` and `check-links` if both get it, since ticket 35
      flagged them as sharing the same gap.
- [x] `executable_claims.py`'s `check()` skips a matched path entirely
      (no findings from it, not even "no verify markers found" if it was
      the only file swept).
- [x] `check_links.py`'s `check()` skips a matched path the same way.
- [x] A regression test per check, using a real `claims.toml`-shaped
      config, not a hand-typed exclusion list bypassing the config
      plumbing.

## Answer

Config shape: `exclude = ["path/glob", ...]` under each check's own
`claims.toml` section (`[executable-claims]` / `[check-links]`), matched
with `fnmatch.fnmatch` against the repo-relative POSIX path
`tracked_files` already returns — same shape and coercion (bare string
treated as a one-element list, guarding the same typo `claim_words.py`'s
own `files` config already guards) as the one existing config-driven
path-selection precedent in this codebase, `claim_words.py`'s
`_files`/`_designated`. Not extracted into a shared helper: each check
file in this codebase already carries its own small local helpers
(`_finding`, `_read`, ...) rather than importing across checks, so a new
one-off `_exclude_patterns`/`_excluded` pair per file matches the existing
convention rather than introducing the first cross-check import for two
call sites.

Both `check()`s filter `tracked`/`sorted(tracked_files(...))` before doing
anything else with a matched path — no `read_text`, no scan, so an
excluded path contributes literally nothing, not even by omission (e.g.
`check_links.py` never adds it to `slug_cache`, so a link *into* an
excluded file from elsewhere still resolves normally; exclusion only
affects the excluded file's own outgoing markers/links).

`executable_claims.py`'s "0 checked" gate (ticket 16: never a silent
clean pass) needed one further distinction, surfaced by the ticket's own
"not even 'no verify markers found' if it was the only file swept"
wording: that gate exists to catch markers *vanishing* unexpectedly, not
a project's own deliberate opt-out. A new `excluded_any` flag, set when at
least one path was actually skipped, suppresses the footer finding
specifically when exclusion is why nothing was checked — a repo with
zero `.md` files and no `exclude` config at all still fails the gate
exactly as before (unchanged, still covered by
`test_a_sweep_finding_zero_markers_is_a_failure`).

2 tests per check (`tests/test_executable_claims.py`,
`tests/test_check_links.py`), each writing a real `claims.toml` and
loading it through `claims.config.load_config` rather than a hand-typed
dict — per the ticket's own requirement that this exercise the actual
config-parsing plumbing, not bypass it.

Post-`/code-review` (one round, both axes): three real findings, all in
this ticket's own diff, all fixed. First, naming one alias of a
symlinked `AGENTS.md`/`CLAUDE.md` pair (`executable_claims.py`'s own
documented convention) in `exclude` left the content checked, and
reported, under the other, un-named alias — the `seen`-by-real-path dedup
ran *after* the exclude check, not before it knew both aliases shared a
path. Fixed by precomputing `excluded_reals` (the set of real paths any
excluded alias resolves to) in a first pass, then filtering on that set
in the main loop, ahead of `seen`. Second, `excluded_any` alone was too
coarse a guard on the "0 checked" gate: excluding some *unrelated* path
suppressed the gate even when a different, real, swept file genuinely
carried no marker — exactly the silently-vanished-marker case ticket 16
exists to catch. Fixed with a second flag, `swept_any` (true the moment
any non-excluded file is actually scanned), narrowing the suppression to
`excluded_any and not swept_any` — nothing was swept at all, and
exclusion is why. Third, the two checks' `_exclude_patterns`/`_excluded`
were verbatim copies of each other; extracted into
`claims.config.exclude_patterns`/`path_excluded`, the one place in this
codebase that already owns config-shape concerns — and switched from
`fnmatch.fnmatch` to `fnmatch.fnmatchcase` while there, since a
git-tracked path is canonically case-sensitive and plain `fnmatch`'s
case-folding is platform-dependent. `claim_words.py`'s own pre-existing,
structurally-similar `_files`/`_designated` (this ticket's own precedent,
above) was left untouched — pre-dates this diff, out of scope for it.

Two review findings were about `claims/hook.py` (ticket 37's shipped
code, not touched by this diff) and are noted in `TODO.md` instead: a
git alias resolving to `commit` isn't recognized by `_is_git_commit`, and
a `bash -c "git commit ..."`-shaped command collapses to one `shlex`
token so no standalone `git` token is ever seen.

Post-`/code-review` (second round, 8-angle fan-out, both axes): one
finding was chased and refuted rather than fixed — a claim that
`check_links.py`'s `exclude` doesn't extend to a symlinked alias the way
`executable_claims.py`'s does. Verified directly rather than trusting the
finder's paraphrase: `check_links.py`'s own pre-existing `_read()` guard
already returns `None` for any symlink path before a line is ever
scanned, so `CLAUDE.md` (the symlink alias) was never checked as a link
*source* regardless of `exclude` — confirmed with a throwaway script
exercising both `exclude=["AGENTS.md"]` and no-exclude cases against a
real symlinked fixture; behavior was already correct, no change needed.
Two independent angles (simplification, altitude) also flagged real
redundancy in the first round's own fix: `excluded_any` was always
exactly `bool(excluded_reals)` (both derive from the same precomputed
set), so it's dropped in favor of checking `excluded_reals` directly, and
the suppression condition rewritten via De Morgan
(`swept_any or not excluded_reals`) to read as "something was swept, or
nothing was excluded" instead of a double-negated conjunction. A third
finding — `claims.toml` mistyping a check's table name (e.g.
`[executable_claims]` for the real `[executable-claims]`) silently makes
any option in it, including the new `exclude`, an inert no-op — is
pre-existing `runner.py` behavior newly made costly by this ticket; noted
in `TODO.md` rather than fixed here (fixing it means validating config
table names against the check registry, a `runner.py` change outside
this ticket's own scope). Remaining findings across all 8 angles were
either about `claim_words.py`'s pre-existing, already-flagged-as-
untouched precedent, or found no defect at all.

Verified: full suite (`python3 -m unittest discover -s tests -p
'test_*.py'`) — 176 passed (was 170; ticket 37 landed the 170 baseline).
`PYRIGHT_PYTHON_IGNORE_WARNINGS=1 uv run pyright claims tests` — 0
errors, 0 warnings, 0 informations.
