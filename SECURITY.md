# Security Policy

## Supported versions

`claims` is pre-1.0: only the **latest released version** receives security
fixes. There are no maintenance branches for older releases.

## Reporting a vulnerability

Please **do not** open a public issue for a suspected vulnerability.

Instead, use GitHub's private vulnerability reporting: **[Security →
Advisories → Report a vulnerability](https://github.com/or1can/claims/security/advisories/new)**
on this repository. You'll get an acknowledgement within a few days, and
the report stays private while a fix is prepared.

## Scope worth knowing about

`claims` installs a `PreToolUse` hook that runs its full check suite
against whatever repository it's installed into, and one of those checks
(`executable-claims`) executes commands named in that repository's own
`<!-- verify: -->` markers. As of `docs/adr/0001-executable-claims-deny-by-default.md`,
a command only runs once it's been explicitly, locally granted in
`claims.local.toml` (git-ignored, per-machine) — a repo's own committed
`claims.toml` can no longer authorize execution by itself, and a
`claims.local.toml` that's ever *tracked* by git has its grants ignored
outright, since `.gitignore` alone doesn't stop an already-committed file
from being honored. Anything that lets a command run without that local
grant, that escapes the intended repository, or that runs something other
than the command a marker actually names is a vulnerability — for example,
a crafted marker or `claims.toml`/`claims.local.toml` value that reaches a
shell outside the check's own sandboxing, a tracked `claims.local.toml`
whose grants are honored anyway, or a path that lets a check read or write
outside the repo it's gating.
