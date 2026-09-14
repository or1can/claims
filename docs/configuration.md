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
| `extensions` | list of extra file extensions, **added** to the built-in set (`.md`, `.swift`, `.py`, `.sh`, `.yml`) | the built-in set alone | This project has source in a language the default set doesn't cover (e.g. `.rs` for a Rust project) and wants restatement to scan it too. |
| `duplication_threshold` | integer (`bool` rejected) | `1` | Text is duplicated **on purpose** across more files than the default tolerates (a shared license header, a generated banner) and every copy but one shouldn't be flagged every time the other changes. Lower to `0` to flag every duplicate immediately instead. |

## `check-links`

```toml
[check-links]
exclude = ["docs/legacy/*.md"]
```

| Key | Shape | Default | Reach for this when |
| --- | --- | --- | --- |
| `exclude` | list of glob strings (bare string → one-element list) | `[]` — nothing excluded | A file's internal links/anchors shouldn't be validated — e.g. a tutorial whose example deliberately links to a heading that doesn't exist yet. |

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
