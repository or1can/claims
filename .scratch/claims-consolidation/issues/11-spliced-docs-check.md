# 11 — Port spliced-docs check (advisory)

**What to build:** a structural check finding a doc comment spliced onto the
wrong declaration (an edit landing between the comment and its item),
reported only when the stranded prose names an undocumented item in the same
file (or resolves to nothing anywhere in the repo). Registered as an
**advisory** check, ported for whichever language(s) the source tools
already covered — no new language-adapter interface designed in this
ticket.

**Blocked by:** 06.

**Status:** resolved

- [x] A doc comment separated from its declaration by an intervening item is
      flagged when the stranded prose names an in-file undocumented item.
- [x] A doc comment naming something that resolves to nothing anywhere in
      the repo is flagged.
- [x] A doc comment correctly attached to its declaration is not flagged.
- [x] Never fails the run (advisory).

## Answer

Built as `claims/checks/spliced_docs.py`, registered in
`claims/checks/__init__.py`. Ported from both source tools that had one —
`ratect`'s `tools/spliced-docs.py` (Rust) and Project B's
`tools/spliced-docs.py` (Swift), same author, both Apache-2.0/relicensed —
onto the *union* of their evidence rules rather than either alone: a break
in a `///` run is reported when the stranded prose names, in backticks,
either an undocumented declaration in the same file (`ratect`'s rule) or a
name resolving to nothing anywhere in the repo (Project B's stronger
variant), matching spec.md's check-inventory description of this check
directly. No adapter interface was designed — the two languages are two
independent, concrete functions (`_check_rust`/`_check_swift`) sharing only
the small `_emit` evidence step; `spec.md`'s Further Notes defers the
adapter-interface question, and this ticket doesn't need it answered to
port two already-written tools.

Swift's declaration regex (`SWIFT_DECL_RE`) is ported verbatim from
Project B's `tools/claims.py::DECL_RE`, not re-derived — that file's own
docstring exists specifically because two independently-written versions of
"what is a declaration" once drifted apart inside Project B's tools.

Not diff-scoped: every tracked `*.rs`/`*.swift` file is swept each run,
matching both source tools' whole-tree behaviour (a splice can predate the
diff being checked) and this repo's `stale-claims`/`executable-claims`
precedent for advisory/gate checks that aren't diff-scoped.

Tests: `tests/test_spliced_docs.py` (9 cases) against fixture git repos —
one undocumented-in-file and one resolves-to-nothing case per language, a
correctly-attached doc (blank `///` between summary and detail) not flagged
per language, an unclosed-backtick regression case (below), and the
advisory `gate=False`/exit-0 contract. 72 tests total across the suite, all
green.

Post-review (`/code-review`) found one real gap, fixed: the Rust and Swift
sides had been sharing one backtick-name regex, copied from `ratect`'s Rust
tool, which requires a *closing* backtick. Project B's own Swift `NAME_RE`
has no such requirement, so a malformed/unclosed backtick reference in a
Swift doc comment silently named nothing under the shared regex. Split into
`RUST_BACKTICKED` (closing backtick required, ratect's rule, unchanged) and
`SWIFT_NAME_RE` (ported verbatim from Project B's `NAME_RE`, no closing
backtick required) — `test_a_swift_unclosed_backtick_still_names_its_declaration`
pins it, and fails against the old shared regex (confirmed by hand before
committing the fix). The review's other finding — `_rust_breaks`/
`_swift_breaks` and `_check_rust`/`_check_swift` sharing an identical shape
— was left as-is: it's the direct consequence of this ticket's own "no
adapter interface" constraint, and extracting the shared shape now is
exactly the interface design spec.md defers.
