# 20 — check-links gate-fails the CLAUDE.md→AGENTS.md symlink convention

**What to build:** `claims/checks/check_links.py`'s `_read_text` refuses to
read *any* symlink (`if path.is_symlink() or not path.is_file(): return None`),
deliberately, per its own comment — "an arbitrary-target symlink must not
crash the check." But that makes a tracked symlink whose target is inside the
repo indistinguishable from one that isn't: a link to `../CLAUDE.md`, where
`CLAUDE.md` is a symlink to `AGENTS.md` (the exact convention
`executable_claims.py`'s own comment names — "A repo's CLAUDE.md is
conventionally a symlink to AGENTS.md"), is reported as a **gate**-failing
broken link. Confirmed live against `ratect`'s real tree during ticket 19:
`decisions/0001-two-binaries.md:78`'s `../CLAUDE.md` link fails for exactly
this reason.

`_target_slugs`/`_resolve` already do the work of confining a *path* read to
`repo_root` (guarding against `../..` escapes and symlinked ancestor
directories) — the fix is resolving a symlinked *file* the same way: follow
it if the resolved target stays within `repo_root`, keep refusing it
(reporting broken, not crashing) if it doesn't.

**Blocked by:** 13.

**Status:** resolved

- [x] A tracked file that is a symlink to another tracked file inside the
      repo (the `CLAUDE.md` → `AGENTS.md` pattern, or an equivalent fixture)
      is read through and its heading anchors validated normally — not
      reported as a broken link.
- [x] A symlink whose resolved target lands outside `repo_root` is still
      refused and reported broken, not silently followed.
- [x] A regression test reproduces the `CLAUDE.md`/`AGENTS.md` shape
      directly (a fixture repo with that symlink pair), not just asserted
      against `ratect`'s real tree.
- [x] Full test suite and `pyright claims tests` stay clean.

## Comments

Fixed in `check_links.py`'s `_target_slugs` (the function that actually
resolves a link's *target*, not `_read`, which only reads the citing file —
the ticket's `_read_text` reference predates a since-renamed helper). It was
bailing on `candidate.is_symlink()` before ever checking where the symlink
led. Removed that early return; `real = candidate.resolve()` plus the
existing `real.is_relative_to(repo_real)` check (added for ticket 13's
symlinked-directory case) already does the confinement — a symlink target
landing inside `repo_root` is now read and its headings validated, one
outside it is still refused and reported broken.

Two regression tests added: one reproducing the `CLAUDE.md` -> `AGENTS.md`
shape directly (a tracked symlink whose target is a real in-repo file, with
an anchor that resolves against the target's headings — not flagged), one
for a tracked file-level symlink whose target resolves outside `repo_root`
(still flagged, not followed). The pre-existing symlinked-directory-escape
and dangling-symlink tests still pass unchanged. 128 tests total, all green;
`pyright claims tests` clean. `/code-review` (medium) found nothing to fix.
