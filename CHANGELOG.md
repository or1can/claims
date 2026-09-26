# Changelog

All notable changes to this plugin are documented here. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions match
`.claude-plugin/plugin.json` and [Semantic Versioning](https://semver.org/)
(a fix is a patch bump; a new check, `claims.toml` key, or doc-author-
facing marker syntax is a minor bump). `claude plugin update` in a
consuming project gates its cache refresh on this version string, not the
git SHA — so this is also the place to check whether an update actually
reached you, not just that one was pushed upstream.

## [Unreleased]

## [0.12.7] - 2026-09-26

- Fixed: `stale-claims` no longer treats your root `claims.toml` as the
  subject of a section. Since 0.12.6, a backticked `claims` (the tool's
  name) or `claims.toml` could resolve to it, so edits to your own
  configuration flagged most prose that mentions the tool.

## [0.12.6] - 2026-09-26

- Fixed: in `stale-claims`, a bare backticked name no longer resolves to
  a file matching `[stale-claims] exclude`. A file named by explicit path
  is still a subject even when excluded. A stem an excluded file shared
  with one other file now names that other file, so a project whose
  excluded files shared stems with its own may see new findings.

## [0.12.5] - 2026-09-26

- Fixed: a `claims.local.toml` table that names no registered check, such
  as `[executable_claims]` for `[executable-claims]`, is now a gate
  finding against that file, with the same suggestion `claims.toml` gets.
  It previously granted nothing and reported nothing. `[hook]` there is
  reported too, since the hook's switch is read from `claims.toml` only.

## [0.12.4] - 2026-09-25

- Fixed: the commit hook now gates a `git commit` run through a git alias
  (`git ci` with `alias.ci = commit`, or a `!` shell alias that commits),
  inside `bash -c`, `sh -c` or `zsh -c`, or through `eval`. Each of these
  previously let the commit land with every check skipped. A shell called
  by path (`/bin/zsh -c`) is still not gated.
- Changed: the hook now also starts for any Bash command that runs
  `bash`, `sh`, `zsh` or `eval`, so that it can look inside them. It
  returns straight away when no commit is found.

## [0.12.3] - 2026-09-25

- Fixed: `claim-words`' `files` globs now match case-sensitively on every
  platform, like every other check's globs. On Windows they previously
  ignored case, so a `docs/*.md` glob also designated the pages of a
  capitalised `Docs` directory.

## [0.12.2] - 2026-09-25

- Fixed: `check-config-defaults` no longer reads lines inside a fenced
  code block. A page showing the claim syntax as an example, such as
  `` `TIMEOUT` defaults to `30` `` inside a fence, was previously checked
  as a real claim. `check-env-vars`, `check-file-refs` and
  `check-cli-flags` already skip fenced blocks the same way.

## [0.12.1] - 2026-09-25

- Fixed: the skill's on-demand `claims.toml` review now checks the
  `historical` globs of `check-links` and `check-file-refs`. A
  `historical` entry that matches no tracked file was previously never
  reported, so a mistyped one went on resolving every mention against the
  working tree without anything saying so.

## [0.12.0] - 2026-09-25

- Added: `check-file-refs` accepts a `historical` glob list in
  `claims.toml`, the same key `check-links` already takes. A bare path
  mention in a matching file that no longer resolves passes if a file was
  at that path in the commit that wrote its line, so a shipped changelog
  or decision-record entry citing a file by its bare path no longer
  blocks moving that file. Uncommitted lines, and lines a later commit
  touched, are still checked; a finding on a historical line names the
  commit it was also tested at. See `docs/checks/check-file-refs.md`.

## [0.11.1] - 2026-09-25

- Changed: the `claim-words` page no longer recommends designating a
  changelog or decision records. Its `files` row now gives the test —
  would you want this file's claims re-verified against the tree as it
  stands? — and names those two as files that usually fail it; the
  example configuration is `["spec.md", "CONTEXT.md", "AGENTS.md"]`. If
  you followed the old advice, expect most of this check's findings in
  those files to be noise, and consider dropping them.
- Changed: the Concepts page's "record-like" is replaced by live and
  dated claims, under the headings "Live and dated claims" and
  "Designated files".

## [0.11.0] - 2026-09-25

- Added: `temporal-words`, an advisory check that reads the sentences a
  diff added to the pages you designate and reports the ones dated by a
  version number (`0.3.0`, `pre-0.9.0`) or by version-history wording
  (`yet`, `used to`, `currently`, `previously`, and `now` beside a
  backticked citation). A reference page has no version picker, so
  "since 0.21.0" is unusable to a reader and a "yet" goes false the day
  the thing lands. Opt in with `files` under `[temporal-words]`; with no
  section the check reports nothing. Give it the opposite file set from
  `claim-words`: a changelog and release notes are where this wording is
  correct. A match inside a code span or a fenced block is never
  reported, and a blockquote does not exempt a sentence here the way it
  does under `claim-words` — see `docs/checks/temporal-words.md`.

## [0.10.5] - 2026-09-25

- Fixed: the Configuring page and the `check-citations` and
  `judgment-agent` pages no longer say that a table named for either
  check "configures nothing". Both accept `enabled = false` like any
  other check, which takes them out of the commit gate; the two checks
  read no other key.

## [0.10.4] - 2026-09-25

- Changed: the Configuring page and the `check-claims` skill now send
  you to a check's page under `docs/checks/`, which ships in the plugin
  beside `claims/`, for what the check does, every `claims.toml` key it
  reads with its shape and default, and what it misses. A check's module
  docstring under `claims/checks/` no longer carries that account; it
  holds only the reasoning behind the check.

## [0.10.3] - 2026-09-24

- Fixed: `enabled = false` under `[check-config-defaults]` no longer
  crashes the check. It read every key of its section as a setting
  mapping, so the shared per-check switch was reported as a malformed
  target instead of silencing the check at commit time.

## [0.10.2] - 2026-09-24

- Changed: the documentation site gains a Concepts page (gate versus
  advisory, mode, candidate versus verdict, designated and record-like
  files, the retired-quote exemption) and a Configuring `claims` page
  (the hook toggle, per-check `enabled`, the unrecognized-table gate,
  the fixed command blocklist, and the `claims.local.toml` grant
  mechanism). The former in-repo configuration page is gone; a check's
  own `claims.toml` keys are documented in its module docstring under
  `claims/checks/` until each check has a page of its own, and the
  `check-claims` skill now points there too.

## [0.10.1] - 2026-09-23

- Changed: this plugin's own architecture decision records moved from
  `docs/adr/` to `decisions/`, and its agent process docs from
  `docs/agents/` to `agents/`. Nothing a consuming project configures or
  runs changes; the paths only matter if you follow a pointer out of a
  check's own docstring, this changelog, or the README into the repo.

## [0.10.0] - 2026-09-21

- Added: `check-links` accepts a `historical` glob list in `claims.toml`
  for append-only records (a changelog, release notes, ADRs). A link in a
  matching file that no longer resolves in the working tree passes if it
  resolved at the commit that wrote its line, so a page those records
  link to can be renamed or restructured without editing the record or
  leaving stub headings behind. Uncommitted lines are unaffected, and a
  line older than the commit that first added `claims.toml` is never
  flagged. See `decisions/0002-historical-links-resolve-at-their-own-commit.md`.

## [0.9.0] - 2026-09-17

- Added: any check can now be silenced from the automatic commit-time
  gate on its own, via `enabled = false` in that check's own
  `claims.toml` section — alongside the existing plugin-wide `[hook]
  enabled = false`, not instead of it. `python3 -m claims.cli` and the
  `check-claims` skill are unaffected either way; both keep showing that
  check's findings on demand.

## [0.8.0] - 2026-09-17

- Added: `stale-claims` now accepts its own `exclude` glob-list key
  (`claims.toml`), same shape as every sibling check's `exclude` — it was
  the one check missing this, with only the built-in `CHANGELOG.md`
  exclusion and no way for a project to name its own.

## [0.7.0] - 2026-09-17

- Added: `check-file-refs` now accepts an explicit inline annotation
  immediately after a bare path mention — a template placeholder like
  `decisions/NNNN-slug.md`<!-- example --> or a fully hypothetical
  example — to declare it's not a real path, so it stops gating
  identically to a broken reference. See `claims/checks/check_file_refs.py` for the
  exact syntax. An annotation with nothing valid immediately before it is
  itself an advisory finding.

## [0.6.9] - 2026-09-17

- Fixed: `check-file-refs` false-positived on a home-directory reference
  (`~/.docker/config.json`) or a host-absolute path
  (`/etc/docker/daemon.json`) — neither is a repo-relative claim, but the
  leading `~`/`/` was silently dropped before resolution, so both were
  checked against the repo root and reported as broken.
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
  `decisions/0001-executable-claims-deny-by-default.md`.

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
