# Version-only changes as no movement

`stale-claims` counts a commit that changes only a project's own release
version, such as `version = "0.28.1"` becoming `"0.28.2"` in
`pyproject.toml`, as a change to that file. Each section naming the file
is ranked in the release's pull request, and a checked mark on one
expires. Neither is going to tell a version line apart from the rest of
the file.

## Why this is out of scope

#228 asked for one of three things: a `[subjects]` key listing per-file
line patterns whose changes don't count, a built-in rule for lines
shaped like a version, or keeping the ranking but leaving those commits
out of the score.

The cost it would remove is small and visible. In this repository a
release bump ranked 4 sections (`AGENTS.md`'s Versioning and
Typechecking, ADR 0008's Decision, ADR 0004's Consequences), each a
quick re-read. In or1can/ratect, the release `6c645e5c` bumped three
`Cargo.toml` files and `Cargo.lock`. Of the 24 sections it ranked, 1
named `Cargo.toml`, and that one named `CHANGELOG.md` and `ROADMAP.md`
as well. None of ratect's 170 `stale-claims` marks has a version file as
a subject. That is the "cheap re-read" #198 already judged worth keeping
(`comment-only-churn.md`).

Acting would need harm of a different kind. Re-reads that never find
anything can teach a reader to mark without reading, so that a real
finding in the same batch gets stamped as well. There was no sign of
that: the marks on these sections had notes specific to what was
re-read.

Two lines a future request has to respect:

- **A dependency pin is not a version-only change.** A `rev:` in
  `.pre-commit-config.yaml`, a crate's version, or the `pyright` pin in
  `pyproject.toml`'s `dev` group can be what a section's claim is about:
  "pinned to a release tag, so an upstream change applies only once a
  bump lands". The pin moving is the moment to re-read that section,
  like the "Superseded by" note in `adr-status-notes-as-churn.md`. Any
  rule here would cover a project's own release version only.
- **A manifest is not a navigation page.** `[subjects] navigation`
  would stop `.claude-plugin/plugin.json` being a subject today, since
  its version is nearly all that changes. But `navigation` means a page
  linked as "see there", and putting a manifest in it bends the term.

The score part of the request is weaker than it looks. Since ADR 0009
the score only orders the sections that are reported, and a section is
ranked only when the range changes one of its subjects, so a pull
request that leaves the version files alone never shows these sections
(`generated-subjects-and-history-weighting.md`).

## Prior requests

- #228: "stale-claims: a version-only change to a subject counts as churn"
