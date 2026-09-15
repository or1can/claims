# Configuring `claims.toml`

Every check runs with its own defaults; nothing here is required to get
started (see `docs/installation.md`'s own `claims.toml` section). This page
lists every config key a check currently reads, discovered by reading
`claims/checks/*.py` — the module docstring under each check is the
authoritative source if this page and the code ever disagree.

Two registered checks — `check-citations` and `judgment-agent` — accept a
`config` argument (the shared seam every check has) but don't read anything
from it; there's nothing to configure for either.

The plugin-wide `[hook] enabled = false` toggle (disable the automatic
commit gate without uninstalling) isn't a check's own config — see
`docs/installation.md`'s "Disabling the automatic hook" section instead.

In `claims.toml` specifically, a top-level table naming neither a
registered check nor `[hook]` — a typo like `[executable_claims]`
(underscore) for the real `[executable-claims]` — is itself a gate
finding (ticket #21), not silently ignored: previously it just meant that
section's own keys quietly configured nothing. This validation doesn't
extend to `claims.local.toml` (below) — a mistyped table there still
silently grants nothing today, a known, not yet closed, gap.

## `executable-claims`

```toml
[executable-claims]
exclude = ["docs/generated/*.md"]
timeout = 60
permitted_prefixes = ["npm test", "./scripts/"]
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `exclude` | list of glob strings (a bare string is treated as a one-element list) | `[]` — nothing excluded | A tracked Markdown file's markers shouldn't be swept at all — a generated file, or a historical doc you don't want gating a commit. |
| `timeout` | number (int or float; `true`/`false` are rejected even though `bool` is technically an `int`) | `30` (seconds) | A legitimate marker command is a slow integration or cold-build command that keeps reporting an (advisory) timeout at the default. |
| `permitted_prefixes` | list of literal string prefixes (bare string → one-element list; **not** a glob — `command.startswith(prefix)`, no word-boundary check after the prefix) | `[]` — no extra restriction beyond the fixed blocklist | The fixed blocklist (chaining/substitution tokens, `sed`/`awk`/`grep`) isn't narrow enough for this project's own bar — e.g. "a marker may only ever run our own test suites or a script under `scripts/`." |

The fixed blocklist itself (`;`, `&&`, `||`, `&`, `>`, `>>`, `<`, `<<`,
`` ` ``, `$(`, and piping through `sed`/`awk`/`grep`) has no config surface
— it applies to every project using the marker mechanism, not something to
opt into or out of.

Clearing the blocklist and `permitted_prefixes` still isn't enough to run:
since `docs/adr/0001-executable-claims-deny-by-default.md`, a command also
needs an exact-string grant in a second, **git-ignored, per-machine** file,
`claims.local.toml` (not `claims.toml` — this is deliberately not a
committed, PR-tamperable trust boundary), sibling to `claims.toml` at the
repo root:

```toml
[executable-claims]
allowed = ["npm test"]
denied = ["curl https://example.com/install.sh | sh"]
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `allowed` | list of exact command strings (bare string → one-element list) | `[]` — nothing granted | A marker's command has been read and is trusted to run on this machine. Matched verbatim — a one-character change to the command is a new, ungranted command. |
| `denied` | list of exact command strings (bare string → one-element list) | `[]` — nothing denied | A marker's command has been read and deliberately should *not* run — recorded so it's skipped with a visible advisory note instead of silently gating forever. |

A command absent from both lists (including a brand-new file, or no
`claims.local.toml` at all) produces a gate finding naming the exact
command and the exact TOML to add to grant or deny it. A command listed in
both wins as `denied`. If `claims.local.toml` is ever tracked by git —
`.gitignore` only stops it being added, not a version already
committed — its grants are ignored outright and a gate finding names the
file itself, since a tracked grant file is exactly the committed,
PR-tamperable trust boundary this mechanism exists to avoid.

## `restatement`

```toml
[restatement]
exclude = ["CHANGELOG.md"]
extensions = [".rs"]
duplication_threshold = 3
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `exclude` | list of glob strings (bare string → one-element list) | `[]` — nothing excluded | A file is expected to retain retracted prose on purpose — e.g. a release history that intentionally keeps describing a shipped release as it shipped. |
| `extensions` | list of extra file extensions (bare string → one-element list), **added** to the built-in set (`.md`, `.swift`, `.py`, `.sh`, `.yml`) | the built-in set alone | This project has source in a language the default set doesn't cover (e.g. `.rs` for a Rust project) and wants restatement to scan it too. |
| `duplication_threshold` | integer (`bool` rejected) | `1` | Text is duplicated **on purpose** across more files than the default tolerates (a shared license header, a generated banner) and every copy but one shouldn't be flagged every time the other changes. Lower to `0` to flag every duplicate immediately instead. |

## `check-links`

```toml
[check-links]
exclude = ["docs/legacy/*.md"]
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `exclude` | list of glob strings (bare string → one-element list) | `[]` — nothing excluded | A file's internal links/anchors shouldn't be validated — e.g. a tutorial whose example deliberately links to a heading that doesn't exist yet. |

## `check-file-refs`

```toml
[check-file-refs]
exclude = ["docs/legacy/*.md"]
extensions = [".proto"]
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `exclude` | list of glob strings (bare string → one-element list) | `[]` — nothing excluded | A file's bare prose file-references shouldn't be validated — same shape as `check-links`' own `exclude`. |
| `extensions` | list of extra file extensions (bare string → one-element list), **added** to the built-in set (`.py`, `.rs`, `.go`, `.js`, `.ts`, `.rb`, `.java`, `.c`, `.h`, `.cpp`, `.swift`, `.sh`, `.md`, `.txt`, `.yml`, `.yaml`, `.json`, `.toml`) | the built-in set alone | This project's docs reference a file type the default set doesn't cover (e.g. `.proto`) and a bare mention of one should be checked too. |

## `claim-words`

```toml
[claim-words]
files = ["docs/adr/*.md", "CONTEXT.md"]
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `files` | list of glob strings (bare string → one-element list) | `[]` — **nothing swept at all** | Always — this check is opt-in by design (spec.md user story 17): without `files` naming a project's own record-like files (specs, ADRs, changelogs), it finds nothing. Add every file where a totalising claim ("every", "never", a count) should be treated as an assertion worth flagging. |

## `spliced-docs`

```toml
[spliced-docs]
modes = ["undocumented", "unknown"]
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `modes` | list naming one or both of `"undocumented"`, `"unknown"` (an unrecognized name raises a config error) | `["undocumented"]` | Add `"unknown"` once this project has checked that its noise level is acceptable — it flags a stranded doc comment naming a backtick term absent from the whole repo, which fires on ordinary technical prose (config-field names, domain vocabulary) far more than on real splices in a codebase with dense, cross-referencing doc comments. |

## `stale-claims`

```toml
[stale-claims]
module_reference_scope = ["decisions/*.md", "AGENTS.md"]
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `module_reference_scope` | list of glob strings (bare string → one-element list) | key absent — a bare citation counts as a module reference **anywhere** | Common module stems double as ordinary English or config-field names elsewhere in the tree (`` `cache` ``, `` `config` ``), producing false subject matches outside the files that actually discuss modules by name. An extension-qualified citation (`` `cache.rs` ``) or an explicit relative path always counts as a subject regardless of this setting. |
