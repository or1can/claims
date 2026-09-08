---
name: check-claims
description: Runs every currently registered claims check against the calling project and reports every finding in one pass. Use whenever the user asks to check claims, verify documentation accuracy, audit prose against code, or run the claims checks — at any point mid-task, not only at commit time (that path is covered separately by this plugin's PreToolUse hook).
---

# Check claims

Runs the shared core runner (`claims.runner.run`) via its CLI adapter and
reports the result. This is the on-demand counterpart to the plugin's
automatic `git commit` hook — same runner, same checks, just invoked by
request instead of automatically.

## Running it

From the directory containing this plugin's `claims` package (this repo's
own root today; wherever ticket 18 installs it once the plugin is
packaged), run:

```bash
python3 -m claims.cli --repo-root <path to the project being checked>
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

## Why there's nothing else here

This skill never lists which checks exist. `claims.cli` imports
`claims.checks`, which registers every built-in check at import time
(`claims/checks/__init__.py`) — so running the command above always
exercises whatever is currently registered, including any check a later
ticket adds, with no change needed to this file.
