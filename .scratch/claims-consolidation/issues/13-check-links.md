# 13 — Port check-links check (gate)

**What to build:** a check validating every internal Markdown link,
including heading anchors (GitHub slug algorithm). Registered as a **gate**
check.

**Blocked by:** 06.

**Status:** resolved

- [x] A link to a path that doesn't exist is flagged.
- [x] A link to a heading anchor that doesn't resolve (including a
      multi-word heading's slug) is flagged.
- [x] A correct relative link with an anchor is not flagged.
- [x] A link ending `...md#anchor)` (path plus anchor, not just a bare
      `.md)`) is checked, not silently skipped — the source tool's first
      version required a link to end in `.md)` and so never validated any
      anchored link while still claiming full coverage; this is a named
      regression case, not just implied by the anchor-resolution bullet
      above.

## Answer

Built as `claims/checks/check_links.py`, registered in
`claims/checks/__init__.py`. Ported from Project B's `scripts/check-links`
and its shared `scripts/slugs.sh` (Apache-2.0/relicensed prior art, same
author) — the only surveyed source tool with this check; `ratect` has no
equivalent (tool-survey.md). Scope matches the source tool exactly: a link
is only checked when its target names another `.md` file (with or without
`#anchor`) or is a bare `#anchor` into the current file; images, source-file
links, and external URLs (explicit scheme guard) are out of scope, same as
upstream.

Whole-tree sweep over tracked `*.md`, not diff-scoped — a broken link is
broken whether or not this diff touched it, matching both the source tool's
own behaviour and this repo's `spliced-docs` precedent for structural gate/
advisory checks. Heading slugs follow the source tool's `slugs_of` exactly:
lowercase, strip anything outside `[a-z0-9 -]`, spaces to hyphens, no
de-duplication for repeated identical headings.

The path-plus-anchor regression (ticket's fourth criterion) is covered by
testing a *valid* path with a *broken* anchor in the `...md#anchor)` form —
proving the anchor half is actually inspected, not just the path half.

Tests: `tests/test_check_links.py` (16 cases) against fixture git repos —
broken path, broken and resolving multi-word-heading anchors, the path-plus-
anchor regression case, same-file bare-anchor links (both directions),
multiple broken links all reported (not just the first), non-`.md`/external
targets correctly out of scope, a symlinked citing file not crashing the
check, and the CLI's exit-code contract. 102 tests total across the suite,
all green.

Post-review (`/code-review`): three findings, all fixed before landing —

- The repo-escape guard tested a bare string prefix (`resolved.startswith("..")`),
  so a real file whose resolved path merely starts with those two characters
  (e.g. a file literally named `..config.md`) was a false-positive broken
  link. Fixed by replacing the lexical guard with a real-path containment
  check (`resolved.resolve().is_relative_to(repo_root.resolve())`).
- That same real-path check also closed a gap the lexical guard couldn't
  see at all: a tracked symlinked *directory* pointing outside the repo
  produces a `resolved` string with no leading `..` or `/`, so the check
  would have followed it and read off-tree content. Confined by real path
  rather than the resolved string, per the fix above.
- No caching across the sweep — a heavily cross-linked doc was re-read and
  re-scanned for headings once per referencing link rather than once per
  target file. Fixed with a `slug_cache` keyed on the resolved target path,
  populated once per distinct target regardless of how many links cite it.
