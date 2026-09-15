---
name: check-claims
description: Runs every currently registered claims check against the calling project and reports every finding in one pass. Use whenever the user asks to check claims or verify documentation accuracy at any point mid-task — not only at commit time, which this plugin's PreToolUse hook already covers automatically.
---

# Check claims

Runs the shared core runner (`claims.runner.run`) via its CLI adapter and
reports the result. This is the on-demand counterpart to the plugin's
automatic `git commit` hook — same runner, same checks, just invoked by
request instead of automatically.

## Running it

Run, from anywhere:

```bash
PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -m claims.cli --repo-root <path to the project being checked>
```

Add `--diff-range <range>` to check something other than the working tree
against `HEAD` — for example `--diff-range main..feature` to check a whole
branch.

## Reporting the result

Show the user the CLI's output verbatim — every finding line, then its
summary line (`N checked, M finding(s), G gate failure(s)`) — rather than
summarizing or filtering it yourself.

The one case to get right: if the runner has zero checks registered, the
CLI prints `0 checked — no checks registered (failure, not a clean pass)`
and exits non-zero. Report that as a failure, exactly as worded — never
read "no findings" or "nothing printed" as a clean pass. This mirrors the
same honesty rule every individual check in this plugin already follows
(most visibly `executable-claims`, which fails a sweep that finds zero
markers for the same reason).

A gate finding (`[GATE] ...` in the output) means something in the checked
project should not be committed as-is; surface it as a blocking problem for
the user to fix, not merely advisory. An `[advisory]` finding is worth the
user's attention but isn't asserting the project is broken.

## Coverage

`claims.cli` imports `claims.checks`, which registers every built-in check
at import time — so the command above always exercises whatever is
currently registered. A later addition to that package reaches this skill
automatically; nothing here needs to change. This is specific to the
normal check pass above — the config-review capability below reads two
hand-maintained maps in `claims/config_review.py`, not the live check
registry, so a new check's own glob-shaped config key needs those maps
updated by hand (a test in `tests/test_config_review.py` fails loud if
that's missed).

## Reviewing whether config actually fits (on demand only)

A second, separate capability (ticket #22) — invoke it only when explicitly
asked to review, sanity-check, or audit the calling project's `claims.toml`
(phrasing like "review my claims.toml", "does my config actually do
anything", "am I missing coverage from a stale exclude"). **Never** run
this as part of the normal check pass above, the automatic hook, or CI —
it produces reasoned prose, not `Finding`s, and has no gate/advisory
severity to report through that pipeline.

A validly-shaped `claims.toml` entry can still be silently inert — a glob
that matches zero tracked files, an `extensions` entry no tracked file
has — and nothing in the normal check pass surfaces that; it only means
whatever that entry was supposed to opt in or out of is quietly not
happening.

1. Load the project's config and compute the mechanical facts — never
   approximate this by re-deriving matching semantics from the raw TOML
   yourself. `repo_root` must be the project's own repo root, not a
   subdirectory — `config_value_matches` raises `ValueError` otherwise,
   rather than silently computing matches against the wrong, narrower set
   of tracked files:

   ```bash
   PYTHONPATH="${CLAUDE_PLUGIN_ROOT}" python3 -c "
   from pathlib import Path
   from claims.config import load_config
   from claims.config_review import config_value_matches

   repo_root = Path('<path to the project being reviewed>')
   for m in config_value_matches(repo_root, load_config(repo_root)):
       if m.error is not None:
           print(f'[{m.check}] {m.key} = {m.value} -> unreadable: {m.error}')
       elif not m.matched_files:
           print(f'[{m.check}] {m.key} = {m.value!r} -> matches nothing')
   "
   ```

   Each printed line names the check, the config key, and the configured
   value that currently matches nothing in the tracked tree. A `-> unreadable`
   line means the value itself couldn't be read as a list of strings (e.g.
   `exclude = 5`) — that's already a hard gate-crash finding on any normal
   run through the hook/CLI, so just note it in passing rather than
   reasoning about typo-vs-deliberate for it. A value that does match
   something prints nothing at all; silence for the rest of the config is
   the expected, boring case.

2. For every `ConfigValueMatch` with `matched_files == ()`, reason about
   whether that's likely a typo/stale entry or a plausible deliberate,
   forward-looking choice (e.g. a project adding `.rs` to
   `restatement.extensions` before its first Rust file lands) — using the
   project's actual file layout and language mix as evidence, and
   `docs/configuration.md`'s own "reach for this when" guidance for that
   key as context for what the entry is supposed to accomplish. This is
   the same evidence-citing standard `judgment-agent`'s subagent already
   holds itself to: a verdict with cited reasoning, never a bare
   pattern-match flag.
3. Report conversationally — the check, the key, the value, what you
   found, and your reasoned judgment — not as `Finding` lines and not with
   a pass/fail summary line. A value that does match something needs no
   mention; only a zero-match value is worth surfacing.

Not covered by this step (tracked separately, not this capability's job):
an unrecognized top-level table name is a mechanical hard error the
runner itself already gates on (ticket #21, no judgment involved); a
typo'd key *within* an otherwise-correctly-named section isn't detected
at all yet, pending schema-declaration infrastructure that doesn't exist;
and this never recommends settings for a project with no `claims.toml` at
all — it reviews what's already there, it doesn't onboard from scratch.
