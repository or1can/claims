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

From the plugin's root directory (wherever the `claims` package was
installed), run:

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

## Coverage

`claims.cli` imports `claims.checks`, which registers every built-in check
at import time — so the command above always exercises whatever is
currently registered. A later addition to that package reaches this skill
automatically; nothing here needs to change.
