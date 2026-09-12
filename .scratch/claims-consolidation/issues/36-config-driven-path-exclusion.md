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

**Status:** ready-for-agent

- [ ] Decide the config shape (e.g. `exclude = ["path/glob", ...]` under
      each check's own `claims.toml` section) — consistent between
      `executable-claims` and `check-links` if both get it, since ticket 35
      flagged them as sharing the same gap.
- [ ] `executable_claims.py`'s `check()` skips a matched path entirely
      (no findings from it, not even "no verify markers found" if it was
      the only file swept).
- [ ] `check_links.py`'s `check()` skips a matched path the same way.
- [ ] A regression test per check, using a real `claims.toml`-shaped
      config, not a hand-typed exclusion list bypassing the config
      plumbing.
