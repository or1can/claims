# Changelog

All notable changes to this plugin are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions match
`.claude-plugin/plugin.json` and [Semantic Versioning](https://semver.org/)
(a fix is a patch bump, a new check or `claims.toml` key is a minor bump).
`claude plugin update` in a consuming project gates its cache refresh on
this version string, not the git SHA — so this is also the place to check
whether an update actually reached you, not just that one was pushed
upstream.

## [Unreleased]

- Added this changelog, so a version bump carries an explanation
  consumers can read without cloning the repo and reading the diff.

## [0.6.8] - 2026-09-16

- Fixed: `check-file-refs` gated a correctly-cited, deliberately
  gitignored file (e.g. `.claude/settings.local.json`) identically to a
  typo. A candidate matching a new `known_untracked` glob list
  (`claims.toml`) is exempted from the git-tracked-set requirement, but
  still has to resolve to a real file confined to the repo.

## [0.6.7] - 2026-09-16

- Fixed: `check-file-refs` only ever resolved a bare path mention against
  the repo root. A candidate that doesn't resolve there is now tried
  again against the citing file's own directory — a per-skill
  `references/*.md` layout, cited from its own sibling doc, no longer
  false-positives.

## [0.6.6] - 2026-09-16

- Fixed: `executable-claims` blocked safe `N>&M` file-descriptor
  duplication (`2>&1`) identically to a real `>&file` write, breaking the
  standard "capture stderr too" idiom most test runners (including
  Python's own `unittest`) need for their real summary line.

## [0.6.5] - 2026-09-16

- Documented the class-sweep step for broadening a search after a
  `judgment-agent` verdict comes back refuted (`claims/skill/SKILL.md`);
  no behavior change.

## [0.6.4] - 2026-09-16

- Added `check-cli-flags` (advisory): flags a claim naming both a script
  and a CLI flag together where `<script> --help` doesn't actually list
  it. Shares `executable-claims`' deny-by-default local-grant mechanism.

## [0.6.3] - 2026-09-16

- Added `check-env-vars` (advisory): flags a backtick-quoted
  `ALL_CAPS_WITH_UNDERSCORES` name that doesn't appear anywhere in a
  configured scope of files (`.env.example` by default).

## [0.6.1] - 2026-09-16

- Added `check-config-defaults` (advisory): flags a claim shaped `` `NAME`
  defaults to `value` `` whose stated value doesn't match the
  project-mapped `file:line` holding that setting's real default.

## [0.6.0] - 2026-09-16

- Added `check-file-refs` (gate): flags a bare, unmarked prose mention of
  a file path that doesn't resolve to a tracked file.

## [0.5.3] - 2026-09-15

- Documented the `judgment-agent` candidate → subagent verdict loop
  (`claims/skill/SKILL.md`); no behavior change.

## [0.5.2] - 2026-09-15

- Added the `check-claims` skill's on-demand, explicit-ask-only review of
  whether a project's own `claims.toml` values are actually doing
  anything (a stale `exclude` glob matching nothing, say).

## [0.5.1] - 2026-09-15

- Fixed: `restatement`'s `extensions` config didn't coerce a bare string
  to a one-element list, unlike every other list-shaped config key.

## [0.5.0] - 2026-09-15

- Added a gate finding for a `claims.toml` top-level table that names
  neither a registered check nor `[hook]` (e.g. a typo'd
  `[executable_claims]`) — previously that section's keys silently
  configured nothing.

## [0.4.0] - 2026-09-15

- Changed: `executable-claims` now denies a marker's command by default,
  requiring an exact-string grant in a git-ignored, per-machine
  `claims.local.toml` before it will run. See
  `docs/adr/0001-executable-claims-deny-by-default.md`.

## [0.3.0] - 2026-09-14

- Changed: `executable-claims` rejects a marker command piping through
  `sed`/`awk`/`grep` — untestable inline text logic that only ever
  existed as a string in an HTML comment.

## [0.2.6] - 2026-09-14

- Added `stale-claims`' `module_reference_scope` config, scoping which
  files a bare module citation counts as a subject in.

## [0.2.5] - 2026-09-14

- Changed: `spliced-docs`' noisier "unknown" mode is now opt-in via
  `claims.toml`'s `modes` key rather than always running.

## [0.2.4] - 2026-09-14

- Fixed: `restatement` no longer flags text duplicated on purpose across
  more than `duplication_threshold` files (a shared license header, a
  generated banner) every time one copy changes.

## [0.2.3] - 2026-09-14

- Changed: `executable-claims`' timeout is now configurable
  (`claims.toml`'s `timeout` key) and reports advisory, not gate, since a
  timeout means the check never got an answer, not that the claim is
  false.

## [0.2.2] - 2026-09-14

- Added a config-driven `exclude` glob list for `executable-claims` and
  `check-links`.

## [0.2.1] - 2026-09-13

- Fixed: the automatic hook now gates specifically on `git commit`, not
  every `Bash` tool call.

## [0.2.0] - 2026-09-12

- Established this versioning policy (see `AGENTS.md`'s own "Versioning"
  section) after discovering the version had been stuck at `0.1.0` since
  the plugin's initial packaging, silently starving installed copies of
  every fix landed since.

## [0.1.0] - 2026-09-09

- Initial plugin packaging and distribution.
